> 🇫🇷 [Version française](../fr/TESTPLAN.md)

# Tesla LoadPilot - Pre-publication test plan

> QA property. Campaign to run BEFORE the first public tag `v1.0.0`.
> Three tracks: (A) non-regression on the pilot site (already in
> production), (B) from-scratch installation from the repo, (C) edge
> cases / failures. Each case states: preparation, action, expected,
> failure criterion.
> Safety reminder: any RS485/TIC intervention is done with the breaker
> off (see [`INSTALL.md`](INSTALL.md) §0). Never flash the charger node
> during a charge.

## 0. Campaign prerequisites

- [ ] `esphome config` then `esphome compile` pass on:
  - `examples/charger-kc868-a6.yaml` (with a local `secrets.yaml` and the
    packages consumed via LOCAL PATH, the tag not existing yet);
  - `examples/meter-teleinfo-olimex-poe.yaml`;
  - the `dsmr-p1` / `sml-de` / `ct-clamps` skeletons: **config only**
    (they are marked never-compiled; the goal is zero syntax/schema
    errors, not a functional validation).
- [ ] `python -m script.hassfest` (or the hassfest GitHub action) passes on
  `custom_components/loadpilot`.
- [ ] HACS validation (`hacs/action` action) passes.
- [ ] The QA secrets scan is green **including on the git history**
  (see QA_REPORT.md - blocker B1: rewrite the history and/or rotate the
  UDP key before any push).

## A. Pilot site (Loupiac production) - non-regression of the extraction

