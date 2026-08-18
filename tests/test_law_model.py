"""Unit tests of the publication-law mirror (tests/law_model.py).

Every branch of the C++ lambda is pinned here with hand-computed numbers,
default calibration (L = 21, contract 21.7, buffer 10% -> budget 19.53,
L - budget = 1.47, gain 0.5, emax 1.0, nudge 0.1, dither 0.05).
The golden tests against the real traces live in test_law_golden.py.
"""

from __future__ import annotations

import math

import pytest

from tests.law_model import LawInputs, LawParams, LawState, publish

# Unit expectations are anchored on the TRACED constants (gain 0.5 era,
# 17-18 Aug bench): pin the gain explicitly so the shipped default (0.75
# since 1.3.x) can evolve without rewriting the measured arithmetic below.
P = LawParams(gain=0.5)
L = P.conductor_limit_a          # 21.0
OFF = L - P.budget_a             # 1.47
D = P.dither_a                   # 0.05

# t_s = 0 gives dither +0.05 (int(t) % 2 == 0), t_s = 1 gives -0.05.
T_PLUS = 0.0
T_MINUS = 1.0


def tick(worst, t=T_PLUS, state=LawState(), **kw):
    """One tick with a single loaded phase, contactor closed by default."""
    inputs = LawInputs(t_s=t, currents_a=(worst, 0.0, 0.0), **kw)
    return publish(inputs, state, P)


def run(seq, params=P, state=LawState()):
    """Run [(t, LawInputs), ...] and return the list of published values."""
    outs = []
    for inputs in seq:
        pub, state = publish(inputs, state, params)
        outs.append(pub)
    return outs, state


# ------------------------------------------------------------------
# Out of constraint: shifted reality, gain 1, zero delay
# ------------------------------------------------------------------
class TestOutOfConstraint:
    def test_slope_one_shifted_reality(self):
        # pub = worst + (L - budget), slope exactly 1, at any level.
        for worst in (6.0, 10.0, 15.0, 19.0):
            pub, _ = tick(worst, t=T_PLUS)
            assert pub == pytest.approx(worst + OFF + D, abs=1e-9)

    def test_budget_boundary_is_at_worst_19_53(self):
        # e = 0 exactly at worst = budget: still the out-of-constraint branch.
        pub, st = tick(P.budget_a, t=T_PLUS)
        assert pub == pytest.approx(L + D, abs=1e-9)
        assert st.capped_since_s is None

    def test_bias_is_additive(self):
        # The pause lever shifts o_raw 1:1 (bias 16 = full pause).
        # Worst chosen above the R1 floor so only the bias is at play.
        pub, _ = tick(8.0, t=T_PLUS, bias_a=4.0)
        assert pub == pytest.approx(8.0 + 4.0 + OFF + D, abs=1e-9)

    def test_exit_resets_capped_timer(self):
        # 100 s in constraint, then out: capped_since must reset so the
        # next episode restarts its escalation clock from zero. The exit
        # step (20.5 -> 16.0, a 4.5 A gentle drop) passes R2 immediately.
        seq = [LawInputs(t_s=t, currents_a=(20.5, 0, 0)) for t in range(0, 100)]
        seq.append(LawInputs(t_s=100.0, currents_a=(16.0, 0, 0)))
        _, st = run(seq)
        assert st.capped_since_s is None


# ------------------------------------------------------------------
# In constraint: pub = L + clamp(gain * e, nudge_min, emax)
# ------------------------------------------------------------------
class TestInConstraint:
    def test_nudge_min_floor(self):
        # e = 0.07 -> gain*e = 0.035 < 0.1 -> floor at L + 0.1.
        pub, _ = tick(P.budget_a + 0.07, t=T_PLUS)
        assert pub == pytest.approx(L + P.nudge_min_a + D, abs=1e-9)

    def test_gain_half_midband(self):
        # e = 1.3 -> exc = 0.65, inside [0.1, 1.0]: the measured gain 0.5.
        pub, _ = tick(P.budget_a + 1.3, t=T_PLUS)
        assert pub == pytest.approx(L + 0.65 + D, abs=1e-9)

    def test_emax_ceiling(self):
        # e = 5 -> gain*e = 2.5 -> clamped at emax = 1.0.
        pub, _ = tick(P.budget_a + 5.0, t=T_PLUS)
        assert pub == pytest.approx(L + P.emax_a + D, abs=1e-9)

    def test_entry_arms_capped_timer(self):
        _, st = tick(P.budget_a + 0.5, t=7.0)
        assert st.capped_since_s == 7.0


