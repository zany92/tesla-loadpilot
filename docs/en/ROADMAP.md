# Roadmap

> Status labels: **done** (validated in production), **in progress**,
> **planned** (designed, not started), **investigating** (open question).
> Nothing here is a commitment - this is a hobby-scale project with a
> production-grade reference installation. This project is not affiliated
> with Tesla, Inc.

## 0.x - make the reference installation shippable (in progress)

- [x] Measured behaviour model of the TWC Gen 3 DPM (fw 26.18) -
  [`BEHAVIOR.md`](BEHAVIOR.md) / [`40_LOI_DE_COMMANDE.md`](../fr/40_LOI_DE_COMMANDE.md) - **done**
- [x] Memoryless control law (worst-phase symmetric clamped publication,
  escalation, fail-safe) validated in production 17 Aug 2026 - **done**
- [x] Encrypted UDP meter contract (port 18511, XXTEA + rolling code,
  6 quantities, 1 Hz) with France/Linky provider - **done, production**
- [ ] Extract generic ESPHome packages (`twc-core.yaml`,
  `boards/kc868-a6.yaml`, `providers/teleinfo-fr.yaml`) from the reference
  firmware - **in progress**
- [ ] `loadpilot` HACS integration: config flow, derived sensors
  (state / headroom / worst phase), services (`set_bias`, `pause`,
  `resume`), diagnostics, Repairs (version skew, stale sources), EN + FR
  translations - **in progress**
- [ ] Lovelace overview dashboard (core cards only) - **in progress**
- [ ] Settle the **PVi1 attribution agreement** and publish a real LICENSE
  (MIT intended) - **blocking for any public release**, see
  [`../LICENSE.placeholder`](../LICENSE.placeholder)
- [ ] First non-reference installation validates → exit criteria for 1.0

## Meter providers - France first, then the matrix

Full eligibility matrix (cadence is the gate: per-phase currents at ~1 Hz):
[`15_FOURNISSEURS_MESURE.md`](../fr/15_FOURNISSEURS_MESURE.md).

| Provider | Countries | Status |
|---|---|---|
| Linky TIC standard (`teleinfo`) | FR | **done - production reference** |
| **DSMR 5 / P1 port (`dsmr`) - candidate #2** | NL, BE (+ Scandinavian variants) | **planned** - 1 s telegrams, per-phase current and power in the standard: the easiest eligible port of the whole matrix. Skeleton to write, needs an in-country tester |
| SML IR head (`sml`) | DE, AT | **planned, with honest caveats** - cadence varies by meter (1–4 s), PIN often required, many meters expose TOTAL power only (per-phase reconstruction degraded or impossible → CT clamps recommended) |
| CT clamps (Shelly Pro 3EM local push, ATM90E32, PZEM) | any country | **planned** - the universal fallback where the national meter is ineligible (DSMR 4 at 10 s, Luxembourg Smarty, UK SMETS with no consumer port) |
| Linky TIC historical mode | FR (legacy) | **not planned as a target** - integer amps, no per-phase power; documented as degraded, standard mode is the fix |

