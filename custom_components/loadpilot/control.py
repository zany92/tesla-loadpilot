"""Pure control policies for Tesla LoadPilot (axis B).

Charge cap (B1), convergence trim (B2) and meter-distrust detection (B4)
as PURE functions: no Home Assistant import, no clock read, no I/O. The
coordinator snapshots the impure inputs (entity states, freshness,
``time.monotonic()``) every CONTROL_TICK_S and executes the effects these
functions return. That is what makes them testable in plain pytest
(tests/ replays the field traces of 17-18 Aug 2026).

Every constant below is calibration from the pilot site. Statuses:
- field-validated: measured on the pilot under real charge
  (data/traces/2026-08-18_1317_manual_limit_tuning.log and the 17/08
  distrust episodes);
- theoretical: generic re-formulation of a validated site mechanism
  (ownership guard, arming reference, cooldown, max() over phases) or
  the whole single-phase branch, never benched.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# Coordinator state during which the trim is allowed to act (mirrors
# const.STATE_REGULATING; kept literal here so this module imports alone).
REGULATING = "regulating"

# Trim machine phases.
TRIM_IDLE = "idle"
TRIM_ARMED = "armed"
TRIM_KICKING = "kicking"
TRIM_COOLDOWN = "cooldown"

# Bias number step on the charger node (contract: 0..max, step 0.5).
_BIAS_WRITE_STEP_A = 0.5

# Float equality tolerance for bias-ownership comparisons (bias values
# are 0.5-step numbers read back from the node).
_EPS = 1e-6


@dataclass(frozen=True)
class ControlParams:
    """Site calibration + install-type bounds for the pure policies."""

    bias_max_a: float            # 16.0 three-phase / 32.0 single-phase
    max_conductor_a: float       # L, option, 21.0 tri / 32.0 mono
    cap_deadband_a: float = 0.5
    cap_decay_per_tick_a: float = 0.5
    cap_kick_margin_a: float = 1.5
    cap_kick_vehicle_over_a: float = 0.5
    band_low_offset_a: float = 0.05
    band_high_offset_a: float = 0.8
    trim_headroom_trigger_a: float = -0.3
    trim_sustain_s: float = 180.0
    trim_kick_a: float = 2.0
    trim_kick_timeout_s: float = 25.0
    trim_cooldown_s: float = 300.0
    trim_vehicle_min_a: float = 6.5
    trim_engage_drop_a: float = 1.0
    distrust_on_offset_a: float = 0.85
    distrust_sustain_s: float = 120.0
    distrust_vehicle_min_a: float = 9.0
    distrust_clear_pub_below_a: float = 1.0   # clear when pub < L - 1.0
    distrust_clear_vehicle_a: float = 7.0
    distrust_clear_sustain_s: float = 60.0


# ---------------------------------------------------------------- helpers
def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_half_away(value: float) -> float:
    """Round to 0 decimals, halves away from zero (Jinja ``round(0)``)."""
    if value >= 0:
        return float(math.floor(value + 0.5))
    return float(math.ceil(value - 0.5))


def _round_half_step(value: float) -> float:
    """Snap a bias value to the 0.5 A step of the node number."""
    return _round_half_away(value / _BIAS_WRITE_STEP_A) * _BIAS_WRITE_STEP_A


def in_dead_band(published_max_a: float, p: ControlParams) -> bool:
    """Published value parked in the charger dead band [L+0.05 ; L+0.8].

    BEHAVIOR §12: inside this band the pilot is deaf (hysteresis). The
    band is where both the cap kick and the trim are legitimate.
    """
    return (
        p.max_conductor_a + p.band_low_offset_a
        <= published_max_a
        <= p.max_conductor_a + p.band_high_offset_a
    )


# ---------------------------------------------------------- B1: charge cap
def compute_cap_bias_target(
    worst_headroom_a: float,
    vehicle_current_a: float,
    cap_a: float,
    p: ControlParams,
) -> Optional[float]:
    """Equilibrium bias for a user cap (field-validated 18/08).

    target = clamp(round0(worst_headroom + vehicle_current - cap),
                   0, bias_max). The Linky echo stays 1:1; only this slow
    offset depends on the vehicle vitals. Any non-finite input (a sensor
    publishing "nan") is REFUSED: None, never an exception (A3 guard).
    """
    if not all(
        math.isfinite(v)
        for v in (worst_headroom_a, vehicle_current_a, cap_a)
    ):
        return None
    raw = worst_headroom_a + vehicle_current_a - cap_a
    return _clamp(_round_half_away(raw), 0.0, p.bias_max_a)


def decide_cap_write(
    target_a: float,
    current_bias_a: float,
    last_own_bias_a: Optional[float],
    vehicle_current_a: float,
    cap_a: float,
    published_max_a: Optional[float],
    p: ControlParams,
) -> Optional[float]:
    """One cap-loop tick decision. None = no write.

    Order of precedence (all field-validated on 18/08 except the generic
    ownership guard, theoretical in this form):
    1. ownership guard: a bias higher than max(target, last_own_bias)+0.5
       belongs to someone else (pause, external shedding): never fight it;
    2. anti-hysteresis kick: vehicle above the cap while the published
       value idles in the dead band and the bias is not already boosted;
    3. dead band 0.5 A, then asymmetric write: raise immediately, decay
       at most 0.5 A per tick (kills the 11-16 A limit cycle).
    """
    finite_inputs = [target_a, current_bias_a, vehicle_current_a, cap_a]
    if last_own_bias_a is not None:
        finite_inputs.append(last_own_bias_a)
    if published_max_a is not None:
        finite_inputs.append(published_max_a)
    if not all(math.isfinite(v) for v in finite_inputs):
        return None  # never write from a poisoned snapshot (A3 guard)

    own_ref = (
        target_a
        if last_own_bias_a is None
        else max(target_a, last_own_bias_a)
    )
    if current_bias_a > own_ref + p.cap_deadband_a + _EPS:
        return None

    kick = (
        published_max_a is not None
        and vehicle_current_a > cap_a + p.cap_kick_vehicle_over_a
        and in_dead_band(published_max_a, p)
        and current_bias_a <= target_a + p.cap_deadband_a + _EPS
    )
    if kick:
        return _round_half_step(
            _clamp(target_a + p.cap_kick_margin_a, 0.0, p.bias_max_a)
        )

    if abs(target_a - current_bias_a) < p.cap_deadband_a:
        return None
    if target_a >= current_bias_a:
        value = target_a
    else:
        value = max(target_a, current_bias_a - p.cap_decay_per_tick_a)
    return _round_half_step(_clamp(value, 0.0, p.bias_max_a))


def decide_cap_release(
    current_bias_a: float,
    last_own_bias_a: Optional[float],
) -> Optional[float]:
    """Release decision when the cap goes back to 0 (auto mode).

    Write bias 0 ONLY when the current bias is the one this loop wrote
    (generic equivalent of the prototype "never during a pause"). None
    at startup (last_own unknown) = prudence, no release write.
    """
    if last_own_bias_a is None:
        return None
    if abs(current_bias_a - last_own_bias_a) <= _EPS:
        return 0.0
    return None


# ------------------------------------------------------ B2: convergence trim
@dataclass(frozen=True)
class TrimState:
    """Trim state machine snapshot (idle | armed | kicking | cooldown)."""

    phase: str = TRIM_IDLE
    since_mono: float = 0.0
    ref_vehicle_a: float = 0.0


@dataclass(frozen=True)
class TrimInputs:
    """Impure inputs snapshotted by the coordinator for one trim tick."""

    enabled: bool
    cap_a: float
    state: str               # coordinator state (regulating, ...)
    distrust: Optional[bool]  # None = detector unavailable
    worst_headroom_a: Optional[float]
    published_max_a: Optional[float]
    current_bias_a: Optional[float]
    vehicle_current_a: Optional[float]
    vehicle_fresh: bool


def _trim_arm_ok(inp: TrimInputs, p: ControlParams) -> bool:
    """All arming guards (prototype of 18/08, field-validated 12:57)."""
    if not inp.enabled:
        return False
    if inp.cap_a >= 0.5:  # manual cap active: the cap loop owns the bias
        return False
    if inp.state != REGULATING:
        return False
    if inp.distrust is True:  # None (detector unavailable) does not block
        return False
    if (
        inp.worst_headroom_a is None
        or inp.worst_headroom_a >= p.trim_headroom_trigger_a
    ):
        return False
    if inp.published_max_a is None or not in_dead_band(
        inp.published_max_a, p
    ):
        return False
    if inp.current_bias_a is None or abs(inp.current_bias_a) > _EPS:
        return False  # someone else is playing with the bias
    if inp.vehicle_current_a is None or not inp.vehicle_fresh:
        return False
    if inp.vehicle_current_a <= p.trim_vehicle_min_a:
        return False
    return True


def trim_step(
    state: TrimState,
    inp: TrimInputs,
    now_mono: float,
    p: ControlParams,
) -> tuple[TrimState, Optional[float]]:
    """One trim tick: (new state, optional bias write).

    Hard aborts (trim disabled, vehicle_current lost, cap > 0) send any
    phase back to IDLE without writing, EXCEPT from KICKING where the
    conditional release (bias still 2.0 -> write 0.0) is attempted first.
    """
    hard_abort = (
        not inp.enabled
        or inp.cap_a >= 0.5
        or inp.vehicle_current_a is None
        or not inp.vehicle_fresh
    )

    if state.phase == TRIM_ARMED:
        if not _trim_arm_ok(inp, p):
            return TrimState(), None
        if now_mono - state.since_mono >= p.trim_sustain_s:
            return (
                TrimState(TRIM_KICKING, now_mono, state.ref_vehicle_a),
                p.trim_kick_a,
            )
        return state, None

    if state.phase == TRIM_KICKING:
        own = (
            inp.current_bias_a is not None
            and abs(inp.current_bias_a - p.trim_kick_a) <= _EPS
        )
        if hard_abort:
            return TrimState(), (0.0 if own else None)
        if inp.state != REGULATING:
            # Firmware stage-2 escalation (or a pause) engaged mid-kick:
            # abandon to cooldown, releasing ONLY our own 2.0 kick (bias
            # still exactly trim_kick_a). A foreign bias (pause, shedding)
            # is never overwritten (BEHAVIOR §12 superposition).
            return TrimState(TRIM_COOLDOWN, now_mono, 0.0), (
                0.0 if own else None
            )
        if not own:
            # Someone else posted a bias (external shedding): the pause
            # wins, no write, cooldown anyway.
            return TrimState(TRIM_COOLDOWN, now_mono, 0.0), None
        engaged = (
            inp.vehicle_current_a is not None
            and inp.vehicle_current_a
            < state.ref_vehicle_a - p.trim_engage_drop_a
        )
        if engaged or now_mono - state.since_mono >= p.trim_kick_timeout_s:
            return TrimState(TRIM_COOLDOWN, now_mono, 0.0), 0.0
        return state, None

    if state.phase == TRIM_COOLDOWN:
        if hard_abort:
            return TrimState(), None
        if now_mono - state.since_mono >= p.trim_cooldown_s:
            return TrimState(), None
        return state, None

    # IDLE (and any unknown phase, defensively).
    if _trim_arm_ok(inp, p):
        return (
            TrimState(TRIM_ARMED, now_mono, inp.vehicle_current_a or 0.0),
            None,
        )
    return TrimState(), None


# -------------------------------------------------- B4: meter distrust
@dataclass(frozen=True)
class DistrustState:
    """Distrust detector snapshot (sustains measured by timestamps)."""

    active: bool = False
    over_since_mono: Optional[float] = None
    clear_since_mono: Optional[float] = None


def distrust_step(
    state: DistrustState,
    published_max_a: Optional[float],
    vehicle_current_a: Optional[float],
    now_mono: float,
    p: ControlParams,
) -> DistrustState:
    """One distrust tick (thresholds DERIVED from L, field-validated 17/08).

    Trip: published_max >= L + 0.85 sustained 120 s while the vehicle
    still pulls > 9 A (the 23:04 lesson is encoded: 21.45 was INSIDE the
    dead band, the threshold lives in the traction zone). Clear:
    published < L - 1.0 sustained 60 s (signal dynamic again) OR vehicle
    < 7 A sustained 60 s (the charger finally obeyed). Without
    vehicle_current the detector is DISABLED, not degraded (§4 of the
    axis-B architecture).
    """
    if not state.active:
        over = (
            published_max_a is not None
            and published_max_a
            >= p.max_conductor_a + p.distrust_on_offset_a
            and vehicle_current_a is not None
            and vehicle_current_a > p.distrust_vehicle_min_a
        )
        if not over:
            if state.over_since_mono is None:
                return state
            return DistrustState(False, None, None)
        since = (
            state.over_since_mono
            if state.over_since_mono is not None
            else now_mono
        )
        if now_mono - since >= p.distrust_sustain_s:
            return DistrustState(True, None, None)
        return DistrustState(False, since, None)

    clearing = (
        published_max_a is not None
        and published_max_a
        < p.max_conductor_a - p.distrust_clear_pub_below_a
    ) or (
        vehicle_current_a is not None
        and vehicle_current_a < p.distrust_clear_vehicle_a
    )
    if not clearing:
        if state.clear_since_mono is None:
            return state
        return DistrustState(True, None, None)
    since = (
        state.clear_since_mono
        if state.clear_since_mono is not None
        else now_mono
    )
    if now_mono - since >= p.distrust_clear_sustain_s:
        return DistrustState(False, None, None)
    return DistrustState(True, None, since)