# ------------------------------------------------------------------
# Escalation: stage 1 at timeout, stage 2 kick at 2x timeout
# ------------------------------------------------------------------
class TestEscalation:
    def _constant_constraint(self, worst, t_end, law_active=True):
        seq = [LawInputs(t_s=float(t), currents_a=(worst, 0, 0),
                         law_active=law_active)
               for t in range(0, int(t_end) + 1)]
        return run(seq)

    def test_stage1_flag_fires_at_timeout(self):
        # Just before 120 s: no flag. At 120 s: flag ON (floor published).
        _, st = self._constant_constraint(20.0, 119)
        assert st.escalation_active is False
        _, st = self._constant_constraint(20.0, 120)
        assert st.escalation_active is True

    def test_stage1_is_a_floor_not_a_step(self):
        # exc is already >= nudge_min by construction: stage 1 must not
        # change the published value, only guarantee it.
        outs, _ = self._constant_constraint(20.0, 125)
        # e = 0.47 -> exc = 0.235: same value before and after 120 s.
        assert outs[119] == pytest.approx(L + 0.235 - D, abs=1e-9)
        assert outs[120] == pytest.approx(L + 0.235 + D, abs=1e-9)

    def test_stage1_flag_stays_off_in_shadow_mode(self):
        # Contract 3.1: in RAW/OMBRE-MAX nothing acts on the wallbox.
        _, st = self._constant_constraint(20.0, 130, law_active=False)
        assert st.escalation_active is False

    def test_stage2_kick_at_double_timeout(self):
        # Shallow constraint e = 0.2 -> exc floor 0.1 -> pub L+0.1: the
        # dead-band case stage 2 exists for. At 240 s the kick raises the
        # published value to at least L + 0.9.
        outs, _ = self._constant_constraint(P.budget_a + 0.2, 240)
        assert outs[239] == pytest.approx(L + 0.1 - D, abs=1e-9)
        assert outs[240] == pytest.approx(L + P.escalation_kick_a + D, abs=1e-9)

    def test_stage2_one_kick_per_episode(self):
        # The kick pushes the vehicle down, the constraint breaks, capped
        # resets: re-entering starts a fresh 240 s clock (one kick per
        # episode, twc-core.yaml lines 92-94).
        seq = [LawInputs(t_s=float(t), currents_a=(P.budget_a + 0.2, 0, 0))
               for t in range(0, 241)]                     # kick at t=240
        # Descent step 19.73 -> 16.0 (gentle drop, passes R2 immediately).
        seq.append(LawInputs(t_s=241.0, currents_a=(16.0, 0, 0)))
        seq += [LawInputs(t_s=float(t), currents_a=(P.budget_a + 0.2, 0, 0))
                for t in range(242, 300)]                  # re-entry
        outs, st = run(seq)
        assert st.capped_since_s == 242.0
        # 58 s into the new episode: nudge floor again, no kick.
        assert abs(outs[-1] - (L + 0.1)) <= D + 1e-9


# ------------------------------------------------------------------
# Dither: the published value is NEVER a dead flat
# ------------------------------------------------------------------
class TestDither:
    def test_alternates_every_second_out_of_constraint(self):
        seq = [LawInputs(t_s=float(t), currents_a=(15.0, 0, 0))
               for t in range(0, 6)]
        outs, _ = run(seq)
        base = 15.0 + OFF
        assert outs == pytest.approx(
            [base + D, base - D, base + D, base - D, base + D, base - D])

    def test_no_two_equal_consecutive_values_anywhere(self):
        # Constant input, every branch: consecutive seconds always differ.
        for worst in (10.0, P.budget_a + 0.05, P.budget_a + 3.0):
            seq = [LawInputs(t_s=float(t), currents_a=(worst, 0, 0))
                   for t in range(0, 10)]
            outs, _ = run(seq)
            assert all(a != b for a, b in zip(outs, outs[1:]))


