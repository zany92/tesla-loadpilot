# TWC Gen 3 load management - measured behaviour model

> **This is the core asset of the project.** Nothing below is documented by
> Tesla: everything was measured on a real installation (wallbox firmware
> **26.18**, three-phase 15 kVA, Max Conductor Limit 21 A, Linky
> measurements at ~1 Hz, wallbox vitals sampled every 2–8 s, several hundred
> samples, **57 contactor-cut episodes re-analysed from the recorder** on
> 13–17 Aug 2026). These constants are properties of the wallbox firmware +
> vehicle pair: **re-calibrate if the TWC firmware changes.**
>
> Every statement is labelled **MEASURED** (our data), **INFERRED** (deduced,
> not directly tested) or **REPORTED** (external source). This is a condensed
> English translation of the French reference document,
> [`40_LOI_DE_COMMANDE.md`](../fr/40_LOI_DE_COMMANDE.md) - where the two differ,
> the French version (17 Aug 2026, definitive model) prevails.

The wallbox runs two independent mechanisms on the meter signal it polls
over Modbus (~190–200 ms cycle): a slow **service loop** that modulates the
pilot signal offered to the vehicle, and a fast **protection** that bites
and ultimately opens the contactor.

## 1. Service loop: a SYMMETRIC functional of the 3 published channels

The service loop does **not** watch the worst published phase:

- **MEASURED** - ≥ 20 discriminating cut episodes (differentiated per-phase
  publication, max > 21 A, mean < 21 A) with **no** prior service
  modulation whatsoever: the vehicle stays strictly constant until the
  protection cuts. ~6 cumulated minutes of `max > 21` with `mean < 21`
  across the 13–14 Aug episodes (e.g. 3 min at a constant 8.1 A with one
  channel published at ≈ 22 A continuously). Even a slow per-phase service
  (1–2 A/min) would have produced a visible drift: absent everywhere.
- **MEASURED** - service engagement was only ever observed **when the mean
  of the 3 published channels crosses the limit** (17 Aug 00:36–00:42: no
  reaction at mean 20.6–20.9 despite maxima 21.3–22.4; modulation from
  mean ≥ 21.3; recovery from mean < 20).
- **Residual ambiguity (not settled)** - mean vs min-of-published. All our
  differentiated episodes had min AND mean < 21 simultaneously; under
  symmetric publication the three coincide. **Without consequence under
  symmetric publication** (any symmetric functional engages at the same
  point). The closing academic test (2 channels ~22 / 1 channel ~18 under
  clamp) was designed but never run.
- **REPORTED (convergent, multiple fw 26.x sources)** - service dynamics far
  from the limit are **SLOW, in minutes**: an incremental "trajectory"
  around the configured limit, not a `setpoint = f(CT)` servo. Ramp-downs
  take minutes even at zero availability - hence the escalation technique
  ("publish +0.1 above the limit") to force a stop. PVi1 himself documents
  "ramps down very slowly (minutes)".
- **MEASURED** - near the limit the reaction is short: ~5–20 s between the
  mean crossing and the first pilot movement (19 s at the clamp in the
  17 Aug validation).
- **MEASURED (17 Aug)** - no fine ~1 A decrements on the way down; the
  **recovery** after clear margin returns is autonomous and paced at
  **~1 A / 30 s** (11 → 16 A in ~2 min).
