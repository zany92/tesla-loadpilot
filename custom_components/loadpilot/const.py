"""Constants for the Tesla LoadPilot integration.

CONTRACTUAL FILE - the names below are the frozen interface shared with the
dashboards and the documentation (see /CONTRACTS.md). The HA specialist owns
and extends this file, but MUST NOT rename anything listed here without an
architecture decision.
"""

from __future__ import annotations

DOMAIN = "loadpilot"

# --- Config flow / config entry keys -------------------------------------
CONF_CHARGER_NODE = "charger_node"        # ESPHome device name of the TWC node
CONF_METER_NODE = "meter_node"            # ESPHome device name of the provider
CONF_PHASES = "phases"                    # 1 or 3
CONF_CONTRACT_LIMIT_A = "contract_limit_a"  # subscribed limit per phase (A)
CONF_BUFFER_PCT = "buffer_pct"            # safety buffer (%), default below
CONF_MIRROR_ENTITIES = "mirror_entities"  # 6 HA entities (backup measure path)
CONF_COUNTRY_PROFILE = "country_profile"  # provider profile (fr_tic, dsmr, ...)

DEFAULT_BUFFER_PCT = 10
DEFAULT_PHASES = 3

# --- Services (domain loadpilot) -----------------------------------------
SERVICE_SET_BIAS = "set_bias"             # {amps: 0..16, step 0.5}
SERVICE_PAUSE = "pause"                   # binary lever: full bias
SERVICE_RESUME = "resume"                 # bias back to 0

# --- Charger-node entity contract (ESPHome device name: loadpilot-twc) ---
# Entity ids below are produced by esphome/packages/twc-core.yaml and are
# consumed by the integration, the dashboards and the docs. Full table in
# /CONTRACTS.md - keep the three in sync.
CHARGER_NODE_DEFAULT_NAME = "loadpilot-twc"
METER_NODE_DEFAULT_NAME = "loadpilot-meter"

# --- Derived entities owned by the integration ---------------------------
SENSOR_STATE = "state"  # regulating | idle | escalating | failsafe | off
STATE_REGULATING = "regulating"
STATE_IDLE = "idle"
STATE_ESCALATING = "escalating"
STATE_FAILSAFE = "failsafe"
STATE_OFF = "off"

# --- Firmware constants (informational; the LAW LIVES IN FIRMWARE) -------
# Mirrored here only for display/diagnostics. Source of truth:
# esphome/packages/twc-core.yaml and docs/40_LOI_DE_COMMANDE.md.
FW_ESCALATION_DELAY_S = 120               # zero-avail duration before L+0.1
FW_UDP_FRESH_MS = 5000                    # UDP staleness before HA-mirror
FW_MAX_CONDUCTOR_DEFAULT_A = 21           # L, TWC "Max Conductor Limit"

# =========================================================================
# Extensions below (HA specialist) - additive only, nothing above renamed.
# =========================================================================

SERVICE_ATTR_AMPS = "amps"

# The bias number on the charger node spans 0..16 A, step 0.5 (contract §4).
BIAS_MIN_A = 0.0
BIAS_MAX_A = 16.0
BIAS_STEP_A = 0.5
# Single-phase bias ceiling: a full pause requires bias >= vehicle current,
# and a single-phase TWC Gen 3 draws up to 32 A on its one phase
# (7.4 kW / 230 V). Three-phase entries stay bounded by BIAS_MAX_A
# (per-entry validation in services.py); the node itself enforces its own
# `bias_max_a` substitution.
BIAS_MAX_MONO_A = 32.0

DEFAULT_CONTRACT_LIMIT_A = 21.7           # France 15 kVA three-phase

# --- Country / provider profiles (esphome/packages/providers/*) ----------
COUNTRY_PROFILE_FR_TIC = "fr_tic"         # production-proven
COUNTRY_PROFILE_DSMR = "dsmr_p1"          # skeleton
COUNTRY_PROFILE_SML = "sml_de"            # skeleton
COUNTRY_PROFILE_CT = "ct_clamps"          # skeleton
COUNTRY_PROFILES = [
    COUNTRY_PROFILE_FR_TIC,
    COUNTRY_PROFILE_DSMR,
    COUNTRY_PROFILE_SML,
    COUNTRY_PROFILE_CT,
]
DEFAULT_COUNTRY_PROFILE = COUNTRY_PROFILE_FR_TIC

# --- Keys of the mirror-entities mapping (CONF_MIRROR_ENTITIES dict) ------
MIRROR_CURRENT_L1 = "current_l1"
MIRROR_CURRENT_L2 = "current_l2"
MIRROR_CURRENT_L3 = "current_l3"
MIRROR_POWER_L1 = "power_l1"
MIRROR_POWER_L2 = "power_l2"
MIRROR_POWER_L3 = "power_l3"
MIRROR_KEYS = [
    MIRROR_CURRENT_L1,
    MIRROR_CURRENT_L2,
    MIRROR_CURRENT_L3,
    MIRROR_POWER_L1,
    MIRROR_POWER_L2,
    MIRROR_POWER_L3,
]

