# Tesla LoadPilot - AI knowledge base

> Single self-contained condensation of the project's knowledge for an AI
> assistant (or a hurried human). Everything here is sourced from the repo
> documents; where a number matters, its validation status is given.
> Source of truth on any conflict: `docs/en/BEHAVIOR.md` and
> `docs/fr/40_LOI_DE_COMMANDE.md` (French version prevails), then
> `ARCHITECTURE.md` and `CONTRACTS.md` (frozen). This project is not
> affiliated with, endorsed by, or sponsored by Tesla, Inc. Prior art:
> PVi1/esphome-twc-control (escalation technique, correlation doctrine)
> and LucaTNT's Neurio register gist. The reference installation is "the
> pilot site", operated by the site owner; no personal data belongs in
> this repo.

## 1. What the project is

Local, cloud-free dynamic load management for the **Tesla Wall Connector
Gen 3** (TWC), a charger with **no control API at all**. The lever is the
wallbox's own Dynamic Power Management (DPM): LoadPilot **emulates the
Tesla reference meter (Neurio) on the TWC's RS485 bus** and feeds it a
carefully shaped version of the real utility-meter measurements. The TWC
then runs its stock firmware loop against the real house consumption and
modulates the pilot signal to ANY vehicle (J1772/Type 2; guests included,
no vehicle API).

Product form (ARCHITECTURE.md D1): one repo, released under one git tag,
distributing two lockstep channels:

- **ESPHome firmware packages** (`esphome/packages/`), consumed as remote
  packages pinned on the tag (`ref: vX.Y.Z`, never `main`);
- **Home Assistant integration** (`custom_components/loadpilot/`),
  installed via HACS custom repository; raises a Repair on version skew.

Hard boundary (D2): **everything that regulates and protects lives in
firmware** and keeps working with Home Assistant, WiFi and cloud all
down. The integration installs, observes, orchestrates; it never sits in
the real-time loop and never hosts a parameter the firmware needs to boot
safe.

## 2. Architecture: the measurement chain

```
Linky (utility meter, TIC serial) --> meter node (Olimex ESP32-POE + TIC hat)
  --> encrypted UDP (XXTEA, port 18511, ~1 Hz) --> charger node (Kincony KC868-A6)
  --> RS485 Modbus RTU (Neurio emulation, polled ~190-200 ms) --> TWC Gen 3
  --> pilot signal (IEC 61851 / J1772) --> vehicle
```

- **Meter node** (France reference): Linky in TIC **standard** mode
  (9600 baud 7E1, frames ~500 ms, SINSTS/URMS give sub-amp current
  resolution; historic mode is degraded: integer amps, no per-phase
  power). Hardware: Olimex ESP32-POE (PoE = one cable near the panel;
  LAN8720 PHY, `power_pin: GPIO12` required on some revisions) + Hallard
  "WeMos TeleInfo" hat (opto-isolated, Linky terminals I1/I2, RX GPIO36).
  `rx_buffer_size: 1024` is mandatory (Tempo frames exceed 400 bytes; at
  256, 2 frames out of 3 are lost, cadence collapses to ~15 s, the
  wallbox hunts). A **TIC watchdog** invalidates all six quantities to
  NAN when the meter link dies: a frozen value can never pass as fresh.
- **UDP contract** (frozen ABI, `docs/fr/15_FOURNISSEURS_MESURE.md` §1):
  ESPHome `packet_transport`, port **18511**, XXTEA + rolling code, six
  quantities `lky_ia/ib/ic` (A) and `lky_pa/pb/pc` (VA), import-positive,
  RAW (never smoothed), 1 Hz heartbeat + immediate send on change,
  **silence on failure** (never freeze-and-repeat). Single-phase: B/C
  published at 0 but slaved to the watchdog (NAN on all six when phase A
  dies). Measured end-to-end latency ~1.1 s median. If the network blocks
  LAN to WLAN broadcast, switch to unicast (one destination; the rolling
  code rejects broadcast+unicast duplicates).
