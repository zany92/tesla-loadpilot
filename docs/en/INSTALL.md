> 🇫🇷 [Version française](../fr/INSTALL.md)

# Installation guide - France (Linky, TIC teleinfo)

> Complete walkthrough for the reference installation: Linky (the French
> smart utility meter) in TIC standard mode (TIC = Teleinfo, the meter's
> telemetry output), Olimex ESP32-POE meter node + Hallard hat, Kincony
> KC868-A6 charger node, Tesla Wall Connector Gen 3 (firmware ≥ 26.18).
>
> **Project status: private beta.** The generic ESPHome packages
> (`esphome/packages/`) and the HACS integration are being extracted
> from the reference firmware; the steps that depend on them are written
> in the future tense and tagged `TODO-sync`. The hardware steps, the
> Tesla One commissioning and the pitfalls, on the other hand, are lived
> and validated in production.
>
> *Independent project, not affiliated with Tesla, Inc.*

## ⚠️ 0. Electrical safety - read in full before opening anything

- The Wall Connector's RS485 terminal block is **behind the faceplate, a
  few centimetres away from live 230 V parts**. **Switch off the wallbox's
  dedicated breaker** before removing the faceplate, and verify the absence
  of voltage.
- The TIC connection is made on the Linky's I1/I2 terminals: they are
  safety extra-low voltage, but they sit **in or next to the electrical
  panel / metering board**. Switch off whatever needs to be, and never work
  alone in a live panel.
- If you are not comfortable working inside an electrical panel, **have the
  wiring done by a qualified electrician**.
- You use this project **at your own risk**. A bad configuration can
  completely neutralise load management (lived experience: badly set
  Tesla One limits = no throttling at all, see §4). Always test in shadow
  mode before going active (§6).
- Absolute flashing rule: **never OTA-flash during an active charge**
  (reboot = Modbus server down = fail-safe publication on restart).

## 1. Prerequisites

### Hardware (detailed BOM: [`10_MATERIEL.md` (French)](../fr/10_MATERIEL.md))

| Role | Hardware |
|---|---|
| Meter | Linky (single- or three-phase) switched to **TIC standard mode** (request it through your supplier/Enedis, the French grid operator, if still in historic mode; historic mode is degraded: whole amperes, no per-phase power) |
| Meter node | Olimex ESP32-POE + Hallard "WeMos TeleInfo" hat (RX GPIO36) |
| Charger node | Kincony KC868-A6 (validated reference; other boards: [`20_FIRMWARE.md` (French)](../fr/20_FIRMWARE.md) §2.9) |
| Wallbox | Tesla Wall Connector Gen 3, firmware ≥ 26.18 |
| Link | CAT5e (one twisted pair + ground), short run preferred |

### Software

| Component | Minimum |
|---|---|
| Home Assistant | 2025.12 |
| ESPHome | 2025.2 (encrypted `packet_transport` + rolling code) |
| Tesla One app | current version (local access, no pro account required) |

### Secrets - BEFORE any flash

Copy `esphome/secrets.yaml.example` to your ESPHome `secrets.yaml` and fill
in every value (WiFi, ESPHome API keys, OTA passwords, and the **shared UDP
key** between the two nodes: it is what encrypts the measurements with
XXTEA). The `secrets.yaml` file **is never committed**
(see [`../SECURITY.md`](../../SECURITY.md)).

## 2. Meter node (Olimex ESP32-POE + Hallard hat)

1. **TIC wiring**: two wires between the Linky's **I1/I2** terminals and
   the Hallard hat's TIC input (opto-isolated, no critical polarity on this
   hat). The hat mounts on the Olimex's UART port: **RX GPIO36**, 9600 bd,
   7E1, standard mode.
2. **Network**: the ESP32-POE is powered and connected over Ethernet (PoE
   or USB). The config declares `power_pin: GPIO12` (power supply of the
   LAN8720 PHY); without it, Ethernet may not come back after a soft reset
   on some units ([`20_FIRMWARE.md` (French)](../fr/20_FIRMWARE.md) §1.2).
3. **Flash**: compile and flash the meter node YAML from the ESPHome
   dashboard (first flash over USB, OTA afterwards).
   `TODO-sync`: the file to use will be
   `esphome/packages/providers/teleinfo-fr.yaml` consumed through an
   example entrypoint (`esphome/examples/`), pinned on the release tag
   (`ref: vX.Y.Z`). Until the extraction lands, the sanitised reference
   file is `esphome/olimex-portail.yaml`.