# --- Charger-node entity suffixes tracked by the coordinator --------------
# entity_id = f"{platform}.{slugified charger_node}_{suffix}"
CHARGER_TRACKED_ENTITIES = {
    # key: (platform, object_id suffix)
    "published_current_l1": ("sensor", "published_current_l1"),
    "published_current_l2": ("sensor", "published_current_l2"),
    "published_current_l3": ("sensor", "published_current_l3"),
    "real_current_l1": ("sensor", "real_current_l1"),
    "real_current_l2": ("sensor", "real_current_l2"),
    "real_current_l3": ("sensor", "real_current_l3"),
    "real_power_l1": ("sensor", "real_power_l1"),
    "real_power_l2": ("sensor", "real_power_l2"),
    "real_power_l3": ("sensor", "real_power_l3"),
    "source_active": ("sensor", "source_active"),
    "udp_age": ("sensor", "udp_age"),
    "udp_fresh": ("binary_sensor", "udp_fresh"),
    "polling_active": ("binary_sensor", "polling_active"),
    "poll_interval": ("sensor", "poll_interval"),
    "bias_target": ("number", "bias_target"),
    "bias_applied": ("sensor", "bias_applied"),
    "contract_limit": ("number", "contract_limit"),
    "buffer_pct": ("number", "buffer_pct"),
    "control_enabled": ("switch", "control_enabled"),
    "escalation_active": ("binary_sensor", "escalation_active"),
    "fw_version": ("sensor", "fw_version"),
}

# --- Entity-mapping overrides (options) -----------------------------------
# Optional per-key remapping of CHARGER_TRACKED_ENTITIES, for nodes whose
# object_ids do not follow the generic contract (historic pilot site).
# Stored in entry.options as {key: full entity_id}. A key absent from the
# dict = generic default; a key mapped to None/"" = entity DECLARED ABSENT
# on the node (tolerated, never tracked).
CONF_ENTITY_OVERRIDES = "entity_overrides"

# The 6 measures the fail-safe judgement relies on (per active phase).
# Any OTHER tracked entity may be declared absent without forcing the
# failsafe state; these six missing = HA genuinely cannot observe the node.
# REFERENCE LIST only: the runtime judge is the coordinator, which derives
# the essentials dynamically PER ACTIVE PHASE (single-phase entries only
# require the L1 pair; this static list is not consumed by the code).
ESSENTIAL_KEYS = [
    "published_current_l1",
    "published_current_l2",
    "published_current_l3",
    "real_current_l1",
    "real_current_l2",
    "real_current_l3",
]

# Source-active values published by the firmware text sensor.
SOURCE_UDP = "UDP"
SOURCE_HA = "HA"
SOURCE_FAILSAFE = "FAILSAFE"
SOURCE_OFF = "OFF"
SOURCE_BOOT = "BOOT"

PHASE_NAMES = ["l1", "l2", "l3"]

# --- Config-flow validation & presets (UX.md §2.3, aligned on firmware) ----
# The number-selector bounds mirror the FIRMWARE knobs (twc-core.yaml):
# contract limit 6..120 A (hardware envelope of the node-resident number),
# buffer 0..30 % (the law clamps at 30 as well - 0..50 in early UX drafts
# was never implementable). The UX "10..100 A" range is a PLAUSIBILITY rule,
# implemented as validation below, not as a hard selector bound.
MIN_CHARGE_BUDGET_A = 8.0        # limit×(1−buffer) under this: the car can never charge (~6 A min + margin)
TRI_LIMIT_SUSPICIOUS_A = 40.0    # 3-phase, per-phase limit above this: probably a kVA or 3-phase-total entry

# French kVA presets (standard Enedis pairs) - input helper ONLY: what is
# stored stays CONF_CONTRACT_LIMIT_A in amps per phase (UX.md §2.3).
# Single-phase starts at 3 kVA (15 A, bottom of the Enedis catalogue;
# 15 A x 0.9 = 13.5 A budget, above the MIN_CHARGE_BUDGET_A floor - a
# marginal but legal contract) and stops at 24 kVA (120 A): 30/36 kVA
# single-phase offers do not exist and would exceed the 120 A firmware
# bound.
CONF_CONTRACT_PRESET = "contract_preset"
CONTRACT_PRESET_CUSTOM = "custom"
CONTRACT_PRESETS_MONO_A = {
    "mono_3": 15.0,
    "mono_6": 30.0,
    "mono_9": 45.0,
    "mono_12": 60.0,
    "mono_15": 75.0,
    "mono_18": 90.0,
    "mono_24": 120.0,
}
CONTRACT_PRESETS_TRI_A = {
    "tri_6": 10.0,
    "tri_9": 15.0,
    "tri_12": 20.0,
    "tri_15": 25.0,
    "tri_18": 30.0,
    "tri_24": 40.0,
    "tri_30": 50.0,
    "tri_36": 60.0,
}
CONTRACT_PRESETS_A = {**CONTRACT_PRESETS_MONO_A, **CONTRACT_PRESETS_TRI_A}
# UX.md §2.0 5-step onboarding: IMPLEMENTED (user -> nodes -> electrical ->
# mirror -> confirm, with charger_not_found/meter_not_found existence checks).
# Still open (post-v0.1.0, tracked in UX_COPY.md §Demandes): ESPHome device
# SELECTORS instead of free-text node names, and the `paused` /
# `charger_current` entity requests.