- **Charger node**: KC868-A6 (RS485 transceiver MAX13487E, hardware
  auto-direction, TX GPIO27 / RX GPIO14, WiFi). Emulates a Neurio as
  **Modbus RTU slave** on the TWC's internal RS485 terminal block (A/B +
  ground; swap A/B if bytes arrive but zero valid frames). The TWC is the
  Modbus **master** and polls every ~190-200 ms with a **~66 ms reply
  deadline** (hence: never `logger: level: VERBOSE` on this node; the
  blocking logs miss the deadline and the wallbox gets zero replies).
- **Source priority** in the charger node, re-evaluated continuously:
  **UDP (fresh < 5 s) > HA mirror entities (~3 s latency, 10 s
  unavailability debounce) > fail-safe** (publish the service-breaker
  value, dithered: margin zero, charge blocked, exactly like a dead real
  meter). Fail-safe is also the boot state.
- **Home Assistant** (optional): mirrors the meter entities (backup
  path), writes the node-resident knobs, derives sensors, orchestrates.

## 3. The publication law (firmware, `esphome/packages/twc-core.yaml`)

Definitions: `L` = Max Conductor Limit as configured in Tesla One
(pilot: 21 A). `contract_limit` = grid-contract limit per phase (pilot:
21.7 A for 15 kVA three-phase). `budget = contract_limit x (1 - buffer%)`
(default buffer 10 %; pilot equilibrium ~19.5 A). `worst` = worst-phase
measured current (includes the wallbox's own draw by construction).
`bias` = pause lever in amps.

```
o_raw = worst + bias + (L - budget)
if o_raw <= L:  pub = o_raw                      # shifted reality, gain 1, zero delay
if o_raw >  L:  pub = L + clamp(gain x (o_raw - L), 0.1, emax)
pub += tail (variant B, decaying)                # anti-oscillation, see below
pub += dither (+/-0.05 A alternating, 1 Hz)      # ALWAYS, including fail-safe
published identically on all 3 CT channels (symmetric)
```

Why each piece exists (all measured, section 4):

- **Symmetric publication**: the TWC service loop is a symmetric
  functional of the 3 CTs (engages when the mean crosses L) while its
  protection keys on the worst CT; publishing the worst phase identically
  makes min = mean = max, so the service engages at the true constraint
  whatever the real functional is, and the protection never sees a
  differentiated excess. Side effect: `ct_total` registers read 3x the
  value; accepted in three-phase commissioning.
- **Gain 1 / zero delay below L**: the plausibility layer demands the
  published signal echo the vehicle's own ramps 1:1 (never dilute, never
  delay). The published measure INCLUDES the wallbox branch, so
  correlation holds by construction. No vehicle estimator, no smoothing.
- **Compressed excursion above L**: the height above L is itself the
  measured slow-down signal (micro-law: L+0.1 -> ~-1 A/s descent; L
  exactly -> HOLD; below L -> recovery ~1 A / 30 s). Compression keeps
  the excess integral small: trip becomes "improbable by dynamics"
  (~20 A.s budget vs seconds of exposure).
- **Dither +/-0.05 A**: a static published value is what latches the
  distrust state; the value is never twice the same, even in fail-safe.

Constants (defaults in `twc-core.yaml`, runtime-adjustable unless noted):