4. **Checks**:
   - the 6 quantities (IRMS1-3, SINSTS1-3) show up in HA and vary;
   - pitfall #1: **`rx_buffer_size: 1024` is mandatory** (a standard Tempo
     frame exceeds 400 bytes; at 256, 2 frames out of 3 are lost and the
     effective cadence drops to ~15 s, and the wallbox will hunt). Tempo
     is an EDF tariff whose TIC frames are longer;
   - on Tempo, verify the cadence stays at ~1 Hz.

On single-phase (THEORETICAL - never bench-validated): a single-phase
Linky does not emit the indexed labels this provider reads (SINSTS1/2/3),
so use the dedicated provider
`esphome/packages/providers/teleinfo-fr-mono.yaml` through the
`esphome/examples/meter-teleinfo-mono-olimex-poe.yaml` entrypoint
(`SINSTS` without index + `URMS1`; phases B/C published at 0, slaved to
the TIC watchdog). With the three-phase provider the UDP feed would never
become fresh and the charger node would sit in fail-safe forever.

## 3. Charger node (Kincony KC868-A6)

1. **WALLBOX BREAKER OFF.** Remove the Wall Connector's faceplate.
2. **RS485 wiring** (full diagram: [`10_MATERIEL.md` (French)](../fr/10_MATERIEL.md) §2):
   - KC868-A6 terminal **A** → **red** wire (A+) of the internal RS485
     terminal block;
   - terminal **B** → **white** wire (B−);
   - **common ground** between the two;
   - no 120 Ω termination needed on a short link (validated in
     production); plan for one if the link exceeds a few metres or if
     frame errors appear;
   - for reference, the **official** Tesla specification (DPM app note)
     for the meter: **shielded** twisted pair, **120 m max** length,
     shield drain **earthed on the panel side** (one end only). On a long
     link or in a noisy environment, align with it. Note: community
     builds work without common ground or termination (LucaTNT gist); our
     reference uses the common ground, both exist in the field.
3. **Flash** the charger node firmware (same remarks: first flash over
   USB, `secrets.yaml` filled in). `TODO-sync`: target =
   `esphome/packages/twc-core.yaml` + `esphome/packages/boards/kc868-a6.yaml`
   pinned on a tag; until then, the sanitised reference is
   `esphome/kc868-a6-1.yaml` ("PVi1-GRADE 17/08" block).
4. **Substitutions to adjust to YOUR installation**:
   - contract limit per phase (e.g. 15 kVA three-phase: 5,000 VA / 230 V
     ≈ 21 A);
   - service breaker (`main_breaker`): this is the value published in
     fail-safe to block charging;
   - safety buffer (default 10 %);
   - phase count (`phase_count`): `"3"` by default (three-phase
     reference). A single-phase install starts from
     `charger-mono-exemple.yaml` instead (`phase_count: "1"`, bias
     ceiling `bias_max_a: "32"`) and pairs with the single-phase meter
     provider (section 2) - THEORETICAL, see the single-phase insert in
     section 4.
5. **Close the faceplate, re-energise the wallbox.**
6. **Checks**:
   - `TWC Polling Active` = on and `TWC Poll Interval` stable at
     ~190-200 ms: the wallbox is polling the emulated meter;
   - RX bytes but **zero valid frames** → polarity: **swap A and B**
     (pitfall lived here and confirmed community-side: "A → +, B → −, and
     swap if silent");
   - if the wallbox still does not poll: **reboot the ESP32 AFTER the
     wallbox is online** (validated community feedback: the boot order
     matters for the wallbox to detect the meter);
   - **bus speed**: community sources report sometimes **9600**, sometimes
     **115200 baud** depending on installations and versions. Our
     reference firmware works as shipped, do not touch it; if you port
     the config to another base and the bus stays silent with correct
     polarity, try both speeds;
   - charger-node pitfall #1: **never `logger: level: VERBOSE`**: blocking
     logs miss the Modbus reply deadline (~66 ms) and the wallbox no
     longer gets a single reply ([`20_FIRMWARE.md` (French)](../fr/20_FIRMWARE.md) §2.2);
   - `Source Active` = UDP and `UDP Fresh` = on (if the network blocks
     LAN→WLAN broadcast, switch UDP to unicast towards the charger node's
     IP: a single destination at a time).
     On the pilot site a plain twisted pair from an Ethernet cable works
     perfectly over 2 m (unshielded, unterminated).

## 4. Tesla One commissioning - without it, NOTHING throttles

Full step-by-step and lived pitfalls:
[`30_COMMISSIONING_TESLA_ONE.md` (French)](../fr/30_COMMISSIONING_TESLA_ONE.md). Summary:

1. Connect to the wallbox's commissioning hotspot (QR code under the
   faceplate), installer menu → *Home Load Management* → add a meter: the
   wallbox detects the emulated **Neurio**.
