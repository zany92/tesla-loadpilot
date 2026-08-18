"""Meter-distrust (B4) detector tests.

Field anchors: test_trip_at_sustained_saturation_with_vehicle replays
lesson 30 (17 Aug 2026 evening episodes); the 21.45 A regression test
encodes the 23:04 false alert (21.45 was INSIDE the dead band: a
sustained soft constraint, not deafness).
"""

from __future__ import annotations

import loadpilot_control as control


def run(params, samples, state=None):
    """Feed (t, published, vehicle) samples through distrust_step."""
    state = state or control.DistrustState()
    for t, pub, vehicle in samples:
        state = control.distrust_step(state, pub, vehicle, t, params)
    return state


def test_trip_at_sustained_saturation_with_vehicle(params_tri):
    """Field anchor 17/08: published 21.9 held 120 s, vehicle 15 A."""
    samples = [(t, 21.9, 15.0) for t in range(0, 121, 10)]
    state = run(params_tri, samples)
    assert state.active is True


def test_no_trip_below_threshold_2304_regression(params_tri):
    """The 23:04 false alert as a test: 21.45 sustained NEVER trips."""
    samples = [(t, 21.45, 15.0) for t in range(0, 301, 10)]
    state = run(params_tri, samples)
    assert state.active is False
    assert state.over_since_mono is None


def test_no_trip_without_vehicle_current(params_tri):
    # Vehicle current unavailable: state unchanged, inactive (the
    # detector is DISABLED without its source, never degraded).
    initial = control.DistrustState()
    state = run(
        params_tri, [(t, 21.9, None) for t in range(0, 301, 10)], initial
    )
    assert state == initial
    assert state.active is False


def test_no_trip_when_vehicle_below_9(params_tri):
    samples = [(t, 21.9, 8.0) for t in range(0, 301, 10)]
    state = run(params_tri, samples)
    assert state.active is False


def test_sustain_resets_on_dip(params_tri):
    # Saturated 0..90 s, dip at 100 s, saturated again 110..220 s: the
    # sustain restarted at 110, so 220 is still short of 120 s.
    samples = [(t, 21.9, 15.0) for t in range(0, 91, 10)]
    samples += [(100, 21.0, 15.0)]
    samples += [(t, 21.9, 15.0) for t in range(110, 221, 10)]
    state = run(params_tri, samples)
    assert state.active is False
    # Ten more seconds complete the new sustain: now it trips.
    state = control.distrust_step(state, 21.9, 15.0, 230.0, params_tri)
    assert state.active is True


def test_clear_on_dynamic_signal_60s(params_tri):
    # Signal dynamic again: published < L - 1 held 60 s.
    active = control.DistrustState(active=True)
    state = run(
        params_tri, [(t, 19.5, 15.0) for t in range(0, 61, 10)], active
    )
    assert state.active is False


def test_clear_on_vehicle_obeys_60s(params_tri):
    # The charger finally obeyed: vehicle < 7 A held 60 s (published
    # still saturated).
    active = control.DistrustState(active=True)
    state = run(
        params_tri, [(t, 21.9, 6.5) for t in range(0, 61, 10)], active
    )
    assert state.active is False


def test_clear_requires_sustain(params_tri):
    # 30 s of dynamic signal then re-saturation: stays active.
    active = control.DistrustState(active=True)
    samples = [(t, 19.5, 15.0) for t in range(0, 31, 10)]
    samples += [(t, 21.9, 15.0) for t in range(40, 101, 10)]
    state = run(params_tri, samples, active)
    assert state.active is True
    assert state.clear_since_mono is None


def test_thresholds_follow_max_conductor(params_mono):
    # Mono L = 32: trip threshold 32.85, clear threshold 31.
    below = run(
        params_mono, [(t, 32.8, 15.0) for t in range(0, 301, 10)]
    )
    assert below.active is False
    tripped = run(
        params_mono, [(t, 32.9, 15.0) for t in range(0, 121, 10)]
    )
    assert tripped.active is True
    # 31.5 is NOT below L - 1: does not clear.
    still = run(
        params_mono,
        [(t, 31.5, 15.0) for t in range(200, 301, 10)],
        tripped,
    )
    assert still.active is True
    cleared = run(
        params_mono,
        [(t, 30.9, 15.0) for t in range(400, 461, 10)],
        still,
    )
    assert cleared.active is False
