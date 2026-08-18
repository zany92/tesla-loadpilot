# Incident runbook - the three failure modes you will actually meet

> Operator-facing, deliberately short. Every signature and remedy below was
> **lived and measured** on the reference installation (fw 26.18, 17 Aug
> 2026). Mechanism details and evidence: [`BEHAVIOR.md`](BEHAVIOR.md)
> (sections referenced per incident). Constants are calibration data - see
> BEHAVIOR §10 before trusting them on another firmware.

## 1. Distrust - the wallbox stops believing the meter

**What it is.** A latched state in which the wallbox ignores the emulated
meter entirely: no service modulation, no protection bites, stop orders
above L ignored for minutes. BEHAVIOR §4.

**Signature / detector.**
- Published value **sustained > L (≥ L + 0.45)** while the vehicle current
  does not move - the reference detector fires on published > 21.45 for
  120 s with vehicle > 9 A.
- Do **NOT** conclude distrust from "no reaction at published ≤ L": at L
  exactly the micro-law says HOLD (nominal). Only ignored orders strictly
  above L prove distrust (BEHAVIOR §4, requalification note).
- The charge-start gate keeps working during distrust (start refused at
  published > L − 5, accepted below): a correct refusal/acceptance proves
  nothing about trust either way.

**Common causes (avoid them).**
- A published value below the wallbox's own branch current (meter glitch).
- A vehicle ramp not echoed 1:1 in the published signal (saturated clamp,
  or an in-constraint effective gain < ~0.5 - the dilution floor,
  BEHAVIOR §3).

**Cure / recovery protocol (validated once, 17 Aug evening).**
1. Stop fighting it: release the bias, let the HA layer shed household
   equipment for protection (that path stays alive).
2. Wallbox power-cycle (breaker off/on). A power-cycle **alone** did not
   recover in our test - do not skip step 3.
3. **~2 h of honest signal**: publish the raw 1:1 measurement (shadow/RAW
   mode), no clamp, no bias.
4. First session restart **with the house calm**, so the opening ramp is
   fully echoed (a start under saturation can re-latch distrust at second
   one).
5. Proof of recovery = a stop order at L + 0.1 honoured in seconds.

## 2. Closed-loop yo-yo - the law obeys too well

**What it is.** Under a sustained constraint the co-variant loop can hunt:
vehicle cycling **±2.5 A, period ~20 s**; after ~7 excursions the excess
integral reaches the cut threshold and the contactor opens. Not distrust -
every order is being honoured. BEHAVIOR §8 (evening addendum) and §2.

**Settings.**
- Validated couple: **gain 0.5 / emax 1.0**. Keep it.
- **Never damp the yo-yo by lowering the gain**: below ~0.5 in-constraint
  gain is dilution and latches distrust in a single ramp - strictly worse
  than the yo-yo (BEHAVIOR §3, gain floor).

**Remedy.**
- Immediate: resolve the sustained constraint with the HA-layer **pause**
  (bias), don't let the loop hunt toward the integral cut.
- Structural: variant B of the co-variant law (asymmetric response /
  one-cycle-in-two nudges) - under design, see
  [`DESIGN_LOI_COVARIANTE.md`](../fr/DESIGN_LOI_COVARIANTE.md).

## 3. Charge start refused - usually not an incident

**What it is.** The vehicle is plugged, nothing starts (wallbox may blink).
If the published value is **> L − 5**, this is the wallbox's normal
admission check: insufficient available power. It is protection working,
not a fault. BEHAVIOR §4 (micro-law).

**Remedy.**
- **Wait.** The start is accepted as soon as the published value drops
  below L − 5 (house load ends, or the bias/pause is released).
- If the refusal persists with a visibly low published value, check the
  fail-safe is not armed (no healthy measure source → published =
  main_breaker → margin 0 by design; check the meter node and its "TIC
  Alive" sensor).
- After **several** interrupted sessions the vehicle silently gives up
  (`evse_state` 9, zero wallbox alerts): that one needs the app or an
  unplug/replug, see BEHAVIOR §5.


## Signature: "charging failed" right after a pause, house calm

Observed 18 Aug 2026. The app reports "charging failed" on a start
attempt, the house is calm, no distrust, but the published value sits
near the conductor limit with the contactor open: the pause bias (16 A)
is still applied, so the charger sees zero availability and refuses to
open the session.

Root cause on the pilot: the shedding logic posted its pause at the
exact moment the user paused from the app, so no charge was running;
the release path required either an active session or a long calm
window (anti-cycling "meal" hysteresis armed by two pauses in under
30 min), and nothing ever released the bias.

Remedy: write 0 to the bias number, then start the charge. Permanent
fix shipped on the pilot: an "empty pause" exemption in the release
logic (vehicle max current under 1 A over 2 min skips the long-calm
requirement; the room projections and the anti-yo-yo hold remain).