# ------------------------------------------------------------------
# Variant B: decaying tail on constraint exit (kc868 pilot firmware)
# ------------------------------------------------------------------
class TestVariantBTail:
    PB = LawParams(gain=0.5, tail_r0_a=1.5)

    def _exit_sequence(self, t_out_end, worst_out=17.0):
        # 10 s in constraint, then out at worst_out until t_out_end.
        seq = [LawInputs(t_s=float(t), currents_a=(20.5, 0, 0))
               for t in range(0, 10)]
        seq += [LawInputs(t_s=float(t), currents_a=(worst_out, 0, 0))
                for t in range(10, t_out_end)]
        return seq

    def test_tail_engages_on_exit_front(self):
        # First out-of-constraint tick: pub = min(o_raw + r0, L).
        outs, st = run(self._exit_sequence(11), params=self.PB)
        o_raw = 17.0 + OFF                       # 18.47
        assert outs[-1] == pytest.approx(min(o_raw + 1.5, L) + D, abs=1e-9)
        assert st.tail_since_s == 10.0

    def test_tail_decays_at_0p15_A_per_s(self):
        outs, _ = run(self._exit_sequence(16), params=self.PB)
        o_raw = 17.0 + OFF
        for k, t in enumerate(range(10, 16)):
            r = 1.5 - 0.15 * k
            expect = min(o_raw + r, L) + _dith(t)
            assert outs[10 + k] == pytest.approx(expect, abs=1e-9)

    def test_tail_capped_at_L(self):
        # Exit barely below the budget: o_raw + r0 > L -> capped at L
        # (the wallbox is not re-invited to ramp up immediately).
        seq = [LawInputs(t_s=0.0, currents_a=(20.5, 0, 0)),
               LawInputs(t_s=1.0, currents_a=(P.budget_a - 0.2, 0, 0))]
        outs, _ = run(seq, params=self.PB)
        assert outs[-1] == pytest.approx(L - D, abs=1e-9)

    def test_tail_expires_then_slope_one(self):
        # r0 / decay = 10 s of tail, then back to the pure v2 line.
        outs, st = run(self._exit_sequence(25), params=self.PB)
        assert st.tail_since_s is None
        assert outs[-1] == pytest.approx(17.0 + OFF + _dith(24), abs=1e-9)

    def test_tail_purged_on_contactor_open(self):
        seq = self._exit_sequence(12)
        seq.append(LawInputs(t_s=12.0, currents_a=(17.0, 0, 0),
                             contactor_closed=False))
        outs, st = run(seq, params=self.PB)
        assert st.tail_since_s is None
        assert outs[-1] == pytest.approx(17.0 + OFF + _dith(12), abs=1e-9)

    def test_r0_zero_is_exactly_variant_A(self):
        seq = self._exit_sequence(20)
        outs_a, _ = run(seq, params=LawParams(gain=0.5, tail_r0_a=0.0))
        # Variant A never deviates from the shifted reality after exit.
        for k, t in enumerate(range(10, 20)):
            assert outs_a[10 + k] == pytest.approx(
                17.0 + OFF + _dith(t), abs=1e-9)


# ------------------------------------------------------------------
# Firewall R1: physical floor with the contactor closed
# ------------------------------------------------------------------
class TestFirewallR1:
    def test_floor_applied_contactor_closed(self):
        # A 0.6 A reading with the contactor closed is physically
        # impossible (the measured glitch that latched distrust).
        pub, _ = tick(0.6, t=T_PLUS, contactor_closed=True)
        assert pub == pytest.approx(P.vehicle_floor_a + OFF + D, abs=1e-9)

    def test_fail_open_without_reliable_mirror(self):
        pub, _ = tick(0.6, t=T_PLUS, contactor_mirror_ok=False)
        assert pub == pytest.approx(0.6 + OFF + D, abs=1e-9)

    def test_no_floor_contactor_open(self):
        pub, _ = tick(0.6, t=T_PLUS, contactor_closed=False)
        assert pub == pytest.approx(0.6 + OFF + D, abs=1e-9)


