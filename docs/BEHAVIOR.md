# TWC Gen 3 load management — measured behaviour model

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
> [`40_LOI_DE_COMMANDE.md`](40_LOI_DE_COMMANDE.md) — where the two differ,
> the French version (17 Aug 2026, definitive model) prevails.

The wallbox runs two independent mechanisms on the meter signal it polls
over Modbus (~190–200 ms cycle): a slow **service loop** that modulates the
pilot signal offered to the vehicle, and a fast **protection** that bites
and ultimately opens the contactor.

## 1. Service loop: a SYMMETRIC functional of the 3 published channels

The service loop does **not** watch the worst published phase:

- **MEASURED** — ≥ 20 discriminating cut episodes (differentiated per-phase
  publication, max > 21 A, mean < 21 A) with **no** prior service
  modulation whatsoever: the vehicle stays strictly constant until the
  protection cuts. ~6 cumulated minutes of `max > 21` with `mean < 21`
  across the 13–14 Aug episodes (e.g. 3 min at a constant 8.1 A with one
  channel published at ≈ 22 A continuously). Even a slow per-phase service
  (1–2 A/min) would have produced a visible drift: absent everywhere.
- **MEASURED** — service engagement was only ever observed **when the mean
  of the 3 published channels crosses the limit** (17 Aug 00:36–00:42: no
  reaction at mean 20.6–20.9 despite maxima 21.3–22.4; modulation from
  mean ≥ 21.3; recovery from mean < 20).
- **Residual ambiguity (not settled)** — mean vs min-of-published. All our
  differentiated episodes had min AND mean < 21 simultaneously; under
  symmetric publication the three coincide. **Without consequence under
  symmetric publication** (any symmetric functional engages at the same
  point). The closing academic test (2 channels ~22 / 1 channel ~18 under
  clamp) was designed but never run.
- **REPORTED (convergent, multiple fw 26.x sources)** — service dynamics far
  from the limit are **SLOW, in minutes**: an incremental "trajectory"
  around the configured limit, not a `setpoint = f(CT)` servo. Ramp-downs
  take minutes even at zero availability — hence the escalation technique
  ("publish +0.1 above the limit") to force a stop. PVi1 himself documents
  "ramps down very slowly (minutes)".
- **MEASURED** — near the limit the reaction is short: ~5–20 s between the
  mean crossing and the first pilot movement (19 s at the clamp in the
  17 Aug validation).
- **MEASURED (17 Aug)** — no fine ~1 A decrements on the way down; the
  **recovery** after clear margin returns is autonomous and paced at
  **~1 A / 30 s** (11 → 16 A in ~2 min).