| Knob / constant | Default | Validated range / notes |
|---|---|---|
| `law_gain_default` (echo gain above L) | 0.75 | 0.5 and 0.75 both field-validated; **absolute floor ~0.5** (below: dilution, distrust latches; measured with 0.25) |
| `law_emax_default` (max excursion above L) | 1.0 A | 0.8-1.0; the dead band reaches ~L+0.9, lower caps waste integral without effect |
| `law_nudge_min_a` (min signal above L) | 0.1 A | not a knob; also the escalation floor |
| `law_dither_a` | 0.05 A | not a knob |
| Variant B tail | 0 (inert) | decays 0.15 A/s; 2.0 A in production on the pilot; validated closed loop (11 min pinned at exact equilibrium, zero oscillation); deltas still pass gain 1 both ways |
| `buffer_default_pct` | 10 % | 0-30 % |
| `bias_max_a` | 16 A (three-phase) | 32 A single-phase (a single-phase TWC draws up to 32 A) |
| Bias ramp | +1.0 A / 5 s up, -0.5 A / 5 s down | applied immediately when the contactor is open (else: 160 s start-refusal window, "code 10") |
| `escalation_timeout_ms` | 120 s | sustained zero availability -> publish L+0.1 = clean stop order |
| `escalation_kick_a` (stage 2) | 0.9 A | after 2x timeout (4 min) of sustained constraint publish at least L+0.9 to break the dead-band hysteresis; one kick per episode; autonomous, no HA |
| `vehicle_floor_a` (firewall R1) | 6.0 A | with the contactor closed each incomer phase carries at least the vehicle minimum; lower readings are impossible and would latch distrust |
| `glitch_drop_a` (firewall R2) | 5.0 A | sudden drops need 2 consecutive samples; rises always pass immediately (the safe direction) |
| `udp_fresh_ms` | 5000 | 5 missed heartbeats -> HA mirror |
| `main_breaker_limit_a` | 25 A | the fail-safe publication value |
| `twc_conductor_limit_a` | 21 A | must equal the Tesla One Max Conductor Limit |
| `recompute_interval` | 1000 ms | law tick |

Firmware switches and modes:

- `Signal Mode` select: `RAW` (publish raw measure + bias, pure Neurio
  emulation) / `OMBRE-MAX` (publish RAW, compute the law in shadow,
  exposed as `Shadow Published Current`) / `ACTIF-MAX` (publish the law).
  **Boots in ACTIF-MAX and survives reboots** (`restore_value`):
  deliberate for production (after an outage the node must come back
  REGULATING). First-install rule: switch to RAW immediately after
  flashing, climb the ladder RAW -> OMBRE-MAX -> ACTIF-MAX.
- `Charge Stop` switch: immediate stop order (publish >= L+0.1), never
  restored across boots.
- `Meter Absent` switch (test): silences the Modbus server entirely; the
  TWC falls back to its documented 6 A cap.
- Master kill-switch `control_enabled`: OFF = factory behaviour
  (0 A publication = maximum headroom).
- **The law knobs (gain, emax, tail) have `restore_value` OFF**: they
  always boot at validated defaults, so **a reflash silently resets any
  tuning** (lived: the tail fell back to 0 after a flash). The
  integration's opt-in "law settings enforcement" re-pushes them at setup
  and on every node reboot.

## 4. The TWC Gen 3 behaviour model (the core asset)

Measured on the pilot (fw **26.18**, three-phase 15 kVA, Max Conductor
Limit 21 A, ~2000 instrumented episodes, 57 contactor cuts re-analysed);
revalidated point by point on **26.26.1**. Labels: MEASURED / INFERRED /
REPORTED. Constants are properties of the wallbox firmware + vehicle
pair: re-calibrate on any TWC firmware change.

### 4.1 Service loop (pilot modulation)

- Symmetric functional of the 3 published CTs; engagement only observed
  when the **mean** crosses L (MEASURED; mean-vs-min ambiguity moot under
  symmetric publication).
- Near the limit: first pilot movement ~5-20 s after crossing (19 s
  measured). Far from the limit: dynamics in **minutes** (REPORTED,
  convergent), hence the escalation technique for deliberate stops.
- Autonomous recovery at clear margin: **~1 A / 30 s**.
- Does NOT watch the worst published phase (>= 20 discriminating
  episodes: max > 21 with mean < 21 produced zero modulation).

### 4.2 Protection (bite, then cut)

- Keys on **max(CT1..CT3)** vs L, never averages (>= 20 cuts with
  mean < 21, zero counter-example).
- **Bite**: 2-6 A nibble, trigger max ~21.3 (up to ~23), latency <= 5 s,
  5-10 s duration, full recovery even while the channel stays > 21.
