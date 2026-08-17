"""Constants for the Tesla LoadPilot integration.

CONTRACTUAL FILE — the names below are the frozen interface shared with the
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
# /CONTRACTS.md — keep the three in sync.
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
# Extensions below (HA specialist) — additive only, nothing above renamed.
# =========================================================================

SERVICE_ATTR_AMPS = "amps"

# The bias number on the charger node spans 0..16 A, step 0.5 (contract §4).
BIAS_MIN_A = 0.0
BIAS_MAX_A = 16.0
BIAS_STEP_A = 0.5

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

# Source-active values published by the firmware text sensor.
SOURCE_UDP = "UDP"
SOURCE_HA = "HA"
SOURCE_FAILSAFE = "FAILSAFE"
SOURCE_OFF = "OFF"
SOURCE_BOOT = "BOOT"

PHASE_NAMES = ["l1", "l2", "l3"]

# --- Repairs issue ids ----------------------------------------------------
ISSUE_FW_VERSION_SKEW = "firmware_version_skew"
ISSUE_SOURCE_FAILSAFE = "source_failsafe"
ISSUE_CHARGER_NODE_MISSING = "charger_node_missing"
