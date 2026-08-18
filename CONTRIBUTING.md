# Contributing to Tesla LoadPilot

Thanks for your interest! The project is in **private beta**: the control
law is production-validated, the distribution channels (HACS integration +
ESPHome packages) are being built. The most valuable contributions right
now are **field reports** - this is a measurement-driven project.

> This project is not affiliated with, endorsed by, or sponsored by
> Tesla, Inc.

## What we need most

1. **Testers with non-French meters** - DSMR 5 (NL/BE) is candidate #2;
   SML (DE/AT) and CT-clamp setups next. See the provider recipe in
   [`docs/fr/15_FOURNISSEURS_MESURE.md`](docs/fr/15_FOURNISSEURS_MESURE.md) §4.
2. **Testers with untested Kincony boards** (A4/A8/A16, ESP32-S3 core) -
   porting rules and minimal QA checklist in
   [`docs/fr/20_FIRMWARE.md`](docs/fr/20_FIRMWARE.md) §2.9.
3. **Behaviour reports on TWC firmware ≠ 26.18** - every constant in
   [`docs/en/BEHAVIOR.md`](docs/en/BEHAVIOR.md) is calibration data for 26.18.
   If your wallbox behaves differently, that is a finding, not a nuisance.

## Issue policy

**The TWC firmware version is mandatory in every issue.** The whole
behaviour model is calibrated against a specific wallbox firmware; without
that version an observation cannot be interpreted, and the issue will be
sent back for it. Also include:

- charger board (KC868-A6, S3 core, …) and meter provider (Linky TIC
  standard, DSMR, …);
- signal mode at the time (RAW / shadow / active) and the observability
  sensors: `source_active`, poll interval, published vs measured currents,
  applied bias;
- for regulation issues: the contactor lifetime cycle counter before/after,
  and whether `evse_state` reached 9 (vehicle give-up - often mistaken for
  a wallbox fault, see [`docs/en/BEHAVIOR.md`](docs/en/BEHAVIOR.md) §5).

Please do **not** open issues asking how to hack the wallbox beyond its
load-management interface, and never paste secrets (WiFi credentials, API
keys, UDP keys) or precise home location data into an issue.

## Ground rules for code and docs

- **No secrets in the repo, ever** - `!secret` everywhere,
  `esphome/secrets.yaml.example` kept up to date. See
  [`SECURITY.md`](SECURITY.md).
- **The safety path stays in firmware.** Anything that keeps the wallbox
  regulated and the contract safe lives on the ESP32 and works with Home
  Assistant down ([`ARCHITECTURE.md`](ARCHITECTURE.md) D2). PRs moving a
  safety element into HA will be declined.
- The UDP meter contract (port, quantities, cadence, encryption) and the
  entity/service contracts are **frozen interfaces**
  ([`CONTRACTS.md`](CONTRACTS.md)) - propose changes in an issue first.
- The measurement corpus in `docs/` (French) is **data**: MESURÉ/INFÉRÉ/
  RAPPORTÉ labels and measured values are not editable style. Corrections
  require new measurements or a source.
- Languages: English for README, code, HACS-facing docs and dashboards;
  the characterisation corpus stays French with English companion docs.
- Attribution to [PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control)
  and LucaTNT's gist must be preserved in any doc touching the emulation.
  No Tesla imagery, anywhere.

## Licensing note

There is **no LICENSE yet** (see
[`LICENSE`](LICENSE)): publication is blocked on an
attribution agreement with PVi1. By submitting a contribution you accept
that it will be released under the project's eventual OSI-approved license
(MIT intended).
