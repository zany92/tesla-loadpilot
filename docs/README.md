# Documentation map

Two layers, two languages:

- **Guides & reference (English)** — written for the international
  audience of the published module.
- **Characterisation corpus (French)** — the original measurement and
  design documents. They are the project's evidence base and are kept
  verbatim: the MESURÉ / INFÉRÉ / RAPPORTÉ labels and measured values are
  **data, not style**. English companions summarise them; where they
  differ, the French originals prevail.

## English guides

| Document | Purpose |
|---|---|
| [`BEHAVIOR.md`](BEHAVIOR.md) | **The measured behaviour model of the TWC Gen 3 DPM** (fw 26.18) — service loop, protection, plausibility, the distrust state, vehicle session quirks, the resulting control law, the 17 Aug 2026 validation, and the negative results. English companion to `40_LOI_DE_COMMANDE.md` |
| [`ROADMAP.md`](ROADMAP.md) | France → other countries (DSMR 5 next), boards, other EVSEs, BLE, richer UI |
| [`INSTALL_FR.md`](INSTALL_FR.md) | *(French)* Complete France installation guide: TIC wiring, flashing, Tesla One commissioning, shadow-mode first tests, safety warnings |

## French characterisation corpus (reference)

| Document | Contents |
|---|---|
| [`00_SOMMAIRE.md`](00_SOMMAIRE.md) | Original staging plan and decisions log (14 Aug 2026). ⚠️ Its "future repo layout" section is historical — superseded by [`../ARCHITECTURE.md`](../ARCHITECTURE.md) D1 |
| [`10_MATERIEL.md`](10_MATERIEL.md) | Reference BOM, RS485 wiring diagram (original, text-only), network architecture |
| [`15_FOURNISSEURS_MESURE.md`](15_FOURNISSEURS_MESURE.md) | **The UDP meter contract (frozen interface)**, country/meter eligibility matrix, recipe for writing a new provider |
| [`20_FIRMWARE.md`](20_FIRMWARE.md) | Both ESPHome nodes explained: TIC pitfalls (`rx_buffer_size`), the VERBOSE-kills-Modbus trap, Neurio emulation, source priority, bias ramp, per-board matrix (§2.9) |
| [`30_COMMISSIONING_TESLA_ONE.md`](30_COMMISSIONING_TESLA_ONE.md) | The lived Tesla One walkthrough: meter declaration, CT setup, the limit-ordering trap, how to verify the DPM actually acts |
| [`40_LOI_DE_COMMANDE.md`](40_LOI_DE_COMMANDE.md) | **The project's core asset**: the measured control-law model (definitive version, 17 Aug 2026) |
| [`50_COUCHE_HA.md`](50_COUCHE_HA.md) | The Home Assistant layer as a pattern: vehicle-first policy, binary bias lever, anti-yo-yo guards, generalisable lessons — and what stays installation-specific |
| [`60_ETUDE_SYNTHETISEUR.md`](60_ETUDE_SYNTHETISEUR.md) | The signal-synthesizer design study and its epilogue: **the negative results** (six failures, the estimator root cause, the ESPHome API deduplication trap) |
| [`61_SPEC_BUFFER_T2.md`](61_SPEC_BUFFER_T2.md) | Safety-buffer spec (variant B: cushion on the HOUSE margin) and the T2 test protocol |

## Frozen top-level references

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — architecture decisions
  (product form, ESP/HA boundary, generality abstractions, versioning).
- [`../CONTRACTS.md`](../CONTRACTS.md) — team contracts: entity tables,
  service contract, UDP contract pointer. *(French)*