- **Cut**: contactor opens at worst-phase excess integral **~20-21 A.s**,
  integral decays while back under L. Shortest observed path to cut:
  43 s. Valid for excesses >= ~1 A only: at +0.5 A the wallbox tolerated
  35 A.s and ~70 s without any reaction.

### 4.3 Dead band and hysteresis (refined on 26.26.1)

- From REST the pilot engages a downward correction only at
  **~L + 0.85** published.
- Once PULLING it follows down to **published = L, where it HOLDS**
  (95 s pinned within 0.1 A), and re-ramps when published < L.
- Consequence: approaching the budget from below parks the vehicle above
  the exact equilibrium (published sits in the dead band, nothing moves);
  approaching from a deep constraint converges exactly. Any external
  nudger must raise fast, release slowly, and kick through L+0.85 when
  the vehicle idles above target. Escalations landing in L+0.1..L+0.5
  from rest are simply ignored.

### 4.4 Plausibility and the distrust state

The firmware checks that the polled meter correlates 1:1 with its own
output. Violations latch a **distrust state** (undocumented by Tesla) in
which the emulated meter is durably ignored.

Entry paths (MEASURED unless noted):

1. A published value **below the wallbox's own branch current** (a 0.6 A
   / 2 s glitch while drawing 16 A latched it).
2. A **vehicle ramp absorbed by a saturated flat publication** (car
   ramped 8 -> 16 A, published echoed +0.7 A: correlation broken).
3. Dilution: effective gain < ~0.5 on the charger component (gain 0.25 /
   emax 0.5 latched distrust in a single ramp).
4. REPORTED (Klangen82 #1): even a permissive +1 A discontinuity
   uncorrelated with the wallbox can latch it.

Once installed: no service modulation, no bites, no integral cut; the
L+0.1 stop order was **ignored for 8 minutes**. The wallbox charges at
its internal ceiling. **Honoured at standstill, ignored in-session**
(MEASURED + community-corroborated): the charge-start admission gate
stays meter-driven (start refused at published > L-5), so a start refusal
NEVER proves trust is back. Only ignored orders strictly above L
(>= L+0.1 sustained) prove distrust.

Does NOT clear it (MEASURED): charging-current renegotiation, a new
session, a reboot of the emulating node (~1 min Modbus dropout), the
+/-0.05 dither.

Recovery protocol (MEASURED once, contributions partially confounded):
**wallbox power-cycle** (breaker off/on) + **~2 h of honest 1:1
published signal** (shadow mode) + **first session start with the house
calm** (opening ramp fully echoed, never absorbed by saturation). A
power-cycle plus a short cure (< 1 h) did NOT recover. Working
hypothesis (INFERRED): trust is a score rebuilt by time on a plausible
signal, not an event flag.

### 4.5 Vehicle-side behaviours (Tesla, through the wallbox)

- Amps memorised **per location** (often 16 A), re-applied at every
  session restart; a setting made during a stable charge sticks.
- **Silent give-up**: after ~3 disturbed charge starts within minutes the
  vehicle stops retrying; signature `evse_state` = 9, zero wallbox
  alerts. Restart requires the app or unplug/replug. Anti-cycling is a
  design requirement.
- Vehicle minimum ~6 A (three-phase AC); PVi1 reports a 5 A regulated
  floor on 26.18 (distinct from the documented 6 A loss-of-meter
  fallback).

### 4.6 Measured dynamics (calibration table)

| Quantity | Value |
|---|---|
| Bite latency / amplitude / duration | <= 5 s / 2-6 A / 5-10 s, full recovery |
| Cut integral (worst-phase excess) | ~20-21 A.s, decays under L, for excess >= 1 A |
| Service latency near L | ~5-20 s |
| Service recovery | ~1 A / 30 s |
| Service far from L | minutes (REPORTED) |
| Ramp-down at a cut / ramp-up after re-auth | ~1 A/s / ~0.65 A/s |
| Contactor-open window in a cycle | ~15-20 s |
| RAW bang-bang period (loop gain 1) | ~55 s |
| One ampere of charge (three-phase) | ~230 VA per phase |
| Modbus poll cadence / reply deadline | ~190-200 ms / ~66 ms |
| Vehicle response to a J1772 setpoint change | ~5 s |
| `evse_state`: cycle stop / give-up | 11 -> 7 / 11 -> 9 |

### 4.7 Closed-loop failure modes (and their fixes)

- **RAW self-referent publication (loop gain 1)**: bang-bang ~55 s, no
  plateau below demand. Not a firmware ceiling: a marginally stable loop.
  Fixed by the clamped/co-variant law. Corollary: beyond ~1 Hz,
  measurement freshness adds nothing; sub-second CT clamps are useless.
- **v1 hard clamp (flat at L)**: manufactured distrust entry #2 (absorbed
  ramps). Replaced by the co-variant law (level above L = signal).