Country quirks stay inside the provider; the only generic optional signal
is `meter_overload` (France: Linky STGE register bit 7, "overrun in
progress" as seen by the meter itself).

## Charger boards (Kincony family and beyond)

Matrix and porting rules: [`20_FIRMWARE.md`](../fr/20_FIRMWARE.md) §2.9. The
core is board-agnostic; a board pack is pins + transceiver + network only.

| Board | Status |
|---|---|
| Kincony KC868-A6 | **done - validated production reference** |
| Kincony ESP32-S3 core (W5500 Ethernet) | **drafted** - compiles, never wired to a wallbox |
| Kincony KC868-A16 | **investigating** - RS485 pins to confirm |
| Kincony KC868-A4 / A8 | **investigating** - RS485 pins not clearly published |

Porting requirement worth repeating: auto-direction RS485 transceivers
strongly preferred - the ~66 ms Modbus reply deadline leaves no margin for
a badly timed DE/RE switch.

## Other chargers / EVSEs

**Investigating (post-1.0).** The architecture already isolates this: a
ChargerBackend consumes the 6 quantities + a limit and exposes published
values. A future non-TWC EVSE (e.g. a generic Modbus smart-meter-input
EVSE) would be a **new core package**, not a fork of `twc-core.yaml`. No
concrete target selected; the TWC Gen 3 / Neurio emulation is the only
implementation for the foreseeable future.

## Vehicle-side orchestration

- **Bias lever (any vehicle, no cloud)** - **done** in firmware: the
  universal binary lever (pause = full bias, resume = bias 0) with ramp
  and contactor-open immediate apply.
- **Vehicle-first policy in HA** (proportional API setpoint for the owned
  vehicle, anti-yo-yo guard, demand memo + projected release) -
  **documented as a pattern** in [`50_COUCHE_HA.md`](../fr/50_COUCHE_HA.md);
  the reference implementation is installation-specific and will not ship
  as-is. Candidate for later blueprints/add-ons - explicitly *not* the
  product's spine.
- **Tesla BLE control** - **investigating**: would replace the cloud Fleet
  API for owned-vehicle fine modulation (local-only, no per-command
  billing). Not in the shipped product yet; the wallbox-side law does not
  depend on it.

## Richer interface

- **planned**: Lovelace overview shipped in-repo (regulation state,
  published vs measured per phase, headroom, active source, bias,
  escalation, pause/resume) - core HA cards only, no mandatory third-party
  dependencies.
- **investigating**: optional Mushroom variant, extra badges/cards, config
  flow polish (per-country presets: contract sizes → per-phase limits).

## Risks and external dependencies (tracked)

The project sits on two firmwares it does not control; these are the known
ways they can move under us.

- **Tesla may harden the plausibility layer.** The distrust state
  ([`BEHAVIOR.md`](BEHAVIOR.md) §4) is an undocumented behaviour, present
  since at least fw 25.x per community reports and characterised by us on
  26.18. Any wallbox OTA can tighten the correlation check (or shift the
  calibration constants) and silently degrade regulation. Mitigation:
  freeze wallbox updates where possible, mandatory firmware version in
  every report, re-run the [`BEHAVIOR.md`](BEHAVIOR.md) §8 validation
  after any update.
- **The commissioning door can close.** Meter activation is locked behind
  installer credentials since ~fw 26.2.0; the working bypass (generic
  Tesla account → More → "Tesla device settings", validated on 26.18) is
  unofficial and revocable by Tesla at any update. This is a fragile
  dependency of the whole install path - documented in
  [`INSTALL_FR.md`](../fr/INSTALL.md) §4.
- **ESPHome breaking changes.** The community has already been bitten:
  ESPHome 2026.5.1 broke a comparable project's YAML via the
  `modbus_controller` → `modbus_server` migration (Klangen82's repo,
  issue #9). Mitigation: releases pin firmware + integration on the same
  tag, and the ESPHome minimum version is part of the release notes.
- **"Cure window" (auto-SHADOW) - investigating.** Recovery from the
  distrust state was observed after hours of honest raw publication
  (shadow mode). If the trust-score hypothesis holds, a deliberate
  automatic cure window (fall back to SHADOW on distrust detection, dwell
  on the honest signal, then re-engage) becomes the recovery mechanism.
  Under validation on the reference installation - not designed into the
  shipped firmware yet.

## Explicit non-goals (v0.x)

From [`../ARCHITECTURE.md`](../../ARCHITECTURE.md):

- No solar/export management (reference install is import-only, GRID mode).
- No vehicle cloud API in the shipped product.
- No YAML-only install path for the integration (config flow only).
- No Tesla imagery, ever.

## Manual hard limit (validated pattern, pilot site, 18 Aug 2026)

A user-chosen charge ceiling (N amps, independent of the vehicle's own
setting), implemented WITHOUT synthesizing a decorrelated meter signal
(that path latches distrust, see BEHAVIOR section 4). Instead it reuses
the node's bias channel: every 30 s, Home Assistant computes
bias_target = worst_phase_headroom + vehicle_current(local vitals) − limit
and writes it to the bias number; the node's own anti-trip ramp applies
it. The Linky echo stays 1:1 (vitals freshness only affects the slow
offset, never the correlation), and every protection layer stays active,
so the limit acts as a cap: the car draws min(limit, what the house
leaves). Candidate for productization in the integration (needs the
vitals integration or any per-vehicle current source).
