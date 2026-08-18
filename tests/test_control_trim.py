"""Convergence-trim (B2) state-machine tests.

Field anchor: test_full_nominal_cycle replays the live validation of
18 Aug 2026 12:57 (headroom -0.8 A held, published parked in the dead
band at 15.2 A steady vehicle draw; kick 2 A, traction engaged, release,
converged to the exact budget).
"""

from __future__ import annotations

import pytest

import loadpilot_control as control


def make_inputs(**overrides):
    """A fully-armable snapshot; override per test."""
    base = dict(
        enabled=True,
        cap_a=0.0,
        state="regulating",
        distrust=False,
        worst_headroom_a=-0.8,
        published_max_a=21.3,
        current_bias_a=0.0,
        vehicle_current_a=10.0,
        vehicle_fresh=True,
    )
    base.update(overrides)
    return control.TrimInputs(**base)


def test_full_nominal_cycle(params_tri):
    """Field anchor 18/08 12:57: idle -> armed -> kick 2.0 -> release 0."""
    state = control.TrimState()

    # Constraint appears: arm, memorize the vehicle reference.
    state, write = control.trim_step(state, make_inputs(), 0.0, params_tri)
    assert state.phase == "armed"
    assert state.ref_vehicle_a == 10.0
    assert write is None

    # Held but not yet 180 s: stay armed, no write.
    state, write = control.trim_step(state, make_inputs(), 170.0, params_tri)
    assert state.phase == "armed"
    assert write is None

    # Sustained 180 s with every guard true: kick 2.0 A.
    state, write = control.trim_step(state, make_inputs(), 180.0, params_tri)
    assert state.phase == "kicking"
    assert write == 2.0

    # Bias readback now 2.0, traction not engaged yet: hold the kick.
    state, write = control.trim_step(
        state, make_inputs(current_bias_a=2.0), 190.0, params_tri
    )
    assert state.phase == "kicking"
    assert write is None

    # Traction engaged (vehicle ref - 1.2): conditional release to 0.
    state, write = control.trim_step(
        state,
        make_inputs(current_bias_a=2.0, vehicle_current_a=8.8),
        200.0,
        params_tri,
    )
    assert state.phase == "cooldown"
    assert write == 0.0

    # Cooldown holds 300 s, then back to idle.
    state, write = control.trim_step(state, make_inputs(), 400.0, params_tri)
    assert state.phase == "cooldown"
    assert write is None
    state, write = control.trim_step(state, make_inputs(), 500.0, params_tri)
    assert state.phase == "idle"
    assert write is None


def test_armed_aborts_if_headroom_recovers_before_sustain(params_tri):
    state, _ = control.trim_step(
        control.TrimState(), make_inputs(), 0.0, params_tri
    )
    assert state.phase == "armed"
    state, write = control.trim_step(
        state, make_inputs(worst_headroom_a=0.5), 60.0, params_tri
    )
    assert state.phase == "idle"
    assert write is None


def test_no_kick_when_published_outside_dead_band(params_tri):
    # Below L+0.05 and above L+0.8: never arms.
    for pub in (21.0, 21.9):
        state, write = control.trim_step(
            control.TrimState(),
            make_inputs(published_max_a=pub),
            0.0,
            params_tri,
        )
        assert state.phase == "idle"
        assert write is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"current_bias_a": 0.5},          # someone else plays the bias
        {"cap_a": 13.0},                  # manual cap active
        {"state": "escalating"},          # not regulating
        {"state": "failsafe"},
        {"vehicle_current_a": 6.0},       # vehicle <= 6.5 A
        {"distrust": True},               # distrust flag raised
    ],
)
def test_no_arming_when_guard_broken(params_tri, overrides):
    state, write = control.trim_step(
        control.TrimState(), make_inputs(**overrides), 0.0, params_tri
    )
    assert state.phase == "idle"
    assert write is None


def test_distrust_none_does_not_block(params_tri):
    # Detector unavailable (no vehicle-current mapped for it): arms anyway.
    state, write = control.trim_step(
        control.TrimState(), make_inputs(distrust=None), 0.0, params_tri
    )
    assert state.phase == "armed"
    assert write is None


def test_kick_timeout_returns_zero_after_25s(params_tri):
    state, _ = control.trim_step(
        control.TrimState(), make_inputs(), 0.0, params_tri
    )
    state, write = control.trim_step(state, make_inputs(), 180.0, params_tri)
    assert state.phase == "kicking" and write == 2.0
    # No engagement at all: timeout at 25 s, conditional release fires.
    state, write = control.trim_step(
        state, make_inputs(current_bias_a=2.0), 205.0, params_tri
    )
    assert state.phase == "cooldown"
    assert write == 0.0


def test_escalation_mid_kick_releases_only_own_kick(params_tri):
    # Firmware stage 2 engages mid-kick (state leaves regulating): the
    # machine abandons to cooldown AND releases its own 2.0 kick if the
    # bias is still exactly ours.
    state = control.TrimState("kicking", 180.0, 10.0)
    state, write = control.trim_step(
        state,
        make_inputs(state="escalating", current_bias_a=2.0),
        190.0,
        params_tri,
    )
    assert state.phase == "cooldown"
    assert write == 0.0
    # A foreign bias (a pause posted 16 during the kick) is NEVER
    # overwritten on the same exit.
    state = control.TrimState("kicking", 180.0, 10.0)
    state, write = control.trim_step(
        state,
        make_inputs(state="escalating", current_bias_a=16.0),
        190.0,
        params_tri,
    )
    assert state.phase == "cooldown"
    assert write is None


def test_conditional_release_skipped_if_bias_stolen(params_tri):
    # Shedding posted 16 A during the kick: the pause wins, no write,
    # cooldown anyway.
    state = control.TrimState("kicking", 180.0, 10.0)
    state, write = control.trim_step(
        state, make_inputs(current_bias_a=16.0), 190.0, params_tri
    )
    assert state.phase == "cooldown"
    assert write is None


def test_cooldown_blocks_rearm_then_expires(params_tri):
    state = control.TrimState("cooldown", 1000.0, 0.0)
    # Arming conditions all true: cooldown still blocks.
    state, write = control.trim_step(
        state, make_inputs(), 1100.0, params_tri
    )
    assert state.phase == "cooldown"
    assert write is None
    # Cooldown expired: back to idle, then re-arms on the next tick.
    state, write = control.trim_step(
        state, make_inputs(), 1300.0, params_tri
    )
    assert state.phase == "idle"
    assert write is None
    state, write = control.trim_step(
        state, make_inputs(), 1310.0, params_tri
    )
    assert state.phase == "armed"
    assert write is None


def test_disable_mid_kick_still_tries_conditional_release(params_tri):
    state = control.TrimState("kicking", 180.0, 10.0)
    state, write = control.trim_step(
        state,
        make_inputs(enabled=False, current_bias_a=2.0),
        190.0,
        params_tri,
    )
    assert state.phase == "idle"
    assert write == 0.0
    # Same abort with a stolen bias: no write, still back to idle.
    state = control.TrimState("kicking", 180.0, 10.0)
    state, write = control.trim_step(
        state,
        make_inputs(enabled=False, current_bias_a=16.0),
        190.0,
        params_tri,
    )
    assert state.phase == "idle"
    assert write is None