- **v2 at sustained constraint (gain 0.5 / emax 1.0)**: genuine limit
  cycle +/-2.5 A, period ~20 s; 7 excursions accumulated the cut
  integral. NEVER fix by lowering the gain (dilution -> distrust,
  strictly worse). Fixed by **variant B** (decaying tail): validated
  closed loop, 11 min pinned at the exact equilibrium.
- **The "balance dance" is NORMAL**: +/-1 A around equilibrium with
  published oscillating around L is the law working, not distrust; do not
  alert on it.

### 4.8 What Tesla documents officially (DPM app note rev 1.2, Jan 2024)

Loss of meter -> 6 A max output (degraded, not stop). Max Conductor
Limit = 80 % of panel rating. One Wall Connector per meter. Requires
fw >= 23.8.1. **No distrust state documented anywhere.**

## 5. Protection layers, fastest to last resort

| Layer | Lives in | Reaction |
|---|---|---|
| Publication law (car yields ~1 A steps) | charger node | seconds |
| Anti-glitch firewall (R1 6 A floor contactor-closed; R2 2-sample confirmation of drops > 5 A) | charger node | instantaneous |
| Escalation stage 1 (120 s zero availability -> L+0.1 stop) | charger node | 120 s |
| Escalation stage 2 (4 min sustained constraint -> >= L+0.9 kick) | charger node | 240 s |
| STOP switch | charger node | immediate |
| Pause lever (bias) driven by house-side shedding | HA layer | 45 s observation, then ~2 min |
| Appliance shedding, alerts, meter overload signal (STGE bit) | HA layer | minutes |
| Fail-safe (no healthy source: publish breaker value, dithered) | charger node | 5 s freshness window |

## 6. The HA integration (`custom_components/loadpilot/`, v1.3.0)

- **Config flow** (5 steps): country profile; two ESPHome node names
  (validated against the entity registry); electrical settings (phases
  1|3, French contract presets 3-24 kVA mono / 6-36 kVA tri or custom
  per-phase limit, buffer); six mirror entities; confirmation with the
  computed budget. Options flow: advanced entity mapping (arbitrary
  entity ids, keys declarable absent), `vehicle_current_entity`,
  orchestration toggles.
- **Derived entities**: `sensor.loadpilot_state` (`regulating` / `idle` /
  `escalating` / `failsafe` / `off`), `sensor.loadpilot_headroom_l1/2/3`,
  `sensor.loadpilot_worst_phase`, `number.loadpilot_charge_cap`,
  `binary_sensor.loadpilot_meter_distrust`.
- **Services**: `loadpilot.set_bias` (amps 0-16, step 0.5),
  `loadpilot.pause` (full bias), `loadpilot.resume` (bias 0). The ramp
  stays firmware.
- **Node entities** (contract, `CONTRACTS.md` §3): published/real
  current and power per phase, `source_active`
  (`UDP`/`HA`/`FAILSAFE`/`OFF`/`BOOT`), `udp_age`, `udp_fresh`,
  `polling_active`, `poll_interval`, bias target/applied, contract
  limit, buffer, `control_enabled`, `escalation_active`, law gain/emax,
  Charge Stop, Meter Absent, Signal Mode, Shadow Published Current,
  `fw_version` (skew detection).