# ------------------------------------------------------------------
# Firewall R2: sudden drops confirmed by 2 samples, rises pass
# ------------------------------------------------------------------
class TestFirewallR2:
    def _feed(self, values, **kw):
        seq = [LawInputs(t_s=float(t), currents_a=(v, 0.0, 0.0), **kw)
               for t, v in enumerate(values)]
        return run(seq)

    def test_sudden_drop_held_then_believed_on_2nd_sample(self):
        # 18 -> 10 is a 8 A drop (> 5): held one sample, believed on the
        # second consistent sample.
        outs, _ = self._feed([18.0, 10.0, 10.0])
        assert outs[1] == pytest.approx(18.0 + OFF - D, abs=1e-9)  # held
        assert outs[2] == pytest.approx(10.0 + OFF + D, abs=1e-9)  # believed

    def test_rise_passes_immediately(self):
        outs, _ = self._feed([10.0, 18.0])
        assert outs[1] == pytest.approx(18.0 + OFF - D, abs=1e-9)

    def test_gentle_drop_passes_immediately(self):
        # 18 -> 14 is a 4 A drop (<= 5): zero latency.
        outs, _ = self._feed([18.0, 14.0])
        assert outs[1] == pytest.approx(14.0 + OFF - D, abs=1e-9)

    def test_inconsistent_candidates_keep_holding(self):
        # Two sudden drops more than TOL=1 A apart: counter restarts,
        # the held value survives a third sample.
        outs, _ = self._feed([18.0, 10.0, 12.5])
        assert outs[2] == pytest.approx(18.0 + OFF + D, abs=1e-9)

    def test_nan_sample_holds_last_value(self):
        outs, _ = self._feed([18.0, math.nan])
        assert outs[1] == pytest.approx(18.0 + OFF - D, abs=1e-9)

    def test_drop_decides_per_phase_worst_follows(self):
        # Phase 1 glitches to 0.6 (drop 17.4 A): held. Phase 2 rises and
        # passes: the worst comes from the held phase 1 value.
        seq = [LawInputs(t_s=0.0, currents_a=(18.0, 9.0, 0.0)),
               LawInputs(t_s=1.0, currents_a=(0.6, 9.5, 0.0))]
        outs, _ = run(seq)
        assert outs[1] == pytest.approx(18.0 + OFF - D, abs=1e-9)


# ------------------------------------------------------------------
# Fail-safe, STOP, master switch
# ------------------------------------------------------------------
class TestSafetyBranches:
    def test_failsafe_publishes_main_breaker_dithered(self):
        pub0, st = publish(LawInputs(t_s=0.0, have_measure=False),
                           LawState(), P)
        pub1, _ = publish(LawInputs(t_s=1.0, have_measure=False), st, P)
        assert pub0 == pytest.approx(P.main_breaker_a + D, abs=1e-9)
        assert pub1 == pytest.approx(P.main_breaker_a - D, abs=1e-9)
        # A static fail-safe would latch wallbox distrust: must alternate.
        assert pub0 != pub1

    def test_failsafe_resets_capped_timer(self):
        _, st = tick(20.5, t=0.0)
        assert st.capped_since_s is not None
        _, st = publish(LawInputs(t_s=1.0, have_measure=False), st, P)
        assert st.capped_since_s is None

    def test_stop_floors_at_L_plus_nudge(self):
        # STOP with plenty of margin: max(o, L + 0.1), immediate.
        pub, _ = tick(10.0, t=T_PLUS, charge_stop=True)
        assert pub == pytest.approx(L + P.nudge_min_a + D, abs=1e-9)

    def test_stop_does_not_lower_a_deeper_constraint(self):
        pub, _ = tick(P.budget_a + 1.6, t=T_PLUS, charge_stop=True)
        assert pub == pytest.approx(L + 0.8 + D, abs=1e-9)

    def test_control_off_publishes_zero(self):
        pub, _ = tick(20.0, t=T_PLUS, control_enabled=False)
        assert pub == 0.0

    def test_pub_never_negative(self):
        pub, _ = tick(0.0, t=T_MINUS, contactor_closed=False,
                      bias_a=-30.0)   # absurd input: still floored at 0
        assert pub == 0.0


# ------------------------------------------------------------------
# Single phase (annex 11: structure invariant, numbers not transferred)
# ------------------------------------------------------------------
class TestSinglePhase:
    def test_worst_is_the_only_phase(self):
        p1 = LawParams(gain=0.5, phase_count=1)
        pub, _ = publish(LawInputs(t_s=0.0, currents_a=(12.0, 99.0, 99.0)),
                         LawState(), p1)
        # Phases 2 and 3 are forced to 0: they never drive the worst.
        assert pub == pytest.approx(12.0 + OFF + D, abs=1e-9)


def _dith(t):
    return D if (int(t) % 2 == 0) else -D