2. **CT 1/2/3 = Conductor** (phases L1/L2/L3), CT 4 = None. On
   single-phase: CT 1 only.
3. **The order of the limits matters**: the *Max Conductor Limit* field
   refuses any value below the wallbox's *Max Output Current* → **lower
   Max Output Current first** (e.g. 16 A), then set the Conductor Limit of
   your contract (21 A for 15 kVA three-phase).
4. Carry these values into the firmware substitutions (Home Load
   Management limit and service breaker).
5. **Verify that DPM acts**: start a charge, create a controlled overshoot
   (kettle, oven...), watch the local vitals
   (`http://<WALLBOX_IP>/api/1/vitals`): expected reaction ≤ 5 s.
   - **Never** judge the charge through the vehicle's cloud API (~10 min
     poll, freezes): local vitals or the `tesla_wall_connector`
     integration only.
   - Conductor Limit left at 32 A on a 21 A contract = "never throttles":
     this is THE pitfall that twice led to the wrong conclusion that
     "DPM does not work".

### Installer lock (firmware ≥ 26.2.0) and workaround

Since roughly firmware **26.2.0**, several installations report that
declaring the external meter is **locked behind Tesla One installer
credentials** (without activation, the wallbox never initiates Modbus
polling). Workaround **community-validated on 26.18** (our version): a
**generic Tesla account** is enough; in the Tesla app, **More → "Tesla
device settings"** gives access to the device configuration without a pro
account. Our reference commissioning (hotspot + Tesla One, §above) worked
without a pro account on 26.18; if the menu is refused to you, use this
workaround. Keep in mind this door is in no way official: Tesla can close
it again with any update.

### STRONG recommendation: freeze the wallbox firmware

The whole chain (bypassed activation lock, behaviour constants measured on
26.18, plausibility layer) rests on a wallbox firmware that is
**undocumented and moving**. The community has already lived through a
behaviour change attributed to an update, and a downgrade is impossible.
**If your installation allows it, block the wallbox's automatic updates**
(no official method documented; open community question). At minimum, note
the firmware version before/after any update and re-run the validation
([`BEHAVIOR.md`](BEHAVIOR.md) §8) after every change.