# --- Repairs issue ids ----------------------------------------------------
ISSUE_FW_VERSION_SKEW = "firmware_version_skew"
ISSUE_SOURCE_FAILSAFE = "source_failsafe"
ISSUE_CHARGER_NODE_MISSING = "charger_node_missing"

# =========================================================================
# Axis B extensions (charge cap / trim / law enforcement / distrust).
# Everything below is OPT-IN: an existing entry with untouched options
# behaves exactly as before (no spontaneous bias write, no new Repair).
# =========================================================================

# Optional options key: full entity_id of a sensor exposing the vehicle
# charging current (device_class current). Deliberately NOT an entry of
# CHARGER_TRACKED_ENTITIES: the correct default for this signal is ABSENT
# (no node publishes it), while that dict's convention is "absent key =
# generic sensor.<slug>_<suffix> default". Absent or empty = the charge
# cap and the distrust detector stay unavailable, the trim stays inert.
CONF_VEHICLE_CURRENT_ENTITY = "vehicle_current_entity"

# Max Conductor Limit (L) commissioned in Tesla One: NOT a node knob, the
# integration can only declare it. Reference of the dead band
# [L+0.05 ; L+0.8] and of the distrust threshold L+0.85.
CONF_MAX_CONDUCTOR_A = "max_conductor_a"
DEFAULT_MAX_CONDUCTOR_TRI_A = 21.0   # field-validated (pilot)
DEFAULT_MAX_CONDUCTOR_MONO_A = 32.0  # theoretical (BEHAVIOR annex §11)

# Convergence trim (B2): opt-in, default OFF - an existing entry must
# never see its bias move on its own.
CONF_TRIM_ENABLED = "trim_enabled"

# Law-settings enforcement (B3): optional option values pushed to the
# node-resident law numbers at setup and on node BOOT (restore_value is
# false on the node: a flash resets the tuning, these options restore it).
# Empty/None = the integration never touches the corresponding number.
CONF_LAW_GAIN_A = "law_gain_a"
CONF_LAW_EXCURSION_A = "law_excursion_a"
CONF_LAW_DRAG_A = "law_drag_a"

# Optional tracked law knobs (NOT essential: they never participate in
# the failsafe judgement; a node without them behaves like a node without
# poll_interval). Suffixes verified against the generic twc-core.yaml
# object_ids: the package names its numbers "Law Echo Gain" and "Law Max
# Excursion" -> number.<slug>_law_echo_gain / _law_max_excursion (the
# historic pilot site remaps them through entity_overrides, mechanics
# already in place).
CHARGER_TRACKED_ENTITIES.update(
    {
        "law_gain": ("number", "law_echo_gain"),
        "law_excursion": ("number", "law_max_excursion"),
        "law_drag": ("number", "law_drag"),
    }
)

# law_drag is a SITE-SPECIFIC OVERRIDE ONLY: the generic twc-core.yaml
# implements the variant A co-variant law and has NO decay-tail (drag)
# number - the knob only exists on variant-B pilot firmware. Keys listed
# here have NO generic default entity: they are tracked (and enforced)
# ONLY when an entity_overrides mapping provides an entity_id, so the
# default enforcement never targets a phantom generic entity.
LAW_OVERRIDE_ONLY_KEYS = ["law_drag"]

# The three law keys the enforcement (B3) can push, with their option.
LAW_KNOB_OPTION_BY_KEY = {
    "law_gain": CONF_LAW_GAIN_A,
    "law_excursion": CONF_LAW_EXCURSION_A,
    "law_drag": CONF_LAW_DRAG_A,
}

# Control tick of the coordinator (slow orchestration policies only; the
# real-time law stays firmware, D2).
CONTROL_TICK_S = 10
# Freshness required from the vehicle-current source (the prototype polls
# at 5 s; the official Wall Connector integration polls ~30 s: x2 margin).
VEHICLE_CURRENT_MAX_AGE_S = 60

# --- Axis B Repairs issue ids ---------------------------------------------
ISSUE_METER_DISTRUST = "meter_distrust"
ISSUE_CHARGE_CAP_INOPERATIVE = "charge_cap_inoperative"
# A law_* option is SET but its target number cannot be resolved (key
# unmapped for an override-only knob, or entity missing on the node):
# the enforcement cannot act. Auto-cleared when the entity appears.
ISSUE_LAW_KNOB_TARGET_MISSING = "law_knob_target_missing"
