# ESPHome packages (generic firmware) — extraction target

Owned by the **HA specialist** (see /CONTRACTS.md). Users consume these via
ESPHome remote packages pinned to a release tag (see /ARCHITECTURE.md D1).

Target layout:

```
packages/
├── twc-core.yaml            # board-agnostic charger-node core: modbus_server
│                            #   (Neurio/Generac emulation), worst-phase
│                            #   symmetric clamped publication, escalation,
│                            #   fail-safe, source priority UDP>HA>failsafe,
│                            #   bias target+ramp, observability sensors
├── boards/
│   ├── kc868-a6.yaml        # VALIDATED reference (GPIO27/14, MAX13487E, WiFi)
│   ├── esp32-s3-core.yaml   # compiled draft (GPIO16/15, W5500) — untested
│   └── ...                  # per docs/20_FIRMWARE.md §2.9
└── providers/
    ├── teleinfo-fr.yaml     # France Linky TIC standard — production-proven
    ├── dsmr-p1.yaml         # NL/BE — skeleton per docs/15_FOURNISSEURS_MESURE.md
    ├── sml-de.yaml          # DE/AT — skeleton, honest per-phase caveats
    └── ct-clamps.yaml       # universal fallback (ATM90E32 / PZEM)
```

Extraction sources: `esphome/kc868-a6-1.yaml` (charger node, "PVi1-GRADE
17/08" block) and `esphome/olimex-portail.yaml` (provider). Those two files
were only PARTIALLY sanitised (`!secret` for ssid/password/api key, but the
production XXTEA UDP key was committed in clear — see QA B1: history rewrite
and key rotation required before any public push; the files are gone from
the working tree). Treat every extraction as unsanitised until proven
otherwise: NO secret, NO Loupiac-specific entity id, everything variable as
`substitutions`.
Entity names produced here are CONTRACTUAL — table in /CONTRACTS.md.
`twc-core.yaml` must expose `loadpilot_fw_version` (text sensor = package
version) for skew detection.