- **Orchestration capabilities (axis B, all opt-in)**, prerequisite
  `vehicle_current_entity` (wallbox local vitals 5 s poll, or the
  official `tesla_wall_connector` integration ~30 s with a 60 s
  freshness guard). Decision logic is pure (`control.py`, injected
  clock, replayed field traces in `tests/`).

### 6.1 Control patterns (motifs) and their constants

**Charge cap (B1, field-validated)**: 10 s tick;
`target = clamp(round0(worst_headroom + vehicle_current - cap), 0, bias_max)`.
Dead band 0.5 A. **Damper (asymmetric writer)**: raise immediately,
decay at most 0.5 A per tick (killed an 11-16 A limit cycle).
**Anti-hysteresis kick**: when the vehicle idles > cap+0.5 with the
published value parked in the charger dead band [L+0.05, L+0.8], write
target+1.5 A once. **Ownership guard**: a bias above
max(target, last_own)+0.5 belongs to someone else (pause, shedding):
never fight it; release (write 0) only when the bias is exactly your
own. Result: a 13 A cap held at 13.2 A steady.

**Convergence trim (B2, default OFF)**: state machine IDLE -> ARMED ->
KICKING -> COOLDOWN. Arm when: enabled, cap < 0.5, state `regulating`,
distrust not true, worst headroom < -0.3 A, published in the dead band,
bias exactly 0, vehicle current fresh and > 6.5 A. After 180 s sustained:
kick bias 2.0 A; release on engagement (vehicle dropped > 1.0 A below
the armed reference) or 25 s timeout; cooldown 300 s. **Ordered
redundancy with firmware stage 2**: the trim acts at 3 min, the firmware
kicks at 4 min; if stage 2 engages mid-kick the trim abandons cleanly,
releasing only its own exact 2.0 A (a foreign bias is never
overwritten). Never a conflict, by construction.

**Meter distrust detector (B4)**: trip when published_max >= L+0.85
sustained 120 s while the vehicle pulls > 9 A; clear when published <
L-1.0 or vehicle < 7 A, sustained 60 s. DISABLED (not degraded) without
the vehicle-current source. Calibration lesson: a 21.45 threshold sat
INSIDE the dead band and produced a false positive; thresholds must live
in the traction zone (>= L+0.85).

**Law settings enforcement**: optional stored gain/emax (and site-mapped
tail) re-pushed at setup and on every node reboot, closing the
reflash-resets-tuning gap.

## 7. Numbered key lessons

Historical numbers from the pilot's internal log are kept as aliases
where they appear in code and tests.

1. **Never dilute** (alias lesson 31): the published signal must echo
   the vehicle's ramps 1:1; multiplicative gain >= ~0.5 without delay is
   the measured floor; treat oscillation with the law's SHAPE (variant B
   tail), never with the gain.
2. **No dead values** (alias lesson 29): a static/flat published value
   latches distrust; permanent +/-0.05 A dither everywhere, fail-safe
   included; providers go silent on failure, never freeze-and-repeat.
3. **Never publish below the wallbox's own branch current**: physically
   impossible for a real incomer meter; instant distrust entry. Firewall
   R1 encodes it (6 A floor while the contactor is closed).
4. **No internal state** (alias lesson 28): the abandoned synthesizer
   architecture accumulated ~20 dynamic globals across six fixes, each
   fix's state creating the next failure; the winning law is memoryless
   (one escalation timer). Add state only with a written justification.
5. **`restore_value` is a design decision per knob**: law knobs boot at
   validated defaults (restore OFF) so a reflash resets tuning
   (integration enforcement closes it); Signal Mode restores (ON) and
   ships ACTIF-MAX so a production site comes back regulating.
6. **Bias writers own their writes** (the "bias writers" doctrine):
   several writers share one bias channel (pause/shedding, cap loop,
   trim kick); each may only release a value it wrote itself, and a
   higher foreign bias always wins. Encoded as the ownership guards of
   `control.py`.
