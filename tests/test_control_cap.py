"""Charge-cap (B1) pure-policy tests.

Field anchors: the numeric cases marked "field anchor" replay values
really observed on the pilot site during the 18 Aug 2026 tuning session
(data/traces/2026-08-18_1317_manual_limit_tuning.log: a 13 A cap held at
13.2 A steady, equilibrium bias self-found).
"""

from __future__ import annotations

import loadpilot_control as control


def test_target_formula_pilot_case(params_tri):
    """Field anchor 18/08: cap 13 A, vehicle ~13.2 A, headroom 2.8 A.

    target = round0(worst_headroom + vehicle - cap) = round0(3.0) = 3.0:
    the equilibrium bias the loop self-found while holding 13.2 A.
    """
    target = control.compute_cap_bias_target(2.8, 13.2, 13.0, params_tri)
    assert target == 3.0
    # The equilibrium property: at the held point the target no longer
    # moves (same inputs, same target).
    assert (
        control.compute_cap_bias_target(2.8, 13.2, 13.0, params_tri)
        == target
    )


def test_target_clamped_0_and_bias_max(params_tri, params_mono):
    # Large positive raw values clamp at the per-install bias ceiling.
    assert (
        control.compute_cap_bias_target(30.0, 13.0, 1.0, params_tri) == 16.0
    )
    assert (
        control.compute_cap_bias_target(30.0, 13.0, 1.0, params_mono) == 32.0
    )
    # Negative raw values clamp at 0 (never a negative bias).
    assert (
        control.compute_cap_bias_target(-5.0, 2.0, 10.0, params_tri) == 0.0
    )


def test_target_formula_refuses_nan(params_tri):
    # A sensor publishing "nan" parses to float NaN: the pure policy
    # must refuse (None), never raise (A3 guard).
    nan = float("nan")
    assert (
        control.compute_cap_bias_target(nan, 13.2, 13.0, params_tri)
        is None
    )
    assert (
        control.compute_cap_bias_target(2.8, nan, 13.0, params_tri)
        is None
    )
    assert (
        control.compute_cap_bias_target(2.8, 13.2, nan, params_tri)
        is None
    )
    # decide_cap_write refuses a poisoned snapshot the same way.
    assert (
        control.decide_cap_write(
            3.0, nan, 3.0, 13.2, 13.0, 21.3, params_tri
        )
        is None
    )
    assert (
        control.decide_cap_write(
            3.0, 3.0, 3.0, nan, 13.0, 21.3, params_tri
        )
        is None
    )


def test_deadband_no_write_within_half_amp(params_tri):
    # |target - bias| = 0.4 < 0.5 and no kick condition: no write.
    assert (
        control.decide_cap_write(
            3.0, 3.4, 3.4, 13.0, 13.0, None, params_tri
        )
        is None
    )


def test_raise_is_immediate(params_tri):
    # Raising goes straight to the target (cap protection first).
    assert (
        control.decide_cap_write(
            6.0, 2.0, 2.0, 12.0, 13.0, None, params_tri
        )
        == 6.0
    )


def test_decay_limited_to_half_amp_per_tick(params_tri):
    # Lowering is throttled to 0.5 A per 10 s tick (anti limit-cycle).
    assert (
        control.decide_cap_write(
            2.0, 6.0, 6.0, 12.0, 13.0, None, params_tri
        )
        == 5.5
    )


def test_kick_when_vehicle_above_cap_and_published_in_band(params_tri):
    """Field anchor 18/08: published 21.3 (dead band), vehicle cap + 1.

    The pilot is deaf in the band: an exact equilibrium bias does not
    re-engage the traction; the loop writes target + 1.5 (bounded 16).
    """
    assert (
        control.decide_cap_write(
            4.0, 4.0, 4.0, 14.0, 13.0, 21.3, params_tri
        )
        == 5.5
    )
    # Bounded by the three-phase bias ceiling.
    assert (
        control.decide_cap_write(
            15.0, 15.0, 15.0, 16.0, 15.0, 21.3, params_tri
        )
        == 16.0
    )


def test_no_kick_outside_band(params_tri):
    # Published 21.0 (below L+0.05) and 21.9 (above L+0.8): no kick;
    # with bias == target there is nothing else to write either.
    assert (
        control.decide_cap_write(
            4.0, 4.0, 4.0, 14.0, 13.0, 21.0, params_tri
        )
        is None
    )
    assert (
        control.decide_cap_write(
            4.0, 4.0, 4.0, 14.0, 13.0, 21.9, params_tri
        )
        is None
    )


def test_no_kick_when_bias_already_above_target_margin(params_tri):
    # Bias 5.0 > target 4.0 + 0.5: the kick must not re-fire (it would
    # ratchet the bias up); the plain asymmetric decay applies instead.
    result = control.decide_cap_write(
        4.0, 5.0, 5.0, 14.0, 13.0, 21.3, params_tri
    )
    assert result == 4.5  # decay step, NOT target + 1.5


def test_foreign_bias_guard_blocks_write(params_tri):
    # A pause posted 16 A: the bias belongs to someone else, never fight.
    assert (
        control.decide_cap_write(
            3.0, 16.0, 2.0, 14.0, 13.0, 21.3, params_tri
        )
        is None
    )


def test_release_only_when_own_bias():
    # Release to 0 only when the current bias is ours.
    assert control.decide_cap_release(3.0, 3.0) == 0.0
    assert control.decide_cap_release(16.0, 3.0) is None
    # None at startup = prudence, no release write.
    assert control.decide_cap_release(3.0, None) is None


def test_written_values_are_half_amp_steps(params_tri):
    cases = [
        control.decide_cap_write(
            4.0, 4.0, 4.0, 14.0, 13.0, 21.3, params_tri
        ),
        control.decide_cap_write(
            6.0, 2.0, 2.0, 12.0, 13.0, None, params_tri
        ),
        control.decide_cap_write(
            2.0, 6.0, 6.0, 12.0, 13.0, None, params_tri
        ),
        control.decide_cap_write(
            15.0, 15.0, 15.0, 16.0, 15.0, 21.3, params_tri
        ),
    ]
    for value in cases:
        assert value is not None
        assert value == round(value * 2) / 2  # multiple of 0.5
        assert 0.0 <= value <= params_tri.bias_max_a
