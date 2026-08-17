# Tesla LoadPilot

> **This project is not affiliated with, endorsed by, or sponsored by Tesla, Inc.**
> "Tesla" and "Wall Connector" are trademarks of Tesla, Inc., used here only to
> identify the hardware this project interoperates with. No Tesla imagery is
> used or distributed in this repository.

**Local, cloud-free charging power regulation for the Tesla Wall Connector
Gen 3** - the wallbox adapts its charging current in real time to your home's
consumption, measured at the utility meter. Any meter, any country, any
vehicle (guests included). France first, with the Linky meter proven in
production.

**Status: private beta.** The control law is validated in production
(17 Aug 2026, reference installation in France, three-phase 15 kVA). The
HACS integration and the generic ESPHome packages are being extracted from
the reference firmware - nothing is published yet.

## The idea

The Wall Connector Gen 3 has a built-in dynamic load management feature
(*Home Load Management*) that requires a Neurio meter - discontinued
hardware. LoadPilot replaces it:

- An **ESP32 next to the wallbox** emulates the Neurio meter on the TWC's
  internal RS485 bus (Modbus RTU slave, reply < 66 ms) and feeds it the real
  measurements of your service entrance.
- An **ESP32 next to the utility meter** (France: Linky via the TIC serial
  output) broadcasts per-phase currents and powers over **encrypted UDP**
  (XXTEA, rolling code, port 18511) at ~1 Hz.
- A **Home Assistant integration** (HACS) provides the config flow, derived
  sensors, services and diagnostics - but it is *never* in the safety path.
  Regulation and protection run entirely in firmware and keep working with
  Home Assistant down, the cloud down, or both.

```mermaid
flowchart LR
    subgraph Meter side
        LKY[Utility meter\nLinky TIC / DSMR / SML / CT clamps]
        PROV[Meter provider node\nESP32 - Olimex ESP32-POE + TIC hat]
        LKY -->|native protocol ~1 Hz| PROV
    end

    subgraph Charger side
        CORE[Charger node - ESP32 Kincony KC868-A6\nworst-phase symmetric clamp\nbias+ramp / escalation 120 s / fail-safe]
        TWC[Tesla Wall Connector Gen 3\nModbus RTU master, polls ~200 ms]
        CORE -->|RS485, Neurio emulation\nreply < 66 ms| TWC
        TWC -->|pilot signal| EV[Vehicle\nany brand, guests included]
    end

    PROV -- "UDP :18511, XXTEA\n6 quantities, 1 Hz + deltas\n(PRIMARY)" --> CORE

    subgraph Home Assistant - optional, never in the safety path
        INT[loadpilot integration\nconfig flow / derived sensors\nservices / Repairs]
    end

    PROV -.->|native API entities| INT
    INT -.->|HA mirror = BACKUP source\n+ writes node-resident settings| CORE
    CORE -.->|native API entities| INT
```

## The key result: a control law the wallbox cannot trip on

Nothing about the TWC Gen 3 load-management behaviour is documented by
Tesla. This project **measured it** (firmware 26.18, hundreds of samples,
57 contactor-cut episodes re-analysed): the service loop that modulates the
vehicle is a *symmetric* function of the three published channels, while
the protection that bites and trips watches the *worst* channel. The full
characterisation - each statement labelled MEASURED / INFERRED / REPORTED -
is in [`docs/BEHAVIOR.md`](docs/BEHAVIOR.md) (English) and
[`docs/40_LOI_DE_COMMANDE.md`](docs/40_LOI_DE_COMMANDE.md) (French,
reference version).

The resulting law is memoryless - about 30 lines, one internal timer:

```
avail_p = clamp(contract_limit × (1 − buffer%) − bias − measure_p, 0, L)   per phase
publish = L − min(avail_1, avail_2, avail_3)     identical on all 3 channels
```

- **The protection cannot trip by construction**: the published signal is
  clamped ≤ L (the Max Conductor Limit), so the worst-phase protection never
  sees an excess - bites and contactor trips disappear.
- Publishing the worst phase **symmetrically** means min = mean = max, so
  the service loop engages at the true constraint whatever its exact
  (unknown) functional is.
- A deliberate stop uses **escalation**: after 120 s at zero availability
  the node publishes L + 0.1 to force a clean stop (technique from PVi1,
  confirmed on our hardware).
- **Fail-safe**: no healthy measurement source → the node publishes the main
  breaker value → zero margin → charging blocked, exactly like a dead meter.
  Source priority is UDP > Home Assistant mirror > fail-safe.

Validated in production on 17 Aug 2026: two real load steps (A/C unit, pool
pump) absorbed in smooth modulation, held plateaus below the vehicle's
setpoint, autonomous recovery at ~1 A / 30 s, **zero contactor events**.

The design also stands on documented **negative results**: an estimator-based
"signal synthesizer" was implemented, tested over several nights, fixed six
times, and abandoned - every internal state added had created its own bug.
See [`docs/60_ETUDE_SYNTHETISEUR.md`](docs/60_ETUDE_SYNTHETISEUR.md)
(French) and the summary in [`docs/BEHAVIOR.md`](docs/BEHAVIOR.md).

## Hardware (reference installation, France)