7. **ESPHome native API deduplicates identical states**: a heartbeat
   with `force_update: true` never reaches the node, so a staleness
   guard on value change declares stable plateaus dead (measured: -7.3 A
   collapses at constant inputs). Never build freshness on value change.
8. **Never `logger: level: VERBOSE` on the charger node**: blocking logs
   miss the ~66 ms Modbus reply deadline; the wallbox gets zero replies.
9. **`rx_buffer_size: 1024` on the TIC UART**: Tempo frames > 400 bytes;
   smaller buffers drop 2 frames in 3 and the wallbox hunts.
10. **Judge the charge on local vitals** (`/api/1/vitals` or the native
    `tesla_wall_connector` integration), never on the vehicle cloud API
    (~10 min poll, freezes): the cloud twice produced the false verdict
    "DPM does not work".
11. **Regulate the car FIRST**: shedding appliances during a charge is
    futile; the DPM immediately redistributes every freed watt to the
    vehicle (measured 16->0->16 bang-bang).
12. **Tesla One limit order**: lower Max Output Current first, then set
    Max Conductor Limit; a Conductor Limit left at 32 A on a 21 A
    contract means "never throttles".
13. **Boot order and polarity**: reboot the ESP32 AFTER the wallbox is
    online for meter detection; RX bytes with zero valid frames = swap
    A/B.
14. **One ESPHome build at a time** on small machines (two parallel
    compilations crashed the build host; packages set
    `compile_process_limit: 1`).
15. **Never OTA-flash the charger node during an active charge** (reboot
    = Modbus down = fail-safe on restart).
16. **Escalations must clear the dead band**: values landing in
    L+0.1..L+0.5 from rest are ignored; stage 2 kicks at L+0.9.
17. **Freeze the wallbox firmware** (block its WAN at the router);
    update only supervised, then re-run the BEHAVIOR §8 validation. The
    calibration is firmware-specific and downgrades are impossible.

## 8. Validation status

**Field-validated (production, pilot site)**: the three-phase chain end
to end; provider `teleinfo-fr.yaml`; board pack `kc868-a6.yaml`; law v2
co-variant (gain 0.5 and 0.75, emax 1.0); variant B tail closed-loop
(2.0 A, 0.15 A/s decay); escalation stages 1 and 2; anti-glitch R1/R2;
fail-safe publication; bias ramp and the contactor-open immediate apply;
charge cap loop (13 A held at 13.2 A); trim arming/kick; distrust
detector thresholds; TWC firmwares 26.18 (full calibration) and 26.26.1
(revalidation; fine protection constants and distrust paths deliberately
not re-measured).

**Theoretical (designed, never benched)**: the ENTIRE single-phase chain
(`phase_count: "1"`, `teleinfo-fr-mono.yaml`, 32 A bias ceiling, CT
registers actually read when commissioned single-phase = bench point 1;
TESTPLAN cases C10, C14-C20); providers `dsmr-p1.yaml`, `sml-de.yaml`,
`ct-clamps.yaml` (skeletons); board pack `esp32-s3-core.yaml` (compiles,
never connected to a wallbox); the generic re-formulations in
`control.py` (ownership guard form, arming reference, cooldown, max over
phases).

**Remaining physical tests**: TIC watchdog hot-unplug, meter-absent 6 A
fallback, from-scratch install campaign.

**Known open risks**: the distrust layer is the structural risk (Tesla
hardens it version after version and could close the commissioning
workaround); HA 2026.8 ignores `suggested_object_id` (translated ids on
non-English instances; rename once in the registry).

## 9. Commissioning facts (Tesla One)

- Without commissioning the emulated meter, NOTHING throttles (the TWC
  never initiates Modbus polling).
- Path: wallbox commissioning hotspot (QR under the faceplate) ->
  installer menu -> Home Load Management -> add meter (detects the
  emulated Neurio). CT1/2/3 = Conductor, CT4 = None (single-phase: CT1
  only).
