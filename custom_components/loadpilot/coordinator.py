"""Coordinator for Tesla LoadPilot.

Observes the ESPHome charger-node entities (push, via state-change events)
and derives the integration-owned values (regulation state, per-phase
headroom, worst phase). The real-time control loop NEVER runs here - it is
firmware (see /ARCHITECTURE.md D2); this coordinator is pure observation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import slugify

from .const import (
    CONF_BUFFER_PCT,
    CONF_CHARGER_NODE,
    CONF_CONTRACT_LIMIT_A,
    CONF_PHASES,
    CHARGER_TRACKED_ENTITIES,
    DEFAULT_BUFFER_PCT,
    DEFAULT_CONTRACT_LIMIT_A,
    DEFAULT_PHASES,
    DOMAIN,
    ISSUE_CHARGER_NODE_MISSING,
    ISSUE_FW_VERSION_SKEW,
    ISSUE_SOURCE_FAILSAFE,
    PHASE_NAMES,
    SOURCE_BOOT,
    SOURCE_FAILSAFE,
    SOURCE_OFF,
    STATE_ESCALATING,
    STATE_FAILSAFE,
    STATE_IDLE,
    STATE_OFF,
    STATE_REGULATING,
)

_LOGGER = logging.getLogger(__name__)

# Safety-net poll: the coordinator is event-driven, this only catches missed
# events (e.g. entity registry churn after an ESPHome rename).
UPDATE_INTERVAL = timedelta(seconds=30)

# Below this measured current (A) on every phase we call the site "idle".
IDLE_CURRENT_THRESHOLD_A = 0.5


@dataclass(slots=True)
class LoadPilotData:
    """Derived snapshot consumed by the integration entities."""

    state: str = STATE_FAILSAFE
    headroom: dict[str, Optional[float]] = field(default_factory=dict)
    worst_phase: Optional[str] = None
    source_active: Optional[str] = None
    contract_limit_a: Optional[float] = None
    buffer_pct: Optional[float] = None
    budget_a: Optional[float] = None
    bias_target_a: Optional[float] = None
    bias_applied_a: Optional[float] = None
    real_current: dict[str, Optional[float]] = field(default_factory=dict)
    published_current: dict[str, Optional[float]] = field(default_factory=dict)
    control_enabled: Optional[bool] = None
    escalation_active: Optional[bool] = None
    udp_fresh: Optional[bool] = None
    polling_active: Optional[bool] = None
    fw_version: Optional[str] = None


class LoadPilotCoordinator(DataUpdateCoordinator[LoadPilotData]):
    """Event-driven coordinator over the charger-node entities."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        integration_version: Optional[str],
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.data[CONF_CHARGER_NODE]}",
            update_interval=UPDATE_INTERVAL,
        )
        self.integration_version = integration_version
        self._charger_slug: str = slugify(entry.data[CONF_CHARGER_NODE])
        self._unsub_state: Optional[CALLBACK_TYPE] = None
        # key -> entity_id map of every tracked charger-node entity.
        self.tracked_entities: dict[str, str] = {
            key: f"{platform}.{self._charger_slug}_{suffix}"
            for key, (platform, suffix) in CHARGER_TRACKED_ENTITIES.items()
        }

    # ------------------------------------------------------------------ setup
    async def async_setup(self) -> None:
        """Subscribe to state changes of the tracked entities."""
        self._unsub_state = async_track_state_change_event(
            self.hass,
            list(self.tracked_entities.values()),
            self._handle_state_change,
        )

    async def async_shutdown(self) -> None:
        """Tear down listeners."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        await super().async_shutdown()

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Recompute the snapshot on any tracked state change."""
        self.async_set_updated_data(self._compute())

    # ---------------------------------------------------------------- helpers
    def _state_str(self, key: str) -> Optional[str]:
        state = self.hass.states.get(self.tracked_entities[key])
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        return state.state

    def _state_float(self, key: str) -> Optional[float]:
        raw = self._state_str(key)
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _state_bool(self, key: str) -> Optional[bool]:
        raw = self._state_str(key)
        if raw is None:
            return None
        return raw == "on"

    # ---------------------------------------------------------------- compute
    async def _async_update_data(self) -> LoadPilotData:
        """Safety-net recompute (event listeners do the real-time work)."""
        return self._compute()

    def _compute(self) -> LoadPilotData:
        """Derive the LoadPilot snapshot from the charger-node states."""
        entry = self.config_entry
        phases: int = entry.options.get(
            CONF_PHASES, entry.data.get(CONF_PHASES, DEFAULT_PHASES)
        )
        phase_names = PHASE_NAMES[:phases] if phases == 1 else PHASE_NAMES

        # Runtime knobs are NODE-RESIDENT (D2): read them from the node,
        # fall back to the config entry only while the node is unavailable.
        contract_limit = self._state_float("contract_limit")
        if contract_limit is None:
            contract_limit = float(
                entry.options.get(
                    CONF_CONTRACT_LIMIT_A,
                    entry.data.get(CONF_CONTRACT_LIMIT_A, DEFAULT_CONTRACT_LIMIT_A),
                )
            )
        buffer_pct = self._state_float("buffer_pct")
        if buffer_pct is None:
            buffer_pct = float(
                entry.options.get(
                    CONF_BUFFER_PCT,
                    entry.data.get(CONF_BUFFER_PCT, DEFAULT_BUFFER_PCT),
                )
            )
        budget = contract_limit * (1.0 - buffer_pct / 100.0)

        real_current: dict[str, Optional[float]] = {}
        published_current: dict[str, Optional[float]] = {}
        headroom: dict[str, Optional[float]] = {}
        for phase in PHASE_NAMES:
            if phase not in phase_names:
                real_current[phase] = None
                published_current[phase] = None
                headroom[phase] = None
                continue
            measure = self._state_float(f"real_current_{phase}")
            real_current[phase] = measure
            published_current[phase] = self._state_float(
                f"published_current_{phase}"
            )
            # Contract §3.3: headroom = budget − measure (per phase, A).
            headroom[phase] = None if measure is None else budget - measure

        worst_phase: Optional[str] = None
        worst_value: Optional[float] = None
        for phase in phase_names:
            value = headroom.get(phase)
            if value is None:
                continue
            if worst_value is None or value < worst_value:
                worst_value = value
                worst_phase = phase

        source = self._state_str("source_active")
        control_enabled = self._state_bool("control_enabled")
        escalation = self._state_bool("escalation_active")

        data = LoadPilotData(
            state=self._derive_state(
                source, control_enabled, escalation, real_current, phase_names
            ),
            headroom=headroom,
            worst_phase=worst_phase,
            source_active=source,
            contract_limit_a=contract_limit,
            buffer_pct=buffer_pct,
            budget_a=budget,
            bias_target_a=self._state_float("bias_target"),
            bias_applied_a=self._state_float("bias_applied"),
            real_current=real_current,
            published_current=published_current,
            control_enabled=control_enabled,
            escalation_active=escalation,
            udp_fresh=self._state_bool("udp_fresh"),
            polling_active=self._state_bool("polling_active"),
            fw_version=self._state_str("fw_version"),
        )
        self._update_issues(data)
        return data

    @staticmethod
    def _derive_state(
        source: Optional[str],
        control_enabled: Optional[bool],
        escalation: Optional[bool],
        real_current: dict[str, Optional[float]],
        phase_names: list[str],
    ) -> str:
        """Map the firmware observables to the contract §3.3 state machine."""
        if control_enabled is False or source == SOURCE_OFF:
            return STATE_OFF
        if source is None or source in (SOURCE_FAILSAFE, SOURCE_BOOT):
            # Unknown source = node unreachable: report the safe truth
            # (firmware publishes main_breaker whenever no source is healthy).
            return STATE_FAILSAFE
        if escalation:
            return STATE_ESCALATING
        measures = [real_current.get(phase) for phase in phase_names]
        if all(
            m is not None and m < IDLE_CURRENT_THRESHOLD_A for m in measures
        ):
            return STATE_IDLE
        return STATE_REGULATING

    # ---------------------------------------------------------------- repairs
    def _update_issues(self, data: LoadPilotData) -> None:
        """Raise/clear Repairs issues (never blocks regulation, D4)."""
        entry_id = self.config_entry.entry_id

        # Charger node entirely absent: NONE of the tracked entities exists
        # in the state machine (never registered / renamed / deleted). This
        # is different from "unavailable" (registered entities keep a state
        # object): it means the configured node name no longer matches
        # anything. The firmware keeps regulating on its own (D2) - HA just
        # cannot observe or adjust it.
        missing_issue = f"{ISSUE_CHARGER_NODE_MISSING}_{entry_id}"
        node_present = any(
            self.hass.states.get(entity_id) is not None
            for entity_id in self.tracked_entities.values()
        )
        if not node_present:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                missing_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key=ISSUE_CHARGER_NODE_MISSING,
                translation_placeholders={
                    "charger_node": self.config_entry.data[CONF_CHARGER_NODE],
                },
                learn_more_url="https://github.com/zany92/tesla-loadpilot",
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, missing_issue)

        # Firmware / integration version skew.
        skew_issue = f"{ISSUE_FW_VERSION_SKEW}_{entry_id}"
        if (
            data.fw_version is not None
            and self.integration_version is not None
            and data.fw_version != self.integration_version
        ):
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                skew_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_FW_VERSION_SKEW,
                translation_placeholders={
                    "fw_version": data.fw_version,
                    "integration_version": self.integration_version,
                },
                learn_more_url="https://github.com/zany92/tesla-loadpilot",
            )
        elif data.fw_version is not None:
            ir.async_delete_issue(self.hass, DOMAIN, skew_issue)

        # Stale sources: the node fell back to fail-safe (charge blocked).
        failsafe_issue = f"{ISSUE_SOURCE_FAILSAFE}_{entry_id}"
        if data.source_active == SOURCE_FAILSAFE:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                failsafe_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_SOURCE_FAILSAFE,
            )
        elif data.source_active is not None:
            ir.async_delete_issue(self.hass, DOMAIN, failsafe_issue)

    # ---------------------------------------------------------------- actions
    async def async_write_number(self, key: str, value: float) -> None:
        """Write a node-resident number entity (best effort, logged)."""
        entity_id = self.tracked_entities[key]
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": value},
            blocking=True,
        )

    async def async_apply_config_knobs(self) -> None:
        """Push config-entry limits to the node-resident knobs (best effort).

        The node HOSTS the knobs (flash-restored); the integration only
        writes them. Failure here must never fail setup: the node keeps its
        last flash-restored values, which are safe by design.
        """
        entry = self.config_entry
        knobs = {
            "contract_limit": entry.options.get(
                CONF_CONTRACT_LIMIT_A,
                entry.data.get(CONF_CONTRACT_LIMIT_A),
            ),
            "buffer_pct": entry.options.get(
                CONF_BUFFER_PCT,
                entry.data.get(CONF_BUFFER_PCT),
            ),
        }
        for key, value in knobs.items():
            if value is None:
                continue
            entity_id = self.tracked_entities[key]
            if self.hass.states.get(entity_id) is None:
                _LOGGER.debug("Knob entity %s not (yet) present", entity_id)
                continue
            try:
                await self.async_write_number(key, float(value))
            except Exception:  # noqa: BLE001 - best effort by design
                _LOGGER.warning(
                    "Could not write %s to %s (node offline?)", value, entity_id
                )

    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Raw tracked states for diagnostics.py."""
        snapshot: dict[str, Any] = {}
        for key, entity_id in self.tracked_entities.items():
            state = self.hass.states.get(entity_id)
            snapshot[key] = {
                "entity_id": entity_id,
                "state": None if state is None else state.state,
            }
        return snapshot
