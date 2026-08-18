# Examples - ready-to-copy user entrypoints

Owned by the **HA specialist** (see /CONTRACTS.md).

One minimal YAML per role, importing the repo packages by tag:

- `charger-kc868-a6.yaml` - charger node, three-phase reference
  (twc-core + board pack)
- `charger-mono-exemple.yaml` - charger node, single-phase variant
  (`phase_count: "1"`, `bias_max_a: "32"`, L1-only mirror)
- `meter-teleinfo-olimex-poe.yaml` - French Linky provider (Olimex ESP32-POE)
- `meter-teleinfo-mono-olimex-poe.yaml` - French Linky SINGLE-PHASE provider
  (same board; SINSTS without index + URMS1, B/C zeros watchdog-slaved)

Single-phase reminder: the whole single-phase chain is THEORETICAL - never
validated on a bench (docs/en/TESTPLAN.md, single-phase campaign).

Rules: substitutions only (no logic here), `!secret` everywhere, `ref:`
pinned to a tag, node names default to `loadpilot-twc` / `loadpilot-meter`
(the entity contract depends on them).