- Installer lock since fw ~26.2.0; community-validated workaround on
  26.18: a generic Tesla account via the Tesla app, More -> "Tesla
  device settings". Unofficial; can be closed by any update.
- The commissioned meter SURVIVED the 26.18 -> 26.26.1 update (measured).

## 10. Glossary (French / English)

| French | English | Meaning |
|---|---|---|
| borne | wallbox / charger | the TWC Gen 3 |
| nœud borne / nœud compteur | charger node / meter node | the two ESP32s |
| compteur | utility meter | Linky in France |
| TIC / téléinfo | TIC (teleinfo) | the Linky telemetry serial output |
| loi de publication | publication law | the shaping law of section 3 |
| pire phase | worst phase | max of the per-phase measures |
| biais | bias | the pause lever (amps added to the published value) |
| tampon / buffer | safety buffer | the (1 - b%) factor of the budget |
| marge / dispo | headroom / availability | budget minus measure |
| défiance | distrust | the latched meter-ignored state |
| vraisemblance | plausibility | the 1:1 correlation check |
| morsure | bite | 2-6 A protection nibble, recovers |
| coupure | cut | contactor opening (integral ~20 A.s) |
| traction | pull / traction | sustained downward modulation once engaged |
| bande morte | dead band | L+0.05..L+0.8, where the pilot is deaf from rest |
| traînée | tail | variant B decaying additive term |
| escalade (palier 2) | escalation (stage 2) | L+0.1 stop order; 4 min L+0.9 kick |
| délestage | load shedding | house-side appliance shedding |
| abonnement / limite de contrat | grid contract / contract limit | e.g. 15 kVA three-phase = 21.7 A/phase |
| disjoncteur de branchement | service breaker | fail-safe publication value |
| plafond de charge | charge cap | user ceiling, integration axis B1 |
| amortisseur | damper | asymmetric bias writer (raise fast, decay 0.5 A/tick) |
| écrivains de biais | bias writers | the ownership doctrine of the bias channel |
| chasse / pompage | hunting | oscillating charge current |
| cycle limite | limit cycle | the +/-2.5 A / 20 s closed-loop oscillation |
| remontée | recovery / ramp-up | autonomous ~1 A / 30 s climb |
| repli / fail-safe | fail-safe | publish breaker value, charge blocked |
| mise en service | commissioning | Tesla One meter declaration |
| ombre (OMBRE-MAX) | shadow mode | compute the law without publishing it |
| abandon silencieux | silent give-up | vehicle stops retrying, evse_state 9 |
| kill-switch maître | master kill-switch | control_enabled OFF = factory wallbox |

## 11. File map

| Path | Content |
|---|---|
| `esphome/packages/twc-core.yaml` | The law (board-agnostic charger core) |
| `esphome/packages/boards/` | kc868-a6 (validated), esp32-s3-core (draft) |
| `esphome/packages/providers/` | teleinfo-fr (proven), teleinfo-fr-mono / dsmr / sml / ct-clamps (theoretical) |
| `esphome/examples/` | Ready-to-copy node entry files (tag-pinned) |
| `custom_components/loadpilot/` | Integration; `control.py` = pure policies; `const.py` = keys |
| `tests/` | pytest replays of the field traces (law model + control) |
| `docs/en/BEHAVIOR.md`, `docs/fr/40_LOI_DE_COMMANDE.md` | The measured model (EN condensed / FR definitive) |
| `docs/en/INSTALL.md`, `docs/fr/INSTALL.md` | Install guides |
| `docs/fr/DESIGN_*.md`, `docs/fr/60_ETUDE_SYNTHETISEUR.md` | Design studies incl. negative results |
| `docs/en/RUNBOOK_INCIDENTS.md` | Incident signatures and operator responses |
| `docs/en/TESTPLAN.md` | GO/NO-GO validation campaign |
| `ARCHITECTURE.md`, `CONTRACTS.md` | Frozen decisions and interface contracts |
| `dashboards/` | Lovelace cards (three-phase and -mono variants), UX copy |