> ⚠️ **Operating invariant - NEVER publish a value below the wallbox's own
> branch current.** A real meter at the head of the installation can
> physically never measure less than what the wallbox itself is drawing:
> the firmware detects it and enters a **distrust state** in which the
> emulated meter is durably ignored (service, protection and escalation
> included); see [`BEHAVIOR.md`](BEHAVIOR.md) §4. The reference
> publication block honours this invariant by construction (the published
> measurement includes the wallbox's branch); any local modification must
> preserve it, including during the vehicle's ramps.

### Single-phase commissioning (THEORETICAL - never bench-validated)

For a single-phase install (`charger-mono-exemple.yaml` +
`teleinfo-fr-mono.yaml`), the Tesla One steps differ on three points:

- **Grid type**: select *single-phase* when commissioning the Neurio meter
  (the exact wording depends on the Tesla One version).
- **Max Conductor Limit**: size for the single phase, e.g. 32 A (a
  single-phase TWC Gen 3 draws up to 32 A on its one phase).
- **Commissioning ladder**: OMBRE-MAX first, observe via `Shadow Published
  Current`, and keep any stay in RAW as short as possible - in RAW the B/C
  channels publish ~0 constant, a dead signal if the wallbox averages its
  CT registers.

Everything above is THEORETICAL: which CT registers a wallbox commissioned
single-phase actually reads, and whether it tolerates non-zero CT2/3, are
the first bench points ([`TESTPLAN.md`](TESTPLAN.md), single-phase cases).
The control-law constants are three-phase measurements.

## 5. Home Assistant integration (HACS)

`TODO-sync`: the integration is under development; the target path will
be:

1. HACS → custom repositories → add this repository (category
   *Integration*) → install **Tesla LoadPilot** → restart HA.
2. Settings → Devices and services → Add integration
   "Tesla LoadPilot": the config flow will ask for the ESPHome nodes
   (charger, meter), the number of phases (1|3), the contract limit, the
   buffer, and the mirror entities (6 current/power sensors: the BACKUP
   source when UDP goes silent).
3. The integration will write the settings **resident on the charger
   node** (limit, buffer, bias, kill-switch): an HA reboot changes nothing
   on the wallbox, and regulation lives without HA.

The integration will raise an HA *Repair* for any firmware/integration
version skew (both channels install from the **same tag**).

## 6. First tests - ALWAYS shadow first

The firmware exposes a signal mode selector (`Signal Mode`, three
positions: `RAW`, `OMBRE-MAX`, `ACTIF-MAX`). **Careful: as shipped, the
node boots in `ACTIF-MAX`** (see the note at the end of this section), so
your **first move after flashing** is to switch the selector to `RAW`,
then climb the ladder below. **Never stay in active mode without having
observed the shadow first**:

1. **Dry run: `OMBRE-MAX` mode.** The wallbox keeps seeing the raw
   measurement (RAW); the "Shadow Published Current" sensor shows what the
   clamped-symmetric-worst-phase block WOULD publish (a single value: the
   publication is symmetric on all three phases by construction). During a
   real charge, verify over several tens of minutes:
   - shadow ≤ limit at all times (clamp);
   - no aberrant value (NaN, transient 0 at boot).
2. **Activation: `ACTIF-MAX` mode**, preferably with a charge in progress
   and the house loaded (the nominal scenario). Expected (reference
   validation, [`BEHAVIOR.md`](BEHAVIOR.md) §8): gentle modulation below
   the setpoint, plateaus held, recovery at ~1 A / 30 s, **zero contactor
   openings** (note the lifetime cycle counter before/after).
3. **Abort immediately if**: the wallbox ignores the signal for > 2 min,
   ANY contactor opening, polling interrupted > 30 s → back to `RAW` and
   analyse before retrying.
4. **Test the fail-safe**: cut the meter node → `Source Active` must go
   UDP → HA → FAILSAFE and the charge must be blocked within ~10 s. This
   is the expected behaviour, not a bug.
5. Test the **master kill-switch**: OFF = the wallbox returns to its
   factory behaviour (0 A publication = maximum headroom), without
   touching the wiring.

> Note - boot behaviour: the selector **survives reboots**
> (`restore_value`) and the firmware **ships with `ACTIF-MAX` as the
> initial position**. This is a deliberate choice for a production site:
> after a power outage, the node must come back REGULATING, not
> observing. Consequence for a FIRST installation: at the very first
> boot, the node is already in `ACTIF-MAX`. There is no electrical danger
> (the law clamps below your contract limit), but it short-circuits the
> test ladder above. Hence the instruction at the top of this section:
> switch to `RAW` immediately after flashing, and only return to
> `ACTIF-MAX` once the shadow is validated. Once in production, the
> chosen mode is preserved across reboots.

## 7. Vehicle caveat: the silent give-up

After ~3 disturbed charge starts within a few minutes, the Tesla vehicle
**stops retrying**, with no alert whatsoever on the wallbox side
(signature: `evse_state` 9). Restart through the app or by
unplugging/replugging. If your first trials multiply stop/resume cycles,
this is probably it, not a failure. Details:
[`BEHAVIOR.md`](BEHAVIOR.md) §5.

## 8. Troubleshooting

| Symptom | Lead |
|---|---|
| RX bytes but zero valid Modbus frames | A/B polarity swapped |
| `TWC Polling Active` OFF while RX scrolls | VERBOSE logs active → go back to DEBUG |
| The wallbox never throttles | Tesla One limits (§4): Max Output Current first, then Conductor Limit |
| Measurement cadence ~15 s, wallbox hunting | `rx_buffer_size` too small on the TIC side |
| Charge refuses to start for no reason | applied bias > 0 (dedicated sensor) or fail-safe active |
| "DPM does not work" as seen from the vehicle app | frozen cloud sensors: look at the local vitals |

To open a ticket: TWC firmware version is **mandatory**, plus board,
signal mode, and observability sensors
(see [`../CONTRIBUTING.md`](../../CONTRIBUTING.md)).