No Tesla imagery is used - wiring is documented with original text diagrams
in [`docs/10_MATERIEL.md`](docs/10_MATERIEL.md).

| Role | Hardware | Notes |
|---|---|---|
| Utility meter | **Linky** (three-phase, TIC *standard* mode, 9600 bd 7E1) | per-phase currents and apparent powers at ~1 Hz |
| Meter node | **Olimex ESP32-POE** + **Hallard "WeMos TeleInfo" hat** | TIC opto-isolated input on GPIO36; Ethernet (LAN8720) |
| Charger node | **Kincony KC868-A6** (ESP32) | RS485 transceiver MAX13487E (auto-direction), TX GPIO27 / RX GPIO14 - the validated reference board; other boards per [`docs/20_FIRMWARE.md`](docs/20_FIRMWARE.md) §2.9 |
| Wallbox | **Tesla Wall Connector Gen 3**, firmware ≥ 26.18 | internal RS485 terminal behind the faceplate; Modbus RTU 115200 8N1 |
| Link | CAT5e, one twisted pair + ground | no 120 Ω termination needed on short runs (validated) |

Other countries: the meter side is pluggable. Any device that ships the six
quantities over the UDP contract is a valid provider - DSMR 5 (NL/BE), SML
(DE/AT, with caveats), universal CT clamps as fallback. Eligibility gate:
per-phase currents at **~1 Hz**. Matrix and provider recipe:
[`docs/15_FOURNISSEURS_MESURE.md`](docs/15_FOURNISSEURS_MESURE.md).

> ## ⚠️ Electrical safety
>
> Wiring the charger node means opening the Wall Connector's faceplate: the
> RS485 terminal sits **next to live 230 V parts**. Switch off the wallbox's
> dedicated breaker before opening it, and the meter-side breaker before any
> work near the service entrance. If you are not comfortable working inside
> an electrical panel, have a qualified electrician do the wiring. You use
> this project **at your own risk**; misconfiguration can defeat load
> management entirely (see the commissioning guide's pitfall list).

## Installation - two channels, one version

LoadPilot ships through two channels that are **released in lockstep** (one
SemVer tag for the whole repo):

1. **The integration** - installed via HACS (custom repository, category
   *Integration*), configured through a config flow.
2. **The firmware** - consumed as ESPHome *remote packages* from this same
   repository, **always pinned to a release tag**:

```yaml
# your charger-node YAML in the ESPHome dashboard
packages:
  loadpilot:
    url: https://github.com/zany92/tesla-loadpilot   # TODO-sync: final owner
    files:
      - esphome/packages/twc-core.yaml
      - esphome/packages/boards/kc868-a6.yaml
    ref: v0.1.0          # ALWAYS a tag, never main
```

The integration compares the firmware's reported package version with its
own and raises a Home Assistant *Repair* on mismatch (it never blocks
regulation).

**France, step by step**: the complete installation guide (TIC wiring,
ESPHome flashing with `secrets.yaml`, Tesla One commissioning, first tests
in shadow mode) is in [`docs/INSTALL_FR.md`](docs/INSTALL_FR.md) (French).

## Compatibility

| Component | Minimum | Why |
|---|---|---|
| Home Assistant | 2025.12 | current config-entry & Repairs APIs |
| ESPHome (both nodes) | 2025.2 | `udp` + `packet_transport` with XXTEA encryption & rolling code |
| TWC Gen 3 firmware | 26.18 (calibration reference) | the entire measured law; **re-calibration required if the wallbox firmware changes** |
| Charger board | Kincony KC868-A6 (validated) | others per matrix in `docs/20_FIRMWARE.md` §2.9 |

`0.x` versioning until the PVi1 attribution agreement is settled and at
least one non-reference installation validates.

## Credits & prior art

- **[PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control)** -
  the founding prior art: the idea of emulating the Neurio meter in ESPHome,
  the Modbus register structure, the "publish slightly above the limit to
  force a stop" escalation technique, and the field proof that a gain < 1
  signal lets the wallbox modulate durably. LoadPilot is an independent
  project, not a fork; a formal attribution agreement with PVi1 is pending
  (see [`LICENSE.placeholder`](LICENSE.placeholder)).
- **[LucaTNT's register-map gist](https://gist.github.com/LucaTNT/4adf01a7252386559070023612efa117)** -
  the Neurio identity block constants used by the emulation.
- Everything else - the RAW publication semantics, the bias/ramp lever, the
  encrypted multi-source UDP link with fail-safe, the 66 ms deadline
  characterisation, and the whole measured control law - is original work of
  this project.

## Roadmap & contributing

- [`docs/ROADMAP.md`](docs/ROADMAP.md) - France → other countries, other
  boards, BLE, richer UI.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) - how to help (testers with non-French
  meters and untested Kincony boards especially welcome). Bug reports
  **must** include the TWC firmware version.
- [`SECURITY.md`](SECURITY.md) - no secrets in this repo, ever; how to
  report a vulnerability.

## License

**TBD.** MIT is the intent, but no license is granted until the attribution
agreement with PVi1 is settled - see
[`LICENSE.placeholder`](LICENSE.placeholder). Until a LICENSE file exists,
all rights are reserved.