The site currently runs on `kc868-a6-1.yaml` (**PVi1-GRADE v2 co-variant**
block, flash #2 of 17 Aug evening). Objective: prove that
`twc-core.yaml` + `boards/kc868-a6.yaml` + `providers/teleinfo-fr.yaml`
reproduce EXACTLY the validated behaviour.

> **Annotation, 17 Aug evening**: several A* cases have already been
> PLAYED FOR REAL on the site firmware (the target behaviour is therefore
> measured, traces on file); see the record below the table. This does NOT
> exempt replaying these cases on the EXTRACTED core: the non-regression
> of the extraction is the very object of this track, and it remains to be
> done.

| # | Test | Expected | Fail if |
|---|---|---|---|
| A1 | Flash the meter node with `teleinfo-fr.yaml` (no charge) | UDP Age < 1100 ms on the charger side, sub-ampere currents consistent with the Linky (±0.1 A) | frame loss, cadence > 2 s |
| A2 | Flash the charger node with the extracted core (no charge) | Polling Active ON, Poll Interval 190-200 ms stable ≥ 1 h | polling gap > 2 s, retry storm |
| A3 | Verify the contractual entity_ids (§3.1/§3.2 CONTRACTS.md) in HA | the 15 charger entities + 6+1 meter entities exist under the exact names | any name deviation (dashboards/integration break) |
| A4 | `OMBRE-MAX` mode during a real charge ≥ 30 min | Shadow ≤ L at all times; published = raw measurement + bias | shadow > L, NaN, transient zero |
| A5 | Switch to `ACTIF-MAX` during charge, house loaded (oven/heat pump) | gentle modulation, plateaus held, recovery ~1 A/30 s, **zero contactor cycles** (lifetime counter before/after) | any contactor event, sustained oscillation |
| A6 | Load step (start heat pump/pool during charge) | absorbed without exceeding the contract beyond the buffer, worst phase respected | sustained overshoot > budget |
| A7 | Escalation: force zero headroom for 120 s (lower Contract Limit) | at 120 s: publication L+0.1, clean stop, `Escalation Active` ON, HA state `escalating` | stop before 120 s, no stop, contactor slam |
| A8 | Bias: `loadpilot.set_bias 6` during charge then `resume` | descent at 0.5 A/5 s, recovery at 1 A/5 s (Bias Applied follows as a ramp) | non-ramped jump during charge |
| A9 | Bias with contactor open (no vehicle) | target applied IMMEDIATELY (no "code 10" window) | ramp applied while idle |
| A10 | Kill-switch OFF for 10 min | constant 0 A publication, the wallbox falls back to factory behaviour (app slider), HA state `off` | the wallbox stays throttled |
| A11 | 24 h in `ACTIF-MAX` (normal use) | zero node reboots, zero contactor cycles, UDP Age p99 < 2 s | spontaneous reboot, watchdog |
| A12 | **Closed-loop yo-yo** (gain 0.5 / emax 1.0, SUSTAINED constraint: air conditioners kept on) | reproduce the signature measured 17 Aug 20:20: vehicle cycling ±2.5 A with ~20 s period; the HA pause (bias) must resolve it BEFORE the integral cut (~7 excursions) | contactor cut reached without the pause intervening |
| A13 | **Dead band at +0.5**: hold the published value at L+0.45..0.55 for ~90 s (fine bias, stable charge) | NO pilot reaction for ~70 s, NO cut (tolerant integral: 35 A·s lived at +0.5); cf. BEHAVIOR §2 (dead band) | frank descent or cut in the L+0.1..L+0.5 band |
| A14 | **Re-distrust by dilution** (do NOT replay in production - destructive case, bench/dedicated window only): gain 0.25 / emax 0.5 then vehicle start-up ramp | distrust latched IN ONE RAMP (car frozen through published > L+0.4, bias pause ignored) + the 21.45/120 s detector FIRING; back to 0.5/1.0 afterwards | the detector does not fire; or distrust also occurs at 0.5/1.0 |
| A15 | **Variant B validation** (placeholder - asymmetric law/one-cycle-in-two nudges, cf. `DESIGN_LOI_COVARIANTE.md` (French), in design) | under the same sustained constraint as A12: modulation held WITHOUT the ±2.5 A cycle or the integral cut; numeric criteria to be set at design time | - (to be defined with variant B) |

### Record of cases already played for real on the pilot site (site firmware, 17 Aug)

Traces (session scratchpad, to be archived with the campaign):
`test_pvi1grade.log` (11:21-11:35, v1), `test_soir_v3.log` (18:34-19:43,
full evening), `test_v2_covariant.log` and `test_v2_toutes_clims.log`
(19:30-19:39, v2). Narrative reference: `BEHAVIOR.md` §8 (+ the
"Evening validation" entry).

| # | Status as of 17 Aug evening | Measured result |
|---|---|---|
| A4 | ✅ played (equivalent) | OMBRE-MAX held ~1 h 30 during a real charge (cure window 16:30-18:00): published = honest raw, no anomaly |
| A5 | ✅ played | v1 11:21-11:35: gentle modulation 16 → 11.1, plateaus held, recovery ~1 A/30 s, contactor lifetime 470 unchanged (`test_pvi1grade.log`); replayed under v2 in the evening (±1 A balance dance at the frontier = NORMAL v2 regime, do not mistake it for distrust) |
| A6 | ✅ played (v2) | +4 air-conditioner load step 19:35+: CONTINUOUS descent 16 → 12+ A under a published slope at L+0.95 (~21.95), zero ceiling, zero cut (`test_v2_toutes_clims.log`) |
| A7 | ◐ partial | the L+0.1 safety net itself is validated with the wallbox trusting: 21.1 order executed in ~5 s (18:49:46, `test_soir_v3.log`); but the exact A7 procedure (lower Contract Limit, wait 120 s, check `Escalation Active`) remains to be played on the extracted core. Measured caveat: under distrust, the same order was ignored for 8 min (noon) |
| A8 | ◐ partial | bias 16 set/released in the real cascade 19:30-19:34; the IN-charge ramp (0.5/1 A per 5 s) validated on site in the preceding days, to be replayed via `loadpilot.set_bias` |
| A9 | ✅ played (v2) | bias release 16 → 0 INSTANT with contactor open (19:34:29) followed by the AUTONOMOUS session resume (cycle 478, no app): full cascade descent → pause → release → resume (`test_v2_toutes_clims.log`) |
| A12 | ✅ played (suffered) | 17 Aug ~20:20: 7 excursions ±2.5 A with ~20 s period then integral cut. ⚠️ Trace not archived (window between the end of `test_soir_v3.log`, 20:14, and the start of `test_loi_douce.log`, 20:31); signature documented in BEHAVIOR §8 (evening addendum); instrument it at replay |
| A13 | ✅ played (measured in passing) | dead band recorded during the lesson-31 episode: ~70 s at published ~L+0.5 without reaction, 35 A·s tolerated; trace `test_loi_douce.log` (20:31-20:35) |
| A14 | ✅ played (suffered) | 17 Aug 20:30-20:34: gain 0.25/emax 0.5 → 4:1 dilution → distrust latched in one ramp (car frozen at 12.1 through published 21.45 → 21.85, pause ignored), first true detection by the 21.45 detector; trace `test_loi_douce.log` |
| A15 | ⬜ to play | waiting on variant B (design in progress) |
| A1-A3, A10, A11 | ⬜ to play | depend on flashing the EXTRACTED core (never flashed to date) |

On a CLEAN HA instance (VM) + the two spare ESP32s if possible:

| # | Test | Expected |
|---|---|---|
| B1 | Follow the README quick start word for word (HACS custom repo + integration) | the integration installs, the config flow starts without reading any other doc |
| B2 | 3-step config flow, default values | entry created, `sensor.loadpilot_state` exists; state `failsafe` as long as the charger node is absent (safe truth) |
| B3 | Config flow with a custom node name (`ma-borne`) | the tracked entities follow the slug; document that the shipped dashboards assume the default names |
| B4 | Single-phase config flow (`phases: 1`) | only `headroom_l1`/L1 exist; no L2/L3 warnings in the integration (the ESPHome warnings on the mirror side are documented as benign) |
| B5 | Options flow: change limit 21.7 → 30 A, buffer 10 → 15 % | reload, knobs pushed to the node (node numbers updated), `budget_a` recomputed |
| B6 | Services: `set_bias` 3.3 A (invalid step) | clean validation error, no stack trace |
| B7 | `loadpilot.pause` / `resume` with no loaded entry | readable HA error "No LoadPilot config entry is loaded" |
| B8 | Import `dashboards/loadpilot-overview.yaml` and `loadpilot_card.yaml` | zero cards in error with the default node names (except the commented-out SoC card) |
| B9 | Follow INSTALL.md on the spare hardware (TIC + RS485) | the guide is sufficient; file every guide/reality deviation as an issue |
| B10 | Translations: run the config flow in FR then in EN | no `[UX_COPY.md pending]` visible in the final release; **verify the generated entity_ids on a FR instance** (pitfall: translated entity name → entity_id differing from the contract) |
| B11 | Repair skew: flash the node with `loadpilot_fw_version: "0.0.9"` | "version skew" issue raised with both versions, cleared after correction |

## C. Edge cases and failures (ARCHITECTURE.md D2 matrix)

| # | Scenario | Action | Expected | Failure criterion |
|---|---|---|---|---|
| C1 | UDP loss alone | unplug the meter node's Ethernet | at 5 s: Source `UDP` → `HA` (mirror), regulation continues with degraded latency | regulation gap, premature fail-safe |
| C2 | UDP + mirror loss (HA up, entities dead) | stop the meter node (the mirror entities go unavailable) | at ~5+10 s (debounce): `FAILSAFE`, main_breaker publication, charge blocked, Repair issue raised | charge continuing on a frozen measurement |
| C3 | HA loss alone, UDP fresh | stop Home Assistant during a regulated charge | regulation CONTINUES (Source `UDP`), no disturbance for ≥ 30 min | node reboot (reboot_timeout ≠ 0), spurious failover |
| C4 | HA + UDP loss (double failure) | HA stopped, then meter node cut | `FAILSAFE`: charge blocked, NEVER an uncontrolled charge | any charge > 0 A under double failure |
| C5 | Source return | reconnect the meter after C2/C4 | `UDP` resumes < 5 s, charge resumes without intervention, Repair issue cleared | manual recovery needed |
| C6 | **Frozen TIC, node alive** (hat unplugged, ESP32 up) | unplug the teleinfo hat for ~2 min | **SETTLED 17 Aug (QA M3, verdict B)**: without the fix, packet_transport re-emits the FROZEN sextuplet at 1 Hz and the HA mirror freezes from the same failure; no fallback triggers (proof by ESPHome source reading: `teleinfo` has no timeout, `send_data_(true)` re-emits everything). FIX IN PLACE: the provider's TIC watchdog (`tic_timeout_ms`, default 15 s) → NAN on the 6 quantities → cascade on the charger side. EXPECTED at test time: ≤ ~17 s after unplugging, "TIC Alive" OFF, HA mirrors unavailable, `FAILSAFE` (DITHERED main_breaker publication), charge blocked; automatic return < 5 s on replugging | the wallbox regulates on a frozen measurement; or a STATIC fail-safe publication (risk: distrust = self-neutralised fail-safe) |
| C7 | Charger node reboot during charge | cut/restore the KC868-A6's power during charge | at boot: main_breaker publication (charge blocked) until the first measurement, then resume; mode restored `ACTIF-MAX`; Contract Limit/Buffer restored from flash; Bias Target = 0 | boot at full headroom (uncontrolled charge), knobs lost |
| C8 | Meter node reboot | cut/restore the Olimex | C1 then C5 chained; rolling code accepted after reboot (no permanent rejection) | packets rejected in a loop after reboot |
| C9 | Full mains outage then return | cut everything for 2 min | both nodes come back on their own, regulation restored without HA (if HA is slower) | blocking boot order |
| C10 | Single-phase | single-phase bench (`phase_count: "1"`, provider B/C=0) | law degenerated onto L1 alone, L1 mirror sufficient, no fail-safe caused by B/C | fail-safe triggered by the absent phases |
| C11 | Vehicle: silent give-up | 3+ closely spaced charge interruptions | documented behaviour ([`INSTALL.md`](INSTALL.md) §7): the vehicle may give up; verify the doc is enough for diagnosis | undocumented / diagnosis impossible |
| C12 | Forged/replayed UDP packet (XXTEA + rolling code) | replay a captured packet | packet rejected (warning log), no influence on the publication | forged measurement accepted |
| C13 | Two UDP destinations (broadcast + unicast) | configure both | duplicate rejection documented (warning/s); verify no effect on freshness | freshness broken by the duplicates |
| C14 | Single-phase: CT registers read by the wallbox (extends C10; verdict on the symmetric-publication decision) | wallbox commissioned single-phase in Tesla One; observe in OMBRE, then brief differentiated publication (CT1 real / CT2-3 at 0, then symmetric) | identify which registers engage service and which trigger protection; the wallbox tolerates non-zero CT2/3 in single-phase | CT2/3 checked as ~0 by the firmware → activate plan B "CT1 only" (dedicated substitution, NOT the default) |
| C15 | Single-phase: `ct_total` = 3x the single value | symmetric publication in single-phase, watch registers 0xFC/0x90 | total accepted (as the 3x-worst-phase total already is in three-phase) | total flagged implausible → plan B |
| C16 | Single-phase: control-law constants | re-run the §B calibration on the single-phase bench | measure dead band above L, cut integral (~20 A.s in three-phase), service latency, recovery slope, L+0.1 micro-law, vehicle minimum (~6 A?) | constants diverge with no safe setting |
| C17 | Single-phase: plausibility scale | 32 A vehicle ramp (double the three-phase per-phase scale) | 1:1 echo accepted; 0.5 gain floor still valid; document distrust entries/exits and the recovery protocol | distrust latched by a legitimate 32 A ramp |
| C18 | Single-phase: real TIC mono | `teleinfo-fr-mono.yaml` on a real single-phase Linky | SINSTS (no index) + URMS1 labels confirmed at ~1 Hz; watchdog test (unplug the hat → FAILSAFE in ~20 s, B/C zeros go NAN with phase A); Tempo frames fit in 1024 bytes | labels differ / frames truncated / B/C zeros keep the feed fresh with a dead TIC |
| C19 | Single-phase: 32 A bias pause | `bias_max_a: "32"`, loadpilot.set_bias amps: 32 during a 32 A charge | full pause effective; ~160 s ramp acceptable; vehicle give-up behaviour (~3 disturbed sessions) identical to three-phase | pause never completes or vehicle errors |
| C20 | Single-phase: fail-safe and Meter Absent | meter absent / fail-safe on the single-phase bench | Tesla-documented 6 A fallback identical; boot main_breaker = charge blocked | uncontrolled charge under fallback |

Compile status (18 Aug): the CI now builds the single-phase charger and
meter configs for real; the packet_transport duplicated-sensor question
is SETTLED (compiles and links, run 32152173724). Bench behavior remains
untested.

Single-phase status: the whole C14-C20 campaign is OPEN - single-phase
support is THEORETICAL until it runs (no single-phase bench available at
design time, 18 Aug 2026).

## D. GO / NO-GO publication criteria

GO only if ALL of the following are true:

1. **Secrets**: git history rewritten without the Loupiac UDP key OR key
   rotated in production AND history rewritten (both recommended); secrets
   scan green on ALL published revisions.
2. A1-A11 green on the pilot site (including 24 h A11 without an event).
   A12-A14: replay on the extracted core recommended but not blocking
   (behaviours already measured on the site firmware, cf. record; A14
   destructive, bench only); A15 follows variant B, out of scope for the
   first tag.
3. C1-C9 green; C6: TIC watchdog fix implemented (done 17 Aug); the
   physical confirmation test remains (maintenance day).
4. B1-B8 green on a clean instance; B10 settled (entity_ids stable in FR).
5. hassfest + HACS validation green; `esphome config` green on the 2
   examples and the 4 providers.
6. Zero `[UX_COPY.md pending]` in translations/; zero `OWNER_TBD`
   (publication account settled); definitive LICENSE in place (PVi1's
   agreement obtained; otherwise the repo stays private, cf.
   LICENSE.placeholder).
7. Contract/UX divergences arbitrated (buffer 30 vs 50 %, limit 6-120 vs
   10-100 A, `paused` state, vehicle current sensor); see QA_REPORT.md.
8. README/INSTALL re-read after extraction: no remaining statement based
   on the old reference firmware (boot mode, Shadow sensors ×3,
   "Linky Source Active").

Immediate NO-GO if: a single C4/C6/C7 case fails (safety), or a secret
remains in the history.


## A15 record (17 Aug evening): variant B validated in closed loop

Yo-yo conditions reproduced (pump + electrolyser + air conditioner, house
breathing around the budget). Targets: Y1 excursions ≤ 2/5 min: zero
burst excursions; Y2 zero contactor cycles: held (482 constant);
Y3 oscillation ≤ ±1.5 A over ≥ 60 s: beaten (0 oscillation, 9.1 A
plateau held 11 min); Y4 zero distrust: held (the single alert = a
threshold false positive, detector recalibrated to L+0.85); Y5 resume:
clean exit 9.1 → 15.7 A in ~6 s. Trace:
`data/traces/2026-08-17_2256_variantB_closed_loop.log`. The decaying
tail remains active in production (2.0 A).


## Record A16 (18 Aug): firmware 26.26.1 revalidation and manual cap

26.26.1 update under supervision (WAN open 2 h, re-blocked within a
minute of the install). Verdicts: emulated meter survived
(commissioning intact, polling resumed at +1 min), behavior model
identical to 26.18 on every replayed axis (echo, dead band, pull,
pause, release, resume), real 115 percent stress absorbed, zero
distrust. Finding: the dead band is a hysteresis (engagement at about
L+0.85 from rest, tracking down to published = L once pulling, hold
measured for 95 s). Manual-cap loop field-tuned: a fast symmetric loop
produced an 11-16 A limit cycle with a 20 s period; the asymmetric one
(raise immediately, decay 0.5 A per 10 s tick, anti-hysteresis kick)
held 13.2 A steady against a 13 A target. Traces in `data/traces/`
(two files dated 18 Aug).
