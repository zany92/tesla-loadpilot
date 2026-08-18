# Tesla LoadPilot

🇫🇷 [Version française](README.fr.md)

![Tesla LoadPilot: the utility meter at the service entrance, two ESP32 nodes bridging the distance over an encrypted link, and the wall connector charging a car in the garage](docs/assets/hero.png)

[![Validate](https://github.com/zany92/tesla-loadpilot/actions/workflows/validate.yml/badge.svg)](https://github.com/zany92/tesla-loadpilot/actions/workflows/validate.yml)

**Local, cloud-free dynamic load management for the Tesla Wall Connector Gen 3, driven by your utility meter.** The charger adapts its power to whatever the house leaves available, in real time, for any vehicle including guests' cars, with no vehicle API, no manufacturer cloud and no extra energy meter to buy.

> Status: **version 1.3.1**, open source (MIT), running in production on a single pilot site (France, 15 kVA three-phase, ~2000 instrumented episodes, firmwares 26.18 and 26.26.1 validated). Installable as a HACS custom repository. Full history: [GitHub releases](https://github.com/zany92/tesla-loadpilot/releases).

---

## The problem

A home EV charger on a fixed utility contract is a race condition: the oven starts while the car charges at full amps and the main breaker (or the utility's smart meter) cuts the whole house. The official answer is Tesla's Dynamic Power Management, which requires a Tesla-sold meter (Neurio W2 / Remote Meter, expensive and increasingly gated behind installer accounts) and only speaks Tesla.

This project was actually born from a layout problem that makes the official hardware unusable: the Tesla meter must be wired to the charger over RS485, but on the original site the charger sits far away from the service entrance where the measurements live. No practical cable run, no official DPM. LoadPilot bridges that distance by splitting the roles across two ESP32 nodes: one reads the meter at the service entrance, one emulates the meter next to the charger, and an encrypted UDP link over the existing network replaces the impossible cable. Chargers with an open control interface (OCPP and friends) solve this by steering the charger itself, but the TWC Gen 3 exposes no control API at all: existing load managers can only fall back on each vehicle's cloud API (Tesla Fleet and the like), which excludes guests and other brands.

LoadPilot takes a third path: **emulate the Tesla meter** on the charger's own RS485 bus, and feed it a carefully shaped version of the measurements your utility meter already produces. The wall connector then does what its firmware was built to do (modulate the pilot signal to the car) but against your real house consumption. The vehicle is irrelevant: any car that speaks J1772/Type 2 obeys, because it is the charger being steered, not the car.

## What it does

- **Car-first load shedding**: when the house needs power, the car yields first, in ~1 A steps, down to the vehicle floor, before any appliance is touched.
- **Autonomous recovery**: when the house calms down, the charge climbs back on its own (measured: ~1 A / 30 s).
- **Guest-proof**: works identically for any vehicle, because the lever is the charger.
- **Survives everything above it**: the control loop lives in two ESP32s; Home Assistant, WiFi and the cloud can all die and the regulation keeps running on the meter-to-charger UDP path, with safe fallbacks at every stage.
- **Instrumented**: a Home Assistant integration exposes the regulation state, per-phase headroom, worst phase, diagnostics, repair issues and services on top of the firmware.

## How it works

```mermaid
flowchart LR
    subgraph Meter side
        LKY[Utility meter\nLinky, TIC serial] --> M[ESP32 meter node\nOlimex ESP32-POE\n+ TIC receiver hat]
    end
    subgraph Charger side
        C[ESP32 charger node\nKincony KC868-A6] -- RS485 Modbus\nNeurio emulation --> TWC[Tesla Wall Connector\nGen 3]
    end
    M -- encrypted UDP\nXXTEA, ~1 Hz, sub-amp --> C
    M -. HA mirror\nfallback path .-> HA[Home Assistant\nLoadPilot integration]
    HA -. observe + configure .-> C
    TWC -- pilot signal --> CAR[Any vehicle]
```

1. The **meter node** reads the utility meter (France: Linky TIC, ~500 ms frames, sub-amp current resolution computed from SINSTS/URMS) and broadcasts the six per-phase quantities over encrypted UDP. A **TIC watchdog** invalidates everything to NAN if the meter link dies, so a frozen value can never masquerade as a fresh one.
2. The **charger node** emulates a Neurio meter on the wall connector's RS485 bus (the charger polls it every ~190 ms). It picks the freshest source (UDP, then the HA mirror, then a fail-safe that reports full consumption and blocks charging) and publishes the **worst phase, symmetrically on all three CT registers**, shaped by the publication law below.
3. The **wall connector** runs its own stock control loop against those readings and modulates the car.

### The publication law (the heart of the project)

Measured behavior of the Gen 3 firmware (see [docs/en/BEHAVIOR.md](docs/en/BEHAVIOR.md) for the full model with MEASURED/INFERRED/REPORTED labels):

- its *service* loop engages on a symmetric function of the three reported CTs, holds at exactly the limit, pulls the car down above it, lets it climb below it;
- its *protection* watches the worst phase with an integral criterion;
- a *plausibility* layer distrusts the meter within seconds if the reported values ever look impossible (below the charger's own draw) or stop echoing the charger's own ramps. Once distrusted, the meter is ignored entirely, sometimes for hours.

The law therefore never publishes a dead value and never hides the charger's own contribution:

| Regime | Published value |
|---|---|
| Below the constraint | The shifted reality itself: worst phase + bias + (limit - budget). Gain 1, zero delay, correlation is perfect by construction. |
| Above the constraint | limit + clamp(gain x excess, 0.1, max excursion): a bounded slope whose height above the limit is itself the measured "come down" signal. |
| Leaving the constraint | An additive tail decaying at 0.15 A/s (variant B) stops the charger from being invited to climb back immediately, killing the limit-cycle oscillation. Deltas still pass at gain 1 in both directions. |
| Always | A +/-0.05 A dither, including in fail-safe, so the charger never sees a static reading. |

The budget is `contract_limit x (1 - buffer%)`: with the default 10 % buffer on a French 15 kVA three-phase contract, the house-plus-car worst phase converges to ~19.5 A of the 21.7 A available.

### Protection layers, from fastest to last resort

| Layer | Lives in | Reaction |
|---|---|---|
| Publication law (car yields) | charger node | seconds |
| Anti-glitch firewall (R1 floor at 6 A while the contactor is closed, R2 two-sample confirmation of sudden drops) | charger node | instantaneous |
| Escalation (sustained zero availability publishes limit + 0.1 as a stop order) | charger node | 120 s |
| STOP switch (immediate stop order, no ramp) | charger node | immediate |
| Pause lever (bias) driven by the house-side shedding logic | HA layer | 45 s observation window, then ~2 min |
| Appliance shedding, alerts, utility-meter overload signal (STGE) | HA layer | minutes |
| Fail-safe (no healthy measurement source: report full consumption, dithered) | charger node | 5 s freshness window |

## Technical prerequisites

**Hardware (pilot bill of materials, France):**

| Part | Role | Notes | Links |
|---|---|---|---|
| Tesla Wall Connector Gen 3 | The charger being steered | Validated firmwares: 26.18 (calibration reference) and 26.26.1 (full revalidation, BEHAVIOR section 12). **Freeze firmware updates** (e.g. block its WAN access at the router) and only unblock for a supervised update, see the runbook. | [Product page](https://www.tesla.com/wall-connector) |
| Kincony KC868-A6 | Charger-side ESP32 node (Neurio emulation) | ESP32 board with an onboard RS485 transceiver (MAX13487E, hardware auto-direction), relays and inputs as a bonus. Any ESP32 plus a MAX485-class transceiver works too. | [Hardware details](https://www.kincony.com/kc868-a6-hardware-design-details.html) - [KinCony store](https://www.kincony.com/) |
| Kincony ESP32-S3 Core Board (alternative) | Budget alternative for the charger node | ESP32-S3 module (ESP32-S3-WROOM-1U); the vendor page lists an RS485 bus and a wired Ethernet port. A draft board pack exists (`esphome/packages/boards/esp32-s3-core.yaml`, `board: esp32-s3-devkitc-1`): it compiles but has NEVER been validated against a wallbox, so treat it as untested. If you use any bare ESP32-S3 devkit instead, add an external MAX485/MAX13487-class RS485 transceiver (plain devkits have none). | [Product page](https://www.kincony.com/kincony-esp32-s3-core-board.html) |
| Waveshare ESP32-S3-RS485-CAN | Charger-side alternative (industrial) | Isolated RS485 with automatic direction control, digital and power isolation, TVS/surge/ESD, 7-36 V screw terminal. On paper the most robust alternative; not bench-validated yet. | [Product page](https://www.waveshare.com/esp32-s3-rs485-can.htm) |
| Olimex ESP32-POE + MOD-RS485-ISO | Charger-side alternative (uniform Olimex fleet) | Same board family as the meter node, PoE powered. The UEXT RS485 module is NOT auto-direction: ESPHome must drive DE//RE via flow_control_pin; prefer the isolated MOD-RS485-ISO variant. Theoretical, not bench-validated. | [MOD-RS485](https://www.olimex.com/Products/Modules/Interface/MOD-RS485/open-source-hardware) |
| Olimex ESP32-POE | Meter-side ESP32 node | Powered over Ethernet next to the meter; any ESP32 with a free UART works. | [Product page](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/open-source-hardware) |
| Teleinfo (TIC) receiver shield, Charles Hallard design | Reads the Linky's TIC output (I1/I2 terminals) | Opto-isolated serial receiver, ESP32-compatible. Sold assembled. | [GitHub](https://github.com/hallard/WeMos-TIC) - [Tindie](https://www.tindie.com/products/25467/) - [Lectronz](https://lectronz.com/products/wemos-tic) |
| RS485 wiring | Charger node to wall connector | Shielded twisted pair 1.5 mm2 recommended by Tesla, 120 m max, drain grounded panel-side; in practice short unterminated runs are fine: the pilot site runs a plain twisted pair from an Ethernet cable over 2 m without any issue. | Tesla app note, see [docs/en/INSTALL.md](docs/en/INSTALL.md) |

**Software:**

- Home Assistant >= 2025.12, ESPHome >= 2025.2 (encrypted `packet_transport`).
- The two firmware packages from [`esphome/packages/`](esphome/packages/) (charger core + a meter provider; France TIC is production-proven, DSMR/SML/CT-clamp providers are skeletons).
- Commissioning through the Tesla app or Tesla One: on firmware >= 26.2 the external-meter menu is gated behind installer credentials, with a documented workaround (generic Tesla account, "Tesla device settings"), see [docs/en/INSTALL.md](docs/en/INSTALL.md).

## Installation

From zero to a regulating charger, in order:

1. **Build the two nodes.** Wire the TIC receiver shield to the Linky's
   I1/I2 terminals and to the meter-side ESP32; wire the charger-side
   ESP32's RS485 transceiver to the wall connector's RS485 terminals
   (shielded twisted pair, drain grounded panel-side).
2. **Flash the firmware.** Start from [`esphome/examples/`](esphome/examples/)
   (three-phase, single-phase and meter-node variants), set your
   substitutions (contract limit, node names, encryption key) and flash
   both nodes with ESPHome >= 2025.2.
3. **Commission the emulated meter** in the Tesla app or Tesla One so the
   wall connector adopts it as its Neurio. On firmware >= 26.2 the menu is
   gated behind installer credentials; the workaround (generic Tesla
   account, "Tesla device settings") is documented step by step in
   [docs/en/INSTALL.md](docs/en/INSTALL.md).
4. **Install the integration.** With [HACS](https://hacs.xyz/) already
   installed: open HACS > menu (three dots, top right) > *Custom
   repositories* > paste `https://github.com/zany92/tesla-loadpilot`,
   pick category *Integration*, *Add*. Search "Tesla LoadPilot" in HACS,
   open it, *Download*, then restart Home Assistant. Detailed walkthrough
   (each screen described): [docs/en/INSTALL.md](docs/en/INSTALL.md),
   section 5. Manual alternative (no HACS): copy
   `custom_components/loadpilot/` into your `config/custom_components/`
   and restart.
5. **Add the integration** (Settings > Devices and services > Add
   integration > Tesla LoadPilot) and follow the 5-step config flow
   described below.
6. **Verify**: `sensor.loadpilot_state` must read `regulating`, and the
   per-phase headrooms must match your contract minus the live house load.
   Then plug the car in and watch the pilot follow the house.

The full guide with photos, wiring details and the commissioning
walkthrough is [docs/en/INSTALL.md](docs/en/INSTALL.md), also available
in [French](docs/fr/INSTALL.md).

## Configuration

Everything user-facing happens in two places:

1. **The config flow** (5 steps): country profile (France TIC first), the two ESPHome node names (validated against your entity registry), electrical settings (phases, contract presets for the French 6 to 36 kVA subscriptions or a custom per-phase limit, safety buffer with its plain-language meaning: 10 % buffer = the car exploits 90 % of what the house leaves), the six mirror entities for the fallback path, and a confirmation screen showing the computed budget.
2. **Runtime tunables**, resident on the charger node (they survive HA outages and reboots with safe defaults):

| Knob | Default | Safe range | Notes |
|---|---|---|---|
| Buffer | 10 % | 0-30 % | Shifts the equilibrium below the contract. |
| Law echo gain | 0.5 | **never below ~0.5** | Below that floor the charger's own ramps are diluted in the published signal and the plausibility layer rejects the meter (measured the hard way). |
| Law max excursion | 1.0 A | 0.8-1.0 A | The charger has a dead band up to ~limit + 0.9: lower caps cost integral without effect. |
| Tail (variant B) | 0 (inert) | 0-2.5 A | Anti-oscillation; validated in closed loop on the pilot (11 min pinned at the exact equilibrium, zero oscillation), runs at 2.0 A in production. |
| Bias | 0 | 0-16 A three-phase, 0-32 A single-phase | The pause lever; driven by the HA shedding logic, manual mode available. A single-phase TWC Gen 3 draws up to 32 A on its one phase, so a full pause needs the 32 A ceiling (single-phase support is theoretical, see below). |
| STOP switch | off | | Immediate stop order. |
| Meter-absent switch | off | | Test switch: silences the Modbus server entirely (the charger falls back to its documented 6 A cap). |

3. **Entity mapping** (options flow, advanced): if your charger node predates the generic package and uses different entity names, map each of the tracked entities explicitly; keys can also be declared absent. This is how the pilot site itself runs.

4. **Optional orchestration capabilities** (axis B, all opt-in, everything defaults to the historic behaviour). Their shared prerequisite is the `vehicle_current_entity` option (advanced entity mapping): a sensor exposing the vehicle charging current, e.g. the wall connector's local vitals (5 s poll, the pilot setup) or the official Tesla Wall Connector integration (~30 s poll, works in degraded mode; freshness guard at 60 s). Without it the first three stay unavailable or inert:

| Capability | What it does |
|---|---|
| Charge cap (`number.loadpilot_charge_cap`, 0 = auto) | User-chosen charge ceiling. A slow 10 s loop steers the node's bias so the car draws min(cap, what the house leaves); anti-hysteresis kick and asymmetric writer field-tuned on the pilot (a 13 A cap held at 13.2 A steady). The real-time law stays in firmware: if HA dies mid-cap the node keeps every protection. |
| Convergence trim (option, default OFF) | Fixes the dead-band parking: after 3 minutes of shallow sustained constraint it fires a transient 2 A bias kick (25 s at most, conditional release) so the charge converges to the exact budget. Ordered redundancy with the firmware's own 4 minute stage-2 kick, never a conflict (see [docs/en/BEHAVIOR.md](docs/en/BEHAVIOR.md), section 12). |
| Meter distrust detector (`binary_sensor.loadpilot_meter_distrust`) | Raises a problem flag plus a Repairs issue when the published value saturates at L + 0.85 for 120 s while the vehicle still pulls above 9 A: the charger has stopped listening to the emulated meter. Auto-cleared; deliberately disabled (not degraded) without the vehicle-current source. |
| Law-settings enforcement (options, empty = never touched) | The law knobs live on the node with restore_value off: a firmware flash silently resets your tuning. Set the gain / excursion / drag options and the integration re-pushes them at setup and on every node reboot. |

**Single-phase or three-phase.** The installation type is chosen in three matching places: the `phase_count` substitution of the charger-node example you copy (`"3"` in `charger-kc868-a6.yaml`, `"1"` in `charger-mono-exemple.yaml`, which also raises the bias ceiling to `bias_max_a: "32"`), the meter provider (`teleinfo-fr.yaml` three-phase, `teleinfo-fr-mono.yaml` single-phase: a single-phase Linky emits different TIC labels), and the contract preset in the config flow (3 to 24 kVA single-phase, 6 to 36 kVA three-phase). Single-phase variants of the dashboards ship alongside (`dashboards/*-mono.yaml`). Reminder: single-phase support is theoretical, never validated on a bench; the walkthrough is in [docs/en/INSTALL.md](docs/en/INSTALL.md).

## Observations from the pilot

The project's real asset is the measured behavior model of the wall connector, assembled from ~5 days of instrumented episodes and cross-checked against every community source I could find. Highlights:

- Service engages on the phase *average*, protection bites on the *worst phase* with an integral of ~20 A.s above the limit (for excursions >= 1 A; below +0.5 A the charger tolerates far more and mostly does nothing).
- Full validated cascade, hands-off: cooking spike, continuous descent 16 to 12 A tracking the slope, pause when four ACs exceeded what the car could yield, automatic release, autonomous session resume, zero contactor cycles.
- The distrust state is real, sticky and undocumented by Tesla: entries, non-recoveries and the working recovery protocol (power-cycle plus hours of honest signal plus a calm-house session start) are all in [docs/en/BEHAVIOR.md](docs/en/BEHAVIOR.md) section 4, with raw traces published alongside my findings on the upstream project's issue tracker.
- Incident signatures and operator responses are catalogued in [docs/en/RUNBOOK_INCIDENTS.md](docs/en/RUNBOOK_INCIDENTS.md).

## Known limitations, honestly

- **One pilot site.** Calibration was established on TWC fw 26.18 (French three-phase installation) and revalidated point by point on 26.26.1 (BEHAVIOR section 12). The constants (dead band, integral, floors) may drift with future Tesla updates; freeze the firmware and only update under supervision.
- **Single-phase support is designed but THEORETICAL.** It has never been validated on a bench: the control-law constants are three-phase measurements, and the CT registers a wallbox commissioned single-phase actually reads are unknown (bench campaign in [docs/en/TESTPLAN.md](docs/en/TESTPLAN.md), cases C14-C20).
- **The distrust layer is the structural risk.** The law is designed to never trigger it, and the entry points I found are closed (impossible values, absorbed ramps, static fail-safe), but Tesla hardens this layer version after version and could close the commissioning workaround entirely.
- **With the tail off**, a house load hovering exactly at the budget can produce a +/-2.5 A limit cycle that ends in a protective cut. The decaying-tail variant closes it (validated in closed loop on the pilot); it ships inert and must be enabled deliberately.
- **HA 2026.8 ignores `suggested_object_id`**: derived sensors may be created with translated ids on non-English instances; rename them once in the registry (documented in the release notes; a proper fix is being investigated).
- **Upstream lineage.** The publication law grew from the fundamentals of [PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control), now MIT-licensed; this project is published under MIT with explicit attribution to PVi1 and Klangen82 (see [LICENSE](LICENSE)).
- Remaining physical tests: TIC watchdog unplug test, meter-absent 6 A fallback test, from-scratch install campaign ([docs/en/TESTPLAN.md](docs/en/TESTPLAN.md)).

## Repository map

| Path | Content |
|---|---|
| `custom_components/loadpilot/` | The Home Assistant integration (config flow, coordinator, sensors, repairs, services, diagnostics, EN/FR). |
| `esphome/packages/` | The generic firmware: charger core (publication law) and meter providers. |
| `esphome/examples/` | Ready-to-adapt node files (three-phase, single-phase, meter node). |
| `tools/simulate_gain.py` | Closed-loop simulator: publication law + measured pilot hysteresis. Predicts how the knobs shape engagement and equilibrium (cannot predict distrust). |
| `dashboards/` | Lovelace cards (user face: one switch + live info; settings face). |
| `docs/en/BEHAVIOR.md` | The measured TWC Gen 3 behavior model. Start here if you want the science. |
| `docs/en/INSTALL.md` | Full installation guide. |
| `docs/en/RUNBOOK_INCIDENTS.md` | Operator playbook. |
| `docs/en/TESTPLAN.md` | Validation campaign and GO/NO-GO criteria. |
| `docs/DESIGN_*.md` | Design studies, including the negative results that shaped the law. |

## Credits

Built on the shoulders of [PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control) (correlation doctrine, Neurio emulation groundwork) and the community reverse-engineering work in the Home Assistant forum and TWCManager threads. Not affiliated with, endorsed by, or supported by Tesla, Inc. Use at your own risk: this project deliberately interacts with electrical safety equipment; read the limits section twice.
