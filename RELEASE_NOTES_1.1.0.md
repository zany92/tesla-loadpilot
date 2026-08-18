# Tesla LoadPilot 1.1.0

Changes since 1.0.1. One SemVer tag still covers the whole repository:
the HACS integration and the ESPHome firmware packages ship in lockstep.

Theme: **single-phase support, end to end and clearly labelled
THEORETICAL** (meter provider, examples, preset, services, dashboards,
documentation), plus fully bilingual documentation.

**Nothing changes for existing three-phase installations.** The charger-node
firmware is unchanged character for character: `esphome/packages/twc-core.yaml`,
`esphome/packages/providers/teleinfo-fr.yaml`, the board packs and the
three-phase examples have a null git diff against 1.0.1, so the pilot-site
binaries need no reflash. The UDP measurement contract (port 18511, the six
`lky_*` broadcast ids) is untouched. The only behaviour change in the whole
release is the `loadpilot.pause` ceiling described below, and it only
affects single-phase entries.

## Single-phase support (THEORETICAL - never bench-validated)

Scope: European 230 V single-phase, one logical CT. US split-phase (240 V,
two CTs) is a third topology and remains out of scope.

The packages already sketched single-phase (`phase_count: "1"` substitution
in the core, phase choice in the config flow, L1-only mirror). What was
missing to make it usable ships in this release:

- **Single-phase TIC provider**
  `esphome/packages/providers/teleinfo-fr-mono.yaml` (new file; the
  three-phase provider is byte-identical). A single-phase Linky never emits
  the indexed labels the three-phase provider reads (SINSTS1/2/3), so with
  the old provider the UDP feed would never become fresh and the charger
  node would sit in fail-safe forever. The single-phase provider reads
  `SINSTS` (no index) plus `URMS1` and computes sub-amp current as
  SINSTS/URMS1; phases B/C are published at 0, **slaved to the TIC
  watchdog** (0 only while phase A is alive, NAN on all six quantities on
  failure). Constant zeros independent of phase A's health would keep the
  feed judged fresh forever with a dead TIC - the exact resurrection of QA
  pitfall M3. `CONTRACTS.md` section 2 is clarified accordingly (a
  clarification of the existing rule, not an ABI change).
- **Single-phase meter example**
  `esphome/examples/meter-teleinfo-mono-olimex-poe.yaml` (same Olimex
  board as the three-phase reference), and a completed charger example
  `charger-mono-exemple.yaml`: `bias_max_a: "32"`, an electrically
  coherent 45 A service breaker for the 9 kVA example, pointers to the
  single-phase provider and to the commissioning ladder (shadow mode
  first, RAW as short as possible).
- **3 kVA preset** (`mono_3`, 15 A) in the config flow: the single-phase
  series now covers the full Enedis catalogue, 3/6/9/12/15/18/24 kVA.
  Three-phase presets are unchanged value by value.
- **Bias up to 32 A on single-phase entries**: a single-phase TWC Gen 3
  draws up to 32 A on its one phase, and a full pause requires a bias at
  least equal to the vehicle current. `loadpilot.set_bias` now accepts up
  to 32 A on a single-phase entry and still refuses anything above 16 A on
  a three-phase one (the value is validated against every targeted entry
  before being written to any). At the fixed firmware ramp, a full 32 A
  pause takes about 160 s; the `Charge Stop` switch remains the immediate
  lever.
- **Single-phase dashboards**: `dashboards/loadpilot-overview-mono.yaml`
  and `dashboards/loadpilot_card-mono.yaml` (L2/L3 rows removed).
- **Documentation**: single-phase annexes in `docs/en/BEHAVIOR.md`
  section 11 and `docs/fr/40_LOI_DE_COMMANDE.md` section 11 (what is
  structurally invariant versus which numbers are three-phase calibration
  NOT transferred), single-phase commissioning inserts in both INSTALL
  guides, a single-phase provider row in
  `docs/fr/15_FOURNISSEURS_MESURE.md`, and "Single-phase or three-phase"
  configuration paragraphs in both READMEs.

**Why "theoretical"**: no single-phase bench was available at design time.
The control-law constants (dead band, ~20 A.s cut integral, latencies,
slopes, vehicle minimum) are three-phase measurements, and the set of CT
registers a wallbox commissioned single-phase actually reads is unknown.
The bench campaign is declared **OPEN** as TESTPLAN cases **C14-C20**
(CT registers read, `ct_total` acceptance, control-law constants, 32 A
plausibility scale, real single-phase TIC, 32 A bias pause, fail-safe and
Meter Absent). Single-phase support stays theoretical until that campaign
runs; do not trust it on a real installation before then.

## Fixed: `loadpilot.pause` used a hard-coded 16 A ceiling

`loadpilot.pause` now writes the per-installation bias ceiling (16 A
three-phase, 32 A single-phase) instead of a hard-coded 16 A. On a 32 A
single-phase charge, a 16 A bias would only have slowed the vehicle down,
never paused it. This is the only behaviour change of the release and it
only affects single-phase entries: on a three-phase entry the service
writes 16 A exactly as before.

## Documentation is now fully bilingual

- `INSTALL` and `TESTPLAN` translated into English (`docs/en/`).
- `BEHAVIOR` and `RUNBOOK_INCIDENTS` translated into French (`docs/fr/`).
- Cross-links are wired language to language: English pages link `docs/en/`,
  French pages link `docs/fr/`.

## Upgrade notes

- No config-flow migration: existing entries reload as they are. The only
  visible difference on a three-phase entry is one more option (`mono_3`)
  in the preset dropdown.
- Charger-node firmware: byte-identical, no reflash needed, no new
  required substitution (`phase_count` still defaults to `"3"`).
- The `set_bias` service selector now shows 0-32 A; three-phase entries
  still reject anything above 16 A at call time.

This project is not affiliated with, endorsed by, or sponsored by
Tesla, Inc.