- **REPORTED (external, important)** - nobody, PVi1 included, has
  demonstrated the exact service law. PVi1's "min per phase" is a
  self-reported inference from 1–2 lived episodes ("not officially
  confirmed by Tesla, just inferred from testing"), without published raw
  logs; our short episodes (43 s to 3 min) exclude it as the fast law. The
  timescale tension is unresolved - one more reason to publish
  symmetrically.

## 2. Protection: WORST PHASE - bite, then full cut

Independent of the service loop, the protection keys on the **maximum CT**
(`max(CT1, CT2, CT3)` vs the Max Conductor Limit, 21 A here):

- **Bite (MEASURED)** - a 2–6 A nibble of the pilot, triggered at
  max ≈ **21.3** (up to ~23), latency **≤ 5 s**, lasting 5–10 s, with
  **full recovery** as soon as the instantaneous excess stops - even while
  the offending channel stays > 21. A bite recovers; a service move holds
  its plateau: that is the distinguishing criterion.
- **Cut (MEASURED, very high confidence)** - contactor opens when the
  **worst-phase excess integral** reaches **~20–21 A·s** (measured ≈ 21 A·s;
  theory ~20), with the integral **decaying while the channel is back under
  the limit** - which explains long tolerated exposures at small excess
  (55 s tolerated at ~21.8 observed historically). ≥ 20 cuts with
  mean < 21 (down to mean 11–16) and **zero counter-example** requiring
  mean ≥ 21: the protection never averages.
- Shortest measured `max > 21` duration leading to a cut: **43 s**.
- **Dead band above L (MEASURED 17/08 evening)** - the wallbox tolerated
  **~70 s at published L + 0.45..0.55 with NO pilot reaction at all**, and
  frank traction (a clear, sustained descent) was only observed from
  **≥ ~L + 0.9**. The excess integral is likewise tolerant at +0.5:
  **35 A·s accumulated at that level without a cut**. Consequence for the
  model: the **~20 A·s integral budget of the cut holds for excesses
  ≥ ~1 A** - do not extrapolate it linearly into the L+0.1..L+0.5 zone,
  where both service and protection are far more forgiving than the
  micro-law's nominal −1 A/s at L + 0.1 suggests. Any escalation or
  co-variant gain tuning that lands the published value in that dead band
  is simply ignored.

## 3. Plausibility: 1:1 correlation, never dilute

Firmware 26.18 checks that the meter signal is correlated with its own
output: while the car charges, the published current must **rise by the
same amount**.

- **REPORTED (PVi1, measured on his installation)** - diluting the vehicle
  component (phase averaging, EMA smoothing of the published signal) breaks
  the correlation → stop within seconds. A multiplicative gain without
  delay is accepted; a time delay is rejected.
- **MEASURED (consistent)** - every publication of ours in which the
  wallbox's own current came back 1:1 was accepted without any
  plausibility error; the yo-yos observed with our estimator variant are
  fully explained by the estimator itself (a lagging-Linky phantom), not by
  a wallbox rejection.
- Design rule: **the published signal must track the vehicle current 1:1 -
  never diluted, never delayed on that component.**
- **The gain has a plausibility FLOOR (MEASURED 17/08 evening, 20:30)** -
  PVi1's never-dilute rule is now quantified on our installation: an
  anti-yo-yo softening of the co-variant law (gain 0.5 → 0.25, emax
  1.0 → 0.5) produced an **effective gain < ~0.5 on the charger component
  while in constraint** - a 4:1 dilution, the "averaging" error in
  disguise. One vehicle start-up ramp partially absorbed under the lowered
  ceiling was enough to **latch distrust in a single ramp** (published
  pinned 21.45 → 21.85 for 3 min while the car sat frozen at 12.1, bias-16
  pause ignored). Rule: **never lower the in-constraint gain below ~0.5**;
  treat yo-yo with the law's shape (variant B), never with the gain.

## 4. The distrust state: when the wallbox stops believing the meter

The plausibility check of §3 is not just a per-sample filter: when it is
violated, the wallbox enters a **latched distrust state** in which the
emulated meter is durably ignored. **MEASURED on our installation
(17 Aug 2026, two instrumented episodes)**:

- **Entry path #1 (MEASURED)** - a published value **below the wallbox's
  own branch current**: a one-off meter glitch published ~0.6 A on a phase
  for ~2 s while the wallbox itself was drawing 16 A. A real meter on the
  incomer can physically never read below the charger's own branch -
  maximally implausible; distrust appears to have latched right there.
- **Entry path #2 (MEASURED)** - a **vehicle ramp absorbed by the saturated
  clamp**: with the published value pinned at the limit (zero
  availability), the car ramped 8 → 16 A while the published signal echoed
  only +0.7 A - eight amps of the wallbox's own current invisible in the
  meter it polls. The 1:1 correlation check breaks; session-level distrust
  was immediate. Note the design tension: the very clamp that makes
  tripping impossible (§7) is what absorbs the ramp echo under prolonged
  saturation. (With trust intact this corner is unreachable - at zero
  availability the pilot is low, so the car cannot ramp; it only happened
  because distrust was already installed.)
- **Once installed, the wallbox ignores EVERYTHING (MEASURED)** - no
  service modulation at sustained clamp, no protection bites, no integral
  cut, and the **L + 0.1 escalation was ignored for 8 minutes** with the
  contactor closed: at 0.1 A over the limit for 480 s the ~20 A·s integral
  (§2) should have cut at ~200 s if the meter were still being honoured.
  The wallbox simply charges at its internal ceiling.
- **What does NOT clear it (all MEASURED)** - a charging-current
  renegotiation, a brand-new charging session, a reboot of the
  meter-emulating node (~1 min Modbus dropout), a ±0.05 A dither on the
  published value.
- **What DID clear it, apparently (MEASURED once)** - an overnight window
  during which the node published the **honest raw measurement for hours**
  (shadow mode). Next morning trust was back and the §8 validation ran
  flawlessly. **Working hypothesis (INFERRED)**: trust is a **score**,
  rebuilt by time spent on a plausible, 1:1-correlated signal - not an
  event flag. A controlled re-test (1–2 h of honest signal, then
  re-engage) is in progress, and a detector now timestamps every
  entry/exit of the state.
- **"Honoured at standstill, ignored in-session" CONFIRMED locally
  (MEASURED 17/08 evening)** - the community signature (§ Independent
  corroboration below) is now measured on our installation: during a
  session-level distrust episode, the **charge-start gate stayed
  meter-driven**. Start refusal at published > L − 5 and acceptance at
  published < L − 5 both worked exactly per the micro-law while every
  in-session order was being ignored. Distrust therefore disables the
  in-session regulation path only, not the admission check - which also
  means a start refusal is NEVER evidence that trust is back.
- Operating invariant that follows: **never publish a value below the
  wallbox's own branch current, and never let the published signal stop
  echoing the vehicle's ramps** - even under saturation.

### Recovery protocol (MEASURED, 17 Aug 2026 evening)

The controlled re-test announced above was run through the afternoon and
evening of 17 Aug. Outcome:

- **What restored trust (MEASURED once, attribution partially confounded)**
  - the combination of: a **wallbox power-cycle** (breaker off/on), then
  **~2 h of honest, 1:1-correlated published signal** (shadow mode), then
  a **first session start with the house calm** (so the vehicle's opening
  ramp is fully echoed, never absorbed by saturation). Hard evidence: the
  very same **L + 0.1 stop order that had been ignored for 8 minutes at
  noon was executed in ~5 s in the evening** (18:49:46, ~1 A/s descent),
  and the whole §8-evening validation then ran flawlessly. The
  power-cycle and the honest-signal cure sit in the same recovery window,
  so their individual contributions are **not yet separated** - a
  power-cycle alone with a short cure (< 1 h) was tested and did NOT
  recover (but the post-reboot session started under saturation, which may
  have re-latched distrust at that very second). To be refined at the next
  distrust episode.
- **Requalification of earlier "distrust" readings (MEASURED)** - several
  episodes previously read as "the wallbox is deaf" actually had the
  published value **at or below L (≤ 21.0)**. That is the nominal HOLD of
  the micro-law (published = L ⇔ hold the current plateau), not distrust:
  a clamp AT the limit cannot command a descent. **Only ignored orders
  strictly above L (≥ L + 0.1 sustained) prove distrust.** Any distrust
  detector must therefore trigger on `published > L` ignored, never on
  "no reaction at published ≤ L" - our first detector threshold (20.85)
  produced exactly that false positive and was recalibrated (21.45).

### Independent corroboration (REPORTED)

- **PVi1 (TMC, 9 Aug 2026, fw 26.18 - our exact version)** - arrives at
  the same theory independently: the TWC3 "actively checks whether the
  reported meter value actually correlates with the load it's causing
  itself"; a static-looking value → detected and ignored, regulation
  honoured before a session but ignored during it. His fix matches ours:
  the CTs must **measure a branch that includes the wallbox itself** so
  the reported value is physically correlated with the car's ramps. Same
  post: the installer lock on meter commissioning introduced around
  fw 26.2.0 is bypassable on 26.18 via a generic Tesla account (app →
  More → "Tesla device settings"), and the regulated floor is 5 A.
- **Klangen82, `tesla-wall-connector-control` issue #1 (5 May 2026)** - a
  **permissive** +1 A step (10 → 11 A) of the emulated value during an
  active session: the TWC "often enters a 'fail-safe' mode before it
  starts ramping up to the new value". Distrust can therefore latch on any
  discontinuity uncorrelated with the wallbox's behaviour, not only on
  restrictive or impossible values.
- **Klangen82 issue #7 (mitf559, brand-new Gen 3; and YLAG on fw 25.x)** -
  the full signature: meter honoured at standstill, ignored in-session,
  "the amps will ramp up to the max" a few seconds after charging starts.
  YLAG reports the same on **fw 25.x**.
- **Interpretation divergence (flagged, not settled)** - the community
  (Klangen82's README disclaimer of 20 Apr 2026, echoed elsewhere)
  attributes this to a **"fw 26.2+ lock"** that "ignores external current
  limits during active charging". The wider body of evidence - fw 25.x
  affected (YLAG), 26.x installations working elsewhere (FreekSchreurs:
  "Firmware version 26.x works without problem"), and our fully
  controllable 26.18 - points instead to a **recoverable behavioural
  state present since at least 25.x**, triggered by publication style
  rather than gated by firmware version. Neither reading is proven.

### What Tesla documents officially (REPORTED - DPM application note, rev 1.2, Jan 2024)

- On **loss of meter connection** the documented fallback is a **6 A
  maximum output** ("so as not to overload the system") - a degraded
  mode, not a stop.
- **No "meter ignored" / distrust state is documented anywhere** in the
  application note: the behaviour described in this section is an
  undocumented layer.
- Max Conductor Limit = **80 % of the panel rating**; **one single Wall
  Connector per meter**; requires **fw ≥ 23.8.1**. (The 5 A regulated
  floor above is PVi1's report on 26.18, not an app-note figure - note it
  differs from the documented 6 A loss-of-meter fallback.)

## 5. Session: the vehicle's memory and the silent give-up

Vehicle-side behaviours (Tesla), measured through the wallbox:

- **Amps memorised PER LOCATION (MEASURED)** - at every session restart the
  vehicle re-applies its memorised setpoint for the location (often 16 A),
  overwriting anything set during the previous session. A setting made
  *during* a stable charge, however, sticks.
- **Give-up after ~3 disturbed sessions (MEASURED, twice on 17 Aug)** -
  after roughly three charge starts interrupted within minutes, the vehicle
  **stops retrying**. Exact signature: `evse_state` → **9**, **zero alerts
  on the wallbox side**, charge-cycle counter frozen - indistinguishable
  from a normal end of charge as seen from the wallbox. **Restart requires
  the app** (or unplug/replug). Any pause-based architecture must plan for
  it: automatic restart after release if an API is available, otherwise an
  explicit notification - and anti-cycling so it never happens.

## 6. Measured dynamics (calibration constants)

| Quantity | Measured value |
|---|---|
| Bite: latency after worst-phase excess | ≤ 5 s |
| Bite: amplitude / duration | 2–6 A / 5–10 s, full recovery |
| Cut: worst-phase excess integral | ~20–21 A·s (decays below the limit) |
| Service: latency near the limit (mean ≥ 21) | ~5–20 s |
| Service: autonomous recovery at clear margin | ~1 A / 30 s |
| Service: dynamics far from the limit | minutes (REPORTED, convergent) |
| Ramp-down at a cut | ~1 A/s |
| Ramp-up after re-authorisation | ~0.65 A/s |
| Contactor-open window within a cycle | ~15–20 s |
| Sustained bang-bang period (RAW publication, loop gain 1) | ~55 s |
| Vehicle minimum (Tesla, 3-phase AC) | ~6 A |
| `evse_state` during a cycle stop / vehicle give-up | 11 → 7 / 11 → 9 |
| Effect of one ampere of charge (3-phase) | ~230 VA per phase per ampere |
| Wallbox Modbus poll cadence | ~190–200 ms |
| Modbus retry timeout (reply deadline) | ~66 ms |
| Vehicle response to a J1772 setpoint change | ~5 s |

## 7. The architectural consequence: clamped worst-phase symmetric publication

> **Superseded on 17 Aug 2026 evening (flash #2)**: the hard clamp below
> was replaced by the **co-variant law** (`DESIGN_LOI_COVARIANTE.md`,
> variant A) after the clamp itself was shown to manufacture the distrust
> state of §4 (a saturated flat value absorbs the vehicle's ramp echo).
> The co-variant law keeps everything in this section except the flat:
> out of constraint it publishes the shifted reality unchanged; in
> constraint it publishes `L + clamp(gain × excess, 0.1, emax)` with a
> permanent ±0.05 dither - the published value is never dead, and the
> level above L is itself the measured slow-down signal (L+0.1 → ~−1 A/s;
> L exactly → HOLD; below L → recovery). Trip goes from "impossible by
> construction" to "improbable by dynamics" (~20 A·s integral budget vs
> seconds of exposure). Measured validation: §8, evening entry.

This was the project's first landing point, and it follows mechanically
from §1–§4:

```
avail_p  = budget − bias − measure_p        (per phase, clamped to [0 ; L])
publish  = L − min(avail_1, avail_2, avail_3)     (identical on all 3 channels)
```

- **Symmetric service + worst-phase protection + unknown exact service law
  ⇒ publish the WORST PHASE IDENTICALLY on all 3 channels** - the only
  robust publication: min = mean = max by construction, so the service loop
  engages exactly at the true constraint **whatever the real functional
  is** (mean, min-of-published, or other).
- **Tripping is impossible by construction**: the published value is
  clamped ≤ L (21 A) - the worst-phase protection never sees an excess;
  bites and cuts disappear. A failure of this block is a non-start or soft
  hunting, never a contactor slam.
- **Deliberate stop = escalation**: since the wallbox ramps toward "zero
  availability" in minutes (§1) and can hold a residual indefinitely, after
  **120 s at zero availability** the block publishes **L + 0.1** on all 3
  channels to force a clean stop (PVi1's technique - REPORTED, then
  MEASURED on our installation). Caveat: the escalation is only honoured
  while the meter is trusted - in the distrust state (§4) it was ignored
  for 8 measured minutes.
- **No vehicle estimator**: the published measurement INCLUDES the
  wallbox's current → the published signal tracks the vehicle 1:1 and the
  plausibility check (§3) is satisfied by construction. No internal state
  other than the escalation timer (see the negative results, §9: every
  internal state added had created its own bug).
- **Safety buffer**: the offered resource is `budget = contract_limit ×
  (1 − b)` (b = 10 % by default) - the vehicle never exploits 100 % of the
  margin, in steady state or transients.

## 8. Validation (17 Aug 2026, 11:21–11:35, 3 s trace, block ACTIVE)

Contactor-cycle baseline = 470. Vehicle at 16 A, live household (A/C, pool
pump). **MEASURED**:

| Time | Event | Published (sym.) | Vehicle |
|---|---|---|---|
| 11:21–11:23 | steady state | 18.1–18.3 | 16.0–16.1 stable |
| 11:23:42 | A/C starts → **clamp at exactly 21.0** | 21.0 | 16.0 |
| 11:24:01 | first gentle modulation (**19 s** after the clamp) | 20.3 | 16.0 → **15.1** |
| 11:26:03 | next plateau (published ~20.1 sustained) | 20.1 | → **13.1** |
| 11:27:48–11:28:03 | pool pump (published 20.8–20.9) | 20.9 | → **11.1** |
| 11:28–11:30 | **plateau 11.1 HELD ~2 min, zero hunting** | ~19.1 | 11.1 |
| 11:29:34–11:30:00 | house load ends, published drops 15.4 → 13.6 | 13.6 | 11.1 |
| 11:30:03 → 11:32:03 | **autonomous recovery ~1 A / 30 s** | 13.6 → 18.4 | 12.1 → … → **16.1** |
| 11:32–11:35 | steady state regained | 18.1–18.4 | ~16.0 |

Outcome: contactor cycles **470, unchanged** (zero cuts), **zero bites**,
`evse_state` = 11 throughout, gentle downward modulation AND autonomous
recovery - **the 26.18 wallbox CAN hold a plateau below the vehicle's
demand** when the published signal is bounded ≤ limit. Two real household
load steps absorbed without a single event.

### Evening validation - co-variant law, flash #2 (17 Aug 2026, 19:06–19:43, MEASURED)

The v2 co-variant law (§7 banner) was flashed at 19:06 and validated live
the same evening, with trust freshly restored (recovery protocol, §4).
All entries below are **MEASURED** (3 s traces `test_soir_v3.log`,
`test_v2_covariant.log`, `test_v2_toutes_clims.log`):

- **The "balance dance" is the NORMAL v2 regime - do not mistake it for
  distrust.** Under co-variant publication, at the budget frontier the
  vehicle holds **±1 A around the exact equilibrium** (`budget − house`,
  15–16 A observed) while the published value oscillates around L
  (20.9–21.4 observed). This is the law working: each crossing above L is
  a real slow-down nudge, each return below L is a real release. Our
  first distrust detector (threshold 20.85) flagged this dance as
  distrust - false positive; the recalibrated criterion is *ignored*
  orders above L (21.45 / 120 s / vehicle > 9 A).
- **Continuous descent under sustained constraint (the v1 clamp's blind
  spot, fixed).** A +4 air-conditioner load step drove the vehicle
  **16 → 12+ A in one continuous descent** under a published slope at
  L + 0.95 (~21.95 observed) - no plateau at 15 A, no frozen published
  value, no distrust entry. The wallbox followed the compressed excess
  signal exactly as the micro-law predicts.
- **Full cascade demonstrated end-to-end without a human**: vehicle
  descent under the law → still insufficient → HA-layer pause posed at
  45 s (bias 16: the vehicle was stopped BEFORE any household equipment
  was shed - "vehicle first" executed to the letter) → load step ends →
  bias released (16 → 0 instantly, contactor open rule) → **AUTONOMOUS
  session resume at the second of the release** (contactor cycle 478, no
  app interaction). The vehicle's silent give-up (§5) did not trigger.
- Wallbox events over the whole evening: the only contactor cycles are
  the expected session stop/start of the cascade - zero protection cuts,
  zero bites, zero distrust entries.

### Later that evening - the closed-loop yo-yo (MEASURED 17/08, ~20:20)

The balance dance above is benign, but under a **sustained** constraint the
v2 law at gain 0.5 / emax 1.0 can degenerate into a genuine closed-loop
limit cycle:

- **Signature (MEASURED)** - vehicle current cycling **±2.5 A** with a
  period of **~20 s**, the published value crossing L on every excursion;
  after **7 excursions** the worst-phase excess integral (§2) accumulated
  to the cut threshold and the **contactor opened**. This is not distrust
  (every order was honoured - it is the loop obeying too well) and not the
  ~55 s RAW bang-bang of §6: it is a faster, law-shaped oscillation proper
  to the co-variant feedback at that gain couple.
- **What NOT to do (MEASURED, lesson learned the same evening)** - lowering
  the gain to damp it creates the dilution of §3 (gain floor) and latches
  distrust: strictly worse. Gain 0.5 / emax 1.0 stays the validated couple.
- **Status** - the fix under design is **variant B** of the co-variant law
  (asymmetric response / one-cycle-in-two nudges, cf.
  `DESIGN_LOI_COVARIANTE.md`), which reshapes the descent signal instead of
  weakening it. Until it lands, a sustained-constraint episode should be
  resolved by the HA-layer pause (bias), not by letting the loop hunt.

## 9. Negative results (assumed, and published on purpose)

An earlier architecture - a "signal synthesizer" that decoupled the
vehicle's AC component through an estimator (gain α < 1 on transients) -
was fully designed, implemented, tested in the field over several nights,
and fixed six times before being **abandoned on 17 Aug 2026** in favour of
the memoryless block above. The full study and its post-mortem epilogue are
kept intact in [`60_ETUDE_SYNTHETISEUR.md`](../fr/60_ETUDE_SYNTHETISEUR.md)
(French). Highlights:

- **Structural failure pattern (MEASURED)**: each fix added internal state,
  and each subsequent failure was a transient mode of the state added by
  the previous fix. Final tally: ~20 dynamic control globals in the last
  synthesizer variant, versus **one** (the escalation timer) in the
  memoryless block that won.
- **The root cause was the estimator itself**: separating "house" from
  "vehicle" using vitals ~2 s late, against a wallbox deciding every
  ~200 ms and a vehicle ramping at ~1 A/s, generates a whole class of
  staleness/freeze/purge/anchor bugs. A design with no estimator
  structurally has none of them.
- **A forensic gem (MEASURED to 0.1 A)**: ESPHome's native API
  **deduplicates identical sensor states** before transmission, so a
  Home Assistant heartbeat with `force_update: true` never reaches the
  node. A 10 s staleness guard therefore declared a perfectly *stable*
  vehicle current "dead" - every plateau ≥ 10 s (the very goal of
  regulation) collapsed the published signal by −7.3 A at constant physical
  inputs. Proven by three independent clues, including one phase immunised
  by an accidental 13.0↔13.1 dither.
- **The earlier "firmware ceiling" verdict was re-scoped**: "the wallbox
  never holds a plateau below demand" is true **only for RAW self-referent
  publication (loop gain 1)** - a marginally stable discrete loop with
  multiplier −1. It was the signature of the loop gain, not a firmware
  ceiling. Corollary: beyond ~1 Hz, measurement freshness adds nothing
  (0.46 s was tested and changed nothing in RAW) - sub-second CT clamps are
  useless for this purpose.

To our knowledge this corpus - symmetric service / worst-phase protection /
1:1 plausibility, the six-failure table, the API deduplication trap, and
the "every internal state creates its own bug" law - is the most complete
characterisation of this wallbox firmware in existence. That is why the
failures are published alongside the result.

## 10. Scope and re-calibration warning

All constants above were measured against **TWC firmware 26.18** with a
Tesla vehicle on a three-phase 15 kVA French installation. The law's
*structure* (symmetric service, worst-phase protection, plausibility) is
expected to hold across 26.x (REPORTED, convergent community sources), but
the *constants* are calibration data. **If your wallbox firmware differs,
re-run the validation of §8 before trusting the escalation and buffer
settings** - and please report your findings (see `CONTRIBUTING.md`; the
TWC firmware version is mandatory in every report).

---

*Credits: the escalation technique, the field proof that a gain < 1 signal
modulates durably, and the register emulation prior art are from
[PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control);
the Neurio identity block is from LucaTNT's public gist. This project is
not affiliated with, endorsed by, or sponsored by Tesla, Inc.*


### Variant B closed-loop validation (17 Aug, 22:56-23:15, MEASURED)

With the decaying-tail law active (tail 2.0 A, decay 0.15 A/s) under the
exact conditions that produced the +/-2.5 A limit cycle: pool pump +
electrolyser + one AC, house breathing around the budget. Results: trust
verdict positive (descent 16 to 9.1 A at ~1 A/s within seconds of the
published entering the pull zone), then **11 minutes pinned at the exact
equilibrium (9.1 A) with zero oscillation** while the house dipped and
rose, zero contactor cycles, and a clean exit (9.1 to 15.7 A in ~6 s once
the constraint fell). The one alert fired was a detector false positive
(threshold sat inside the dead band; recalibrated to L+0.85). Raw trace:
`data/traces/2026-08-17_2256_variantB_closed_loop.log`.
