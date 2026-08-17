# Examples — ready-to-copy user entrypoints

Owned by the **HA specialist** (see /CONTRACTS.md).

One minimal YAML per role, importing the repo packages by tag:

- `charger-kc868-a6.example.yaml` — charger node (twc-core + board pack)
- `meter-teleinfo-fr.example.yaml` — French Linky provider (Olimex ESP32-POE)

Rules: substitutions only (no logic here), `!secret` everywhere, `ref:`
pinned to a tag, node names default to `loadpilot-twc` / `loadpilot-meter`
(the entity contract depends on them).
