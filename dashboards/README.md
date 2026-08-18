# Dashboards - Lovelace + UX copy

Owned by the **UX designer** (see /CONTRACTS.md - file list and constraints).

Consumes ONLY the entity/service contract tables from /CONTRACTS.md (never
the specialist's source files). No Tesla imagery of any kind; original SVG
only. English strings by default; French copy delivered through
`UX_COPY.md` for the specialist's `translations/`.

Files:

- `loadpilot-overview.yaml` - full view, three-phase reference.
- `loadpilot-overview-mono.yaml` - single-phase variant (same view, L2/L3
  rows removed, plus the worst-phase row - always L1 on a single phase;
  single-phase support itself is THEORETICAL, never bench-validated).
- `loadpilot_card.yaml` - the everyday master card.
- `loadpilot_card-mono.yaml` - single-phase variant of the master card
  (Headroom L2/L3 rows removed).
