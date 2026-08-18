"""Pure-Python mirror of the LoadPilot firmware publication law.

Golden-test reference model (mission C10). This file re-implements, line
for line, the C++ lambda of the co-variant publication law so that the
hard-won measured constants (gain 0.5, emax 1.0, nudge 0.1, dither 0.05,
budget = contract x (1 - buffer%), escalation 120 s / 240 s, tail
-0.15 A/s, firewall R1/R2, fail-safe main_breaker) are locked by tests
against the real traced episodes in data/traces/.

Sources mirrored (line numbers as of 2026-08-18):
- Variant A (shipped core): esphome/packages/twc-core.yaml, script
  recompute_ct, block "PVi1-GRADE v2 CO-VARIANT" (lines 1131-1243).
- Variant B (pilot firmware, decaying tail): /Volumes/config/esphome/
  kc868-a6-1.yaml lines 1574-1594 (tail branch only; everything else is
  identical to variant A). tail_r0_a = 0.0 gives variant A exactly.

The model is a pure function: publish(inputs, state, params) returns
(published_current_A, new_state) and never mutates its arguments.
NO Home Assistant import, no I/O, no clock: time comes in via inputs.t_s.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


# =========================================================================
# Parameters: defaults are the twc-core.yaml substitutions (do NOT change
# them here without changing the firmware first, the golden tests exist
# precisely to catch such a drift).
# =========================================================================
@dataclass(frozen=True)
class LawParams:
    # twc-core.yaml line 51: twc_conductor_limit_a (Max Conductor Limit, "L")
    conductor_limit_a: float = 21.0
    # line 53: main_breaker_limit_a (fail-safe publication value)
    main_breaker_a: float = 25.0
    # line 56: contract_limit_default_a (grid contract per phase)
    contract_limit_a: float = 21.7
    # line 58: buffer_default_pct (the vehicle only exploits (1-b) of the margin)
    buffer_pct: float = 10.0
    # line 65: law_gain_default (compression gain above L)
    gain: float = 0.5
    # line 67: law_emax_default (max excursion above L)
    emax_a: float = 1.0
    # line 70: law_nudge_min_a (smallest slow-down signal, NOT a knob)
    nudge_min_a: float = 0.1
    # line 74: law_dither_a (permanent alternating dither, 1 Hz, NOT a knob)
    dither_a: float = 0.05
    # line 80: vehicle_floor_a (firewall R1: physical floor, contactor closed)
    vehicle_floor_a: float = 6.0
    # line 83: glitch_drop_a (firewall R2: sudden-drop threshold)
    glitch_drop_a: float = 5.0
    # twc-core.yaml line 1175: TOL = 1.0f (R2 candidate matching tolerance)
    glitch_tol_a: float = 1.0
    # line 1176: N_CONFIRM = 2 (samples needed to believe a sudden drop)
    glitch_confirm_n: int = 2
    # line 87: escalation_timeout_ms = 120000 (stage-1 floor/safety net)
    escalation_timeout_s: float = 120.0
    # line 95: escalation_kick_a (stage 2, 18 Aug 2026: breaks the dead-band
    # hysteresis after 2x the timeout in SUSTAINED constraint)
    escalation_kick_a: float = 0.9
    # kc868-a6-1.yaml line 69: tail_decay_aps (variant B tail decay, A/s)
    tail_decay_aps: float = 0.15
    # kc868-a6-1.yaml twc_law_tail knob (r0). 0.0 = variant A (no tail).
    tail_r0_a: float = 0.0
    # twc-core.yaml line 60: phase_count (1 or 3)
    phase_count: int = 3

    @property
    def budget_a(self) -> float:
        """twc-core.yaml line 1156: budget = climit * (1 - bpct / 100)."""
        return self.contract_limit_a * (1.0 - self.buffer_pct / 100.0)


# =========================================================================
# Inputs of one recompute tick (the firmware runs one per second).
# =========================================================================
@dataclass(frozen=True)
class LawInputs:
    t_s: float                              # absolute time, seconds
    currents_a: tuple = (0.0, 0.0, 0.0)     # per-phase incomer measure (NaN ok)
    bias_a: float = 0.0                     # twc_bias_applied (pause lever)
    contactor_closed: bool = True           # HA mirror of the TWC contactor
    contactor_mirror_ok: bool = True        # twc_contactor_seen && available
    have_measure: bool = True               # a healthy source exists
    control_enabled: bool = True            # master switch
    charge_stop: bool = False               # direct STOP lever
    law_active: bool = True                 # mode ACTIF-MAX (index 2)


# =========================================================================
# State carried between ticks (the firmware globals).
# =========================================================================
@dataclass(frozen=True)
class LawState:
    capped_since_s: float | None = None     # global capped_since_ms
    tail_since_s: float | None = None       # kc868 global tail_since_ms
    # Firewall per-phase state (twc-core.yaml lines 726-800):
    # last believed current, pending drop candidate, confirmation count.
    fw_last_i: tuple = (math.nan, math.nan, math.nan)
    fw_pend: tuple = (math.nan, math.nan, math.nan)
    fw_n: tuple = (0, 0, 0)
    escalation_active: bool = False         # observability flag (contract 3.1)


def _dither(t_s: float, amp: float) -> float:
    """twc-core.yaml line 1149: ((bnow / 1000) % 2 == 0) ? +d : -d.

    The firmware parity is on millis() since boot; wall-clock parity is
    therefore NOT reproducible from a trace. Tests either control t_s or
    absorb +/-amp in their tolerance.
    """
    return amp if (int(t_s) % 2 == 0) else -amp


def _firewall(inputs: LawInputs, state: LawState, params: LawParams):
    """Anti-glitch input firewall, twc-core.yaml lines 1166-1204.

    R2 first (lines 1177-1196): a sample-to-sample drop larger than
    glitch_drop_a must repeat on glitch_confirm_n consecutive samples
    (candidates matched within glitch_tol_a) before being believed; rises
    and gentle drops pass immediately (the safe direction). NaN input
    holds the last believed value.
    R1 second (lines 1198-1203): with the wallbox contactor closed each
    incomer phase carries at least the vehicle minimum; a lower reading
    is physically impossible. Fail-open: no reliable mirror -> no floor.
    Returns (held per-phase currents, new fw state tuples).
    """
    n_ph = 3 if params.phase_count == 3 else 1
    mi = list(inputs.currents_a) + [0.0, 0.0]
    mi = mi[:3]
    last = list(state.fw_last_i)
    pend = list(state.fw_pend)
    cnt = list(state.fw_n)
    for i in range(n_ph):
        x = mi[i]
        if math.isnan(last[i]):             # first ever sample: believed
            last[i] = x
            continue
        if math.isnan(x):                   # lost sample: hold last value
            mi[i] = last[i]
            continue
        if x >= last[i] - params.glitch_drop_a:
            # Rise or gentle drop: zero latency (line 1181).
            pend[i] = math.nan
            cnt[i] = 0
            last[i] = x
        else:
            # Sudden drop: needs confirmation (lines 1184-1195).
            if math.isnan(pend[i]) or abs(x - pend[i]) > params.glitch_tol_a:
                pend[i] = x                 # new candidate
                cnt[i] = 1
            else:
                cnt[i] += 1
            if cnt[i] >= params.glitch_confirm_n:
                last[i] = min(x, pend[i])   # drop confirmed
                pend[i] = math.nan
                cnt[i] = 0
            mi[i] = last[i]                 # held -> last believed value
    # R1 physical floor (lines 1198-1203), fail-open on mirror doubt.
    if inputs.contactor_mirror_ok and inputs.contactor_closed:
        for i in range(n_ph):
            if mi[i] < params.vehicle_floor_a:
                mi[i] = params.vehicle_floor_a
    if n_ph == 1:
        mi[1] = mi[2] = 0.0
    return mi, tuple(last), tuple(pend), tuple(cnt)


def publish(inputs: LawInputs, state: LawState, params: LawParams = LawParams()):
    """One recompute tick. Returns (published symmetric current A, state).

    Mirrors twc-core.yaml recompute_ct in this order:
    1. master switch OFF -> publish 0 (max margin, control disarmed);
    2. no healthy measure -> fail-safe main_breaker +/- dither (a STATIC
       value would latch wallbox distrust and undo the fail-safe);
    3. firewall R2 then R1 on the per-phase measures;
    4. co-variant law on the worst phase (+ variant B tail if tail_r0_a>0);
    5. escalation stage 1 (timeout) and stage 2 (2x timeout, one kick per
       episode because leaving the constraint resets capped_since);
    6. STOP floor, dither, floor at 0.

    When law_active is False (RAW / OMBRE-MAX) the firmware publishes the
    NORMAL branch and only shadows the law; this mirror always returns the
    law value (the shadow), and the escalation flag stays OFF as in
    contract 3.1 (nothing is acting on the wallbox).
    """
    L = params.conductor_limit_a
    t = inputs.t_s
    dth = _dither(t, params.dither_a)

    # ---- Branch: master switch OFF (twc-core.yaml lines 1095-1100) ----
    if not inputs.control_enabled:
        new_state = LawState(fw_last_i=state.fw_last_i,
                             fw_pend=state.fw_pend, fw_n=state.fw_n)
        return 0.0, new_state

    # ---- Branch: fail-safe, dithered (lines 1101-1116) ----
    if not inputs.have_measure:
        new_state = LawState(fw_last_i=state.fw_last_i,
                             fw_pend=state.fw_pend, fw_n=state.fw_n)
        return params.main_breaker_a + dth, new_state

    # ---- Firewall (R2 then R1) ----
    mi, fw_last, fw_pend, fw_n = _firewall(inputs, state, params)

    # ---- Co-variant law, worst phase symmetric (lines 1205-1233) ----
    worst = max(mi[0], mi[1], mi[2])
    o_raw = worst + inputs.bias_a + (L - params.budget_a)
    e = o_raw - L
    capped = state.capped_since_s
    tail = state.tail_since_s
    esc = False

    if e <= 0.0:
        # OUT OF CONSTRAINT: shifted reality, gain 1, zero delay.
        if capped is not None:
            # Exit front: arm the variant B tail (kc868 lines 1583-1585).
            tail = t
            capped = None
        # Tail purge: contactor open or variant A (kc868 line 1589).
        ctc_open = (inputs.contactor_mirror_ok
                    and not inputs.contactor_closed)
        if ctc_open or params.tail_r0_a <= 0.0:
            tail = None
        if tail is not None:
            # Variant B decaying tail (kc868 lines 1590-1595):
            # r = r0 - decay * dt ; pub = min(o_raw + r, L).
            r = params.tail_r0_a - params.tail_decay_aps * (t - tail)
            if r <= 0.0:
                tail = None
                o = o_raw
            else:
                o = min(o_raw + r, L)
        else:
            o = o_raw                        # v2 exact (variant A)
    else:
        # IN CONSTRAINT: pub = L + clamp(gain * e, nudge_min, emax); the
        # level above L IS the measured slow-down signal (micro-law:
        # L+0.1 -> ~-1 A/s ; L exactly -> HOLD ; below L -> recovery).
        o = L + _clamp(params.gain * e, params.nudge_min_a, params.emax_a)
        if capped is None:
            capped = t
        # Stage 1 (lines 1218-1225): floor/safety net after the timeout.
        if t - capped >= params.escalation_timeout_s:
            o = max(o, L + params.nudge_min_a)
            esc = True
        # Stage 2 (lines 1226-1229, 18 Aug 2026): anti-hysteresis kick.
        if t - capped >= 2.0 * params.escalation_timeout_s:
            o = max(o, L + params.escalation_kick_a)

    # ---- Direct STOP floor (line 1231) ----
    if inputs.charge_stop:
        o = max(o, L + params.nudge_min_a)

    # ---- Dither: never a dead value (line 1232) ----
    o += dth
    if o < 0.0:
        o = 0.0

    new_state = LawState(
        capped_since_s=capped,
        tail_since_s=tail,
        fw_last_i=fw_last,
        fw_pend=fw_pend,
        fw_n=fw_n,
        # Contract 3.1: the flag means the floor IS being published.
        escalation_active=esc and inputs.law_active,
    )
    return o, new_state
