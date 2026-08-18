"""Golden tests: the law mirror replayed against the real pilot traces.

Each test replays a chosen segment of data/traces/*.log through
tests/law_model.py and checks that the simulated published value matches
the traced one. Each segment locks a hard-won measured constant: if
someone "improves" the law or a default, these tests break.

Replay methodology and its documented limits
--------------------------------------------
- Input reconstruction: the 18/08 traces carry L1 and L3 only; L2 was
  not traced. Worst phase is therefore max(L1, L3). On this installation
  L2 never drove the worst during the traced sessions (L1/L3 carry the
  house plus the vehicle phases), and the excellent fit below (residuals
  well under 0.1 A over hundreds of samples) confirms it a posteriori.
  The 17/08 variant B trace carries "pire=X%" directly (worst phase as a
  percentage of the 21.7 A contract), fed as a single phase.
- One-sample lag: the traced pub is the wallbox-side vitals value and
  lags the logger's measure sample by one line (3-4 s). The replay feeds
  sample i-1 to predict the pub of sample i. Measured on the 18/08
  deadband: exact to the dither with this lag, off by ~0.7 A without it.
- Pre-dither replay: the dither sign depends on millis()-since-boot
  parity, unknowable from wall-clock timestamps, so the replay runs the
  mirror with dither_a = 0 and the traced value keeps its +/-0.05. The
  dither logic itself is pinned exactly in test_law_model.py.
- Tolerance +/-0.15 A: the traced dither (+/-0.05); the law ticks at
  1 Hz but the logs sample every 3-4 s, so the measure the firmware
  actually used can differ slightly from the logged one (+/-0.05
  observed on steady plateaus); trace values are rounded to 0.01 A
  (pire to 0.1%, that is 0.022 A). Total ~0.12, rounded up to 0.15.
  Segments are STEADY on purpose: fast transients would alias the 3 s
  sampling and test nothing.
- Escalation stage 2 (escalation_kick_a = 0.9) was added to the shipped
  core on 18/08 AFTER these traces were recorded: the 13:16-13:20
  constraint hold exceeds 240 s with no kick visible in the trace
  (pub stays ~21.6, never 21.9). Replays that span 240 s of constraint
  therefore run with the kick disabled, and that firmware-version skew
  is documented as a known divergence, not masked by tolerance.

Segments deliberately EXCLUDED (untraced external levers)
---------------------------------------------------------
- 18/08 12:57:45-12:58:20 and every pause edge: the HA integration trim
  writes transient 2 A bias kicks and the pause lever ramps 0->16 by
  steps; the bias value is not in the trace, so o_raw cannot be
  reconstructed while it moves. (Segments where the bias is constant and
  known, 0 or 16, ARE replayed.)
- 17/08 22:56 trace, out-of-constraint stretches (23:16:33-23:17:31 and
  23:17:44-23:20:07): the traced pub sits systematically 0.22-0.26 A
  BELOW worst + 1.47 (n=63, while the in-constraint stretches of the
  same trace fit within 0.12). A constant input offset would also shift
  the in-constraint fit by half of it (gain 0.5): it does not. The
  divergence is therefore branch- or channel-dependent (that evening ran
  an experimental variant B build, and pire/pub come from different
  logging channels); unexplained, reported in the C10 report, excluded
  here rather than absorbed by a 0.3 A tolerance that would blunt every
  other lock.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from tests.law_model import LawInputs, LawParams, LawState, publish

TRACES = Path(__file__).resolve().parent.parent / "data" / "traces"

L = 21.0
CONTRACT = 21.7
OFFSET = 1.47            # L - budget = 21 - 21.7 * 0.9, locked by these tests
TOL = 0.15               # justified in the module docstring

# Stage-2 kick disabled (not present in the traced firmware, see above),
# dither_a = 0 (pre-dither replay, see the methodology note) and gain
# pinned to 0.5: every trace in data/traces was recorded on the 0.5-era
# firmware (the shipped default moved to 0.75 in 1.3.x; a future trace
# recorded on that firmware must pin 0.75 here).
PARAMS_TRACED_FW = LawParams(gain=0.5, escalation_kick_a=0.0, dither_a=0.0)


# ------------------------------------------------------------------
# Trace parsing
# ------------------------------------------------------------------
_RE_18 = re.compile(
    r"(\d+):(\d+):(\d+) car=([\d.]+) (True|False) pub=([\d.]+)"
    r" L1=([\d.?]+) L3=([\d.?]+) def=(\w+)")
_RE_17B = re.compile(
    r"(\d+):(\d+):(\d+) car=(True|False)\|([\d.]+) pub=([\d.]+)"
    r" pire=([\d.]+)%")


def _hms(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def load_trace_1808(name):
    """18/08 format: HH:MM:SS car=X True|False pub=Y L1=Z L3=W def=off.

    Returns rows with t (s), pub, phases (L1, L3), contactor. Lines with
    a '?' placeholder (logger hiccup) are skipped.
    """
    rows = []
    for line in (TRACES / name).read_text().splitlines():
        m = _RE_18.match(line)
        if not m or "?" in m.group(7) + m.group(8):
            continue
        rows.append({
            "t": _hms(m.group(1), m.group(2), m.group(3)),
            "ts": f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
                  f":{int(m.group(3)):02d}",
            "contactor": m.group(5) == "True",
            "pub": float(m.group(6)),
            "phases": (float(m.group(7)), float(m.group(8)), 0.0),
        })
    return rows


def load_trace_1708_variantB(name):
    """17/08 variant B format: car=True|X pub=Y pire=Z% (of 21.7 A)."""
    rows = []
    for line in (TRACES / name).read_text().splitlines():
        m = _RE_17B.match(line)
        if not m:
            continue
        rows.append({
            "t": _hms(m.group(1), m.group(2), m.group(3)),
            "ts": f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
                  f":{int(m.group(3)):02d}",
            "contactor": m.group(4) == "True",
            "pub": float(m.group(6)),
            "phases": (float(m.group(7)) * CONTRACT / 100.0, 0.0, 0.0),
        })
    return rows


def segment(rows, start_ts, end_ts, min_rows=4):
    sel = [r for r in rows if start_ts <= r["ts"] <= end_ts]
    assert len(sel) >= min_rows, (
        f"segment {start_ts}..{end_ts} not found in trace")
    return sel


def replay(rows, params=PARAMS_TRACED_FW, bias=0.0, mirror_ok=True):
    """Feed sample i-1, compare with the traced pub of sample i.

    Returns [(traced_row, simulated_pub)] for rows[1:].
    """
    state = LawState()
    out = []
    for prev, cur in zip(rows, rows[1:]):
        inputs = LawInputs(
            t_s=float(prev["t"]),
            currents_a=prev["phases"],
            bias_a=bias,
            contactor_closed=prev["contactor"],
            contactor_mirror_ok=mirror_ok,
        )
        sim, state = publish(inputs, state, params)
        out.append((cur, sim))
    return out


def assert_matches(pairs, tol=TOL):
    worst_res = 0.0
    for row, sim in pairs:
        res = row["pub"] - sim
        worst_res = max(worst_res, abs(res))
        assert abs(res) <= tol, (
            f"{row['ts']}: traced pub={row['pub']:.2f} vs simulated "
            f"{sim:.2f} (residual {res:+.2f} > {tol})")
    return worst_res


# ------------------------------------------------------------------
# 18/08 12:53, firmware 26.26.1 revalidation
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def rows_1808():
    return load_trace_1808("2026-08-18_1253_fw26261_revalidation.log")


class TestGolden20260818Revalidation:

    def test_1253_deadband_plateau_locks_budget_offset_and_gain(self, rows_1808):
        """18/08 12:53:27-12:57:04, the dead-band plateau.

        Vehicle pinned at 15.2 A, worst ~20.3 A, traced pub 21.30-21.50
        around 21.38. Locks the whole in-constraint chain at once:
        o_raw = worst + (L - budget) with L - budget = 1.47 (contract
        21.7 A x buffer 10%), then pub = L + gain x e with gain = 0.5
        (e ~0.77 -> pub ~21.38). Any drift of contract default, buffer
        default, L or gain moves this plateau and fails the test.
        51 consecutive samples, measured residual <= 0.10.
        (The C10 mission brief says "13:53-13:55": the trace shows this
        plateau at 12:53-12:57, brief timestamp off by one hour.)
        """
        pairs = replay(segment(rows_1808, "12:53:27", "12:57:04"))
        assert_matches(pairs)
        # The lock is meaningful only if the segment really sits in the
        # dead band: worst ~20.3 -> simulated pub in [21.2, 21.6].
        assert all(21.2 <= sim <= 21.6 for _, sim in pairs)

    def test_1253_startup_ramp_slope_one_zero_delay(self, rows_1808):
        """18/08 12:53:17 -> 12:53:21, out-of-constraint startup ramp.

        Locks the gain-1 zero-delay branch: worst 16.72 at 12:53:17 is
        published as 16.72 + 1.47 = 18.19 -> traced 18.14 (dither -0.05)
        on the very next sample. This is the plausibility rule (never
        dilute, never delay the vehicle component) made measurable.
        """
        pairs = replay(segment(rows_1808, "12:53:13", "12:53:21", min_rows=3))
        row, sim = pairs[-1]
        assert row["ts"] == "12:53:21"
        assert sim == pytest.approx(16.72 + OFFSET, abs=0.06)
        assert abs(row["pub"] - sim) <= TOL

    def test_1304_session_resume_slope_one_low_range(self, rows_1808):
        """18/08 13:04:04-13:04:22, autonomous resume after the floor stop.

        House ~5.5 A, contactor just re-closed, vehicle ramping from 0:
        traced pub 6.96-7.02 = worst + 1.47 exactly (slope 1 in the low
        range). KNOWN DIVERGENCE, replayed fail-open: the trace flags the
        contactor True while worst < 6 A, yet the traced pub shows NO R1
        floor (with the floor pub would be 7.47). Either the logger's
        contactor mirror led the firmware's own (mirror updates race the
        3 s logger during the resume) or the R1 branch did not trust the
        mirror at that instant. Replayed with contactor_mirror_ok=False
        (the firewall's own fail-open case) and reported in the C10
        report; do NOT tune vehicle_floor_a to make the floored variant
        fit, the floor is a measured physical bound.
        """
        pairs = replay(segment(rows_1808, "13:04:04", "13:04:22"),
                       mirror_ok=False)
        assert_matches(pairs)
        assert all(6.8 <= sim <= 7.2 for _, sim in pairs)

    def test_1316_midband_hold_locks_gain_no_stage2_in_traced_fw(self, rows_1808):
        """18/08 13:16:43-13:20:51, manual 13 A cap: hold at worst ~20.8.

        e ~1.27 -> exc = 0.635, mid-band: locks gain = 0.5 well away from
        both the 0.1 floor and the 1.0 ceiling (the dead-band plateau
        alone could be fitted by a wrong gain plus a wrong offset; this
        second operating point pins both). 52 samples, residual <= 0.09.
        Runs with escalation_kick_a = 0: the constraint here is sustained
        past 240 s and the traced pub NEVER kicks to 21.9, proving stage
        2 was not in that day's firmware (added to twc-core later on
        18/08). With the shipped default the replay would kick at
        13:20:39: that skew is the point of documenting it.
        """
        pairs = replay(segment(rows_1808, "13:16:43", "13:20:51"))
        assert_matches(pairs)
        assert all(21.45 <= sim <= 21.8 for _, sim in pairs)

    def test_1322_bias16_pause_locks_bias_additivity_and_emax_room(self, rows_1808):
        """18/08 13:22:59-13:27:20, full pause (bias 16 A), vehicle off.

        Two windows of the same pause, one constant bias = 16 A:
        - 13:22:59-13:27:20 (58 samples): house ~1.55 A, o_raw = 1.55 +
          16 + 1.47 ~19.0, BELOW L: the pause publishes house + bias at
          slope 1 (traced 18.9-19.2), never a static value.
        - 13:27:59-13:28:12 (steady mini-window): house 5.4 A, o_raw
          ~22.9, e ~1.87 -> exc = 0.935, just under emax = 1.0: traced
          pub 21.89-21.98. Locks that gain x e is NOT clipped at 0.94
          (emax >= 1.0) under the bias.
        The 16 A bias is not in the trace but is the known constant
        full-pause lever of that session (car=0.1, contactor open); a
        varying bias could not fit 60 samples within 0.13.
        The stretch 13:27:24-13:29:26 around the mini-window is EXCLUDED:
        a ~4 s cycling load flicks L3 between 5.4 and 2.0 faster than
        the 3 s logger, so the sample fed to the replay is not the one
        the 1 Hz firmware saw (aliasing, see the methodology note).
        """
        pairs = replay(segment(rows_1808, "13:22:59", "13:27:20"), bias=16.0)
        assert_matches(pairs)
        assert all(18.8 <= sim <= 19.5 for _, sim in pairs)  # slope 1
        pairs = replay(segment(rows_1808, "13:27:59", "13:28:12"), bias=16.0)
        assert_matches(pairs)
        assert all(21.8 <= sim <= 22.0 for _, sim in pairs)  # clamp 0.935


# ------------------------------------------------------------------
# 17/08 22:56, variant B closed-loop (pilot firmware kc868-a6-1)
# ------------------------------------------------------------------
class TestGolden20260817VariantB:
    @pytest.fixture(scope="class")
    def rows(self):
        return load_trace_1708_variantB(
            "2026-08-17_2256_variantB_closed_loop.log")

    def test_2256_constraint_entry_same_law_through_pire_channel(self, rows):
        """17/08 22:56:25-22:59:42, engagement of the variant B session.

        Vehicle ramps to 16 A, pire 92.5-95%: in constraint the variant B
        firmware is character for character the variant A law (the tail
        only exists out of constraint). Locks, on the OTHER firmware and
        the OTHER logging channel (pire% of 21.7), the same constants as
        the 18/08 plateau: offset 1.47 and gain 0.5. 61 samples,
        residual <= 0.12.
        """
        pairs = replay(segment(rows, "22:56:25", "22:59:42"))
        assert_matches(pairs)

    def test_2304_equilibrium_11min_locks_budget_as_convergence_point(
            self, rows):
        """17/08 23:04:35-23:15:07, the 9.1 A equilibrium held 11 min.

        The closed loop parks the vehicle at 9.1 A with the worst phase
        breathing around the budget boundary (19.53 A = 90% of 21.7) and
        the published value pinned in [21.05, 21.48]: budget = contract x
        (1 - buffer) IS the convergence point, and the nudge_min = 0.1
        floor is what holds it there (pub alternates around L + 0.1).
        Pointwise tolerance is 0.30 here, NOT 0.15: the input breathes
        across the branch boundary where the law is discontinuous by
        nudge_min (a 0.02 A input flicker moves pub by 0.1), and the 3 s
        log aliases the 1 Hz law; the mean residual over 197 samples is
        +0.02, so the widened pointwise band hides no systematic error
        (asserted separately).
        """
        pairs = replay(segment(rows, "23:04:35", "23:15:07"))
        worst_res = assert_matches(pairs, tol=0.30)
        residuals = [row["pub"] - sim for row, sim in pairs]
        mean_res = sum(residuals) / len(residuals)
        assert abs(mean_res) <= 0.08, f"systematic offset {mean_res:+.3f}"
        # The equilibrium itself: both trace and mirror hold the line at
        # the budget boundary for 11 minutes.
        assert all(21.0 <= row["pub"] <= 21.55 for row, _ in pairs)
        assert all(20.8 <= sim <= 21.55 for _, sim in pairs)
        assert len(pairs) >= 190
        assert worst_res <= 0.30