- **REPORTED (external, important)** — nobody, PVi1 included, has
  demonstrated the exact service law. PVi1's "min per phase" is a
  self-reported inference from 1–2 lived episodes ("not officially
  confirmed by Tesla, just inferred from testing"), without published raw
  logs; our short episodes (43 s to 3 min) exclude it as the fast law. The
  timescale tension is unresolved — one more reason to publish
  symmetrically.

## 2. Protection: WORST PHASE — bite, then full cut

Independent of the service loop, the protection keys on the **maximum CT**
(`max(CT1, CT2, CT3)` vs the Max Conductor Limit, 21 A here):

- **Bite (MEASURED)** — a 2–6 A nibble of the pilot, triggered at
  max ≈ **21.3** (up to ~23), latency **≤ 5 s**, lasting 5–10 s, with
  **full recovery** as soon as the instantaneous excess stops — even while
  the offending channel stays > 21. A bite recovers; a service move holds
  its plateau: that is the distinguishing criterion.
- **Cut (MEASURED, very high confidence)** — contactor opens when the
  **worst-phase excess integral** reaches **~20–21 A·s** (measured ≈ 21 A·s;
  theory ~20), with the integral **decaying while the channel is back under
  the limit** — which explains long tolerated exposures at small excess
  (55 s tolerated at ~21.8 observed historically). ≥ 20 cuts with
  mean < 21 (down to mean 11–16) and **zero counter-example** requiring
  mean ≥ 21: the protection never averages.
- Shortest measured `max > 21` duration leading to a cut: **43 s**.

## 3. Plausibility: 1:1 correlation, never dilute

Firmware 26.18 checks that the meter signal is correlated with its own
output: while the car charges, the published current must **rise by the
same amount**.

- **REPORTED (PVi1, measured on his installation)** — diluting the vehicle
  component (phase averaging, EMA smoothing of the published signal) breaks
  the correlation → stop within seconds. A multiplicative gain without
  delay is accepted; a time delay is rejected.
- **MEASURED (consistent)** — every publication of ours in which the
  wallbox's own current came back 1:1 was accepted without any
  plausibility error; the yo-yos observed with our estimator variant are
  fully explained by the estimator itself (a lagging-Linky phantom), not by
  a wallbox rejection.
- Design rule: **the published signal must track the vehicle current 1:1 —
  never diluted, never delayed on that component.**

## 4. Session: the vehicle's memory and the silent give-up

Vehicle-side behaviours (Tesla), measured through the wallbox:

- **Amps memorised PER LOCATION (MEASURED)** — at every session restart the
  vehicle re-applies its memorised setpoint for the location (often 16 A),
  overwriting anything set during the previous session. A setting made
  *during* a stable charge, however, sticks.
- **Give-up after ~3 disturbed sessions (MEASURED, twice on 17 Aug)** —
  after roughly three charge starts interrupted within minutes, the vehicle
  **stops retrying**. Exact signature: `evse_state` → **9**, **zero alerts
  on the wallbox side**, charge-cycle counter frozen — indistinguishable
  from a normal end of charge as seen from the wallbox. **Restart requires
  the app** (or unplug/replug). Any pause-based architecture must plan for
  it: automatic restart after release if an API is available, otherwise an
  explicit notification — and anti-cycling so it never happens.

## 5. Measured dynamics (calibration constants)

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

## 6. The architectural consequence: clamped worst-phase symmetric publication

This is the project's landing point, and it follows mechanically from
§1–§3:

```
avail_p  = budget − bias − measure_p        (per phase, clamped to [0 ; L])
publish  = L − min(avail_1, avail_2, avail_3)     (identical on all 3 channels)
```

- **Symmetric service + worst-phase protection + unknown exact service law
  ⇒ publish the WORST PHASE IDENTICALLY on all 3 channels** — the only
  robust publication: min = mean = max by construction, so the service loop
  engages exactly at the true constraint **whatever the real functional
  is** (mean, min-of-published, or other).
- **Tripping is impossible by construction**: the published value is
  clamped ≤ L (21 A) — the worst-phase protection never sees an excess;
  bites and cuts disappear. A failure of this block is a non-start or soft
  hunting, never a contactor slam.
- **Deliberate stop = escalation**: since the wallbox ramps toward "zero
  availability" in minutes (§1) and can hold a residual indefinitely, after
  **120 s at zero availability** the block publishes **L + 0.1** on all 3
  channels to force a clean stop (PVi1's technique — REPORTED, then
  MEASURED on our installation).
- **No vehicle estimator**: the published measurement INCLUDES the
  wallbox's current → the published signal tracks the vehicle 1:1 and the
  plausibility check (§3) is satisfied by construction. No internal state
  other than the escalation timer (see the negative results, §8: every
  internal state added had created its own bug).
- **Safety buffer**: the offered resource is `budget = contract_limit ×
  (1 − b)` (b = 10 % by default) — the vehicle never exploits 100 % of the
  margin, in steady state or transients.

## 7. Validation (17 Aug 2026, 11:21–11:35, 3 s trace, block ACTIVE)

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
recovery — **the 26.18 wallbox CAN hold a plateau below the vehicle's
demand** when the published signal is bounded ≤ limit. Two real household
load steps absorbed without a single event.

## 8. Negative results (assumed, and published on purpose)

An earlier architecture — a "signal synthesizer" that decoupled the
vehicle's AC component through an estimator (gain α < 1 on transients) —
was fully designed, implemented, tested in the field over several nights,
and fixed six times before being **abandoned on 17 Aug 2026** in favour of
the memoryless block above. The full study and its post-mortem epilogue are
kept intact in [`60_ETUDE_SYNTHETISEUR.md`](60_ETUDE_SYNTHETISEUR.md)
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
  vehicle current "dead" — every plateau ≥ 10 s (the very goal of
  regulation) collapsed the published signal by −7.3 A at constant physical
  inputs. Proven by three independent clues, including one phase immunised
  by an accidental 13.0↔13.1 dither.
- **The earlier "firmware ceiling" verdict was re-scoped**: "the wallbox
  never holds a plateau below demand" is true **only for RAW self-referent
  publication (loop gain 1)** — a marginally stable discrete loop with
  multiplier −1. It was the signature of the loop gain, not a firmware
  ceiling. Corollary: beyond ~1 Hz, measurement freshness adds nothing
  (0.46 s was tested and changed nothing in RAW) — sub-second CT clamps are
  useless for this purpose.

To our knowledge this corpus — symmetric service / worst-phase protection /
1:1 plausibility, the six-failure table, the API deduplication trap, and
the "every internal state creates its own bug" law — is the most complete
characterisation of this wallbox firmware in existence. That is why the
failures are published alongside the result.

## 9. Scope and re-calibration warning

All constants above were measured against **TWC firmware 26.18** with a
Tesla vehicle on a three-phase 15 kVA French installation. The law's
*structure* (symmetric service, worst-phase protection, plausibility) is
expected to hold across 26.x (REPORTED, convergent community sources), but
the *constants* are calibration data. **If your wallbox firmware differs,
re-run the validation of §7 before trusting the escalation and buffer
settings** — and please report your findings (see `CONTRIBUTING.md`; the
TWC firmware version is mandatory in every report).

---

*Credits: the escalation technique, the field proof that a gain < 1 signal
modulates durably, and the register emulation prior art are from
[PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control);
the Neurio identity block is from LucaTNT's public gist. This project is
not affiliated with, endorsed by, or sponsored by Tesla, Inc.*
