"""Coordinator for Tesla LoadPilot.

Observes the ESPHome charger-node entities (push, via state-change events)
and derives the integration-owned values (regulation state, per-phase
headroom, worst phase). The real-time control loop NEVER runs here - it is
firmware (see /ARCHITECTURE.md D2); this coordinator is pure observation.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    BIAS_MAX_A,
    BIAS_MAX_MONO_A,
    CONF_BUFFER_PCT,
    CONF_CHARGER_NODE,
    CONF_CONTRACT_LIMIT_A,
    CONF_ENTITY_OVERRIDES,
    CONF_LAW_DRAG_A,
    CONF_LAW_EXCURSION_A,
    CONF_LAW_GAIN_A,
    CONF_MAX_CONDUCTOR_A,
    CONF_PHASES,
    CONF_TRIM_ENABLED,
    CONF_VEHICLE_CURRENT_ENTITY,
    CHARGER_TRACKED_ENTITIES,
    CONTROL_TICK_S,
    DEFAULT_BUFFER_PCT,
    DEFAULT_CONTRACT_LIMIT_A,
    DEFAULT_MAX_CONDUCTOR_MONO_A,
    DEFAULT_MAX_CONDUCTOR_TRI_A,
    DEFAULT_PHASES,
    DOMAIN,
    LAW_KNOB_OPTION_BY_KEY,
    LAW_OVERRIDE_ONLY_KEYS,
    ISSUE_CHARGE_CAP_INOPERATIVE,
    ISSUE_CHARGER_NODE_MISSING,
    ISSUE_FW_VERSION_SKEW,
    ISSUE_LAW_KNOB_TARGET_MISSING,
    ISSUE_METER_DISTRUST,
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
    VEHICLE_CURRENT_MAX_AGE_S,
)
from .control import (
    ControlParams,
    DistrustState,
    TrimInputs,
    TrimState,
    compute_cap_bias_target,
    decide_cap_release,
    decide_cap_write,
    distrust_step,
    trim_step,
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
    # --- Axis B (additive; inert defaults for unconfigured entries) ------
    vehicle_current_a: Optional[float] = None
    vehicle_fresh: bool = False
    charge_cap_a: float = 0.0
    cap_active: bool = False
    distrust_active: Optional[bool] = None  # None = detector unavailable
    trim_phase: str = "idle"


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
        # Optional per-key remapping (historic nodes with non-generic
        # object_ids). Value = FULL entity_id; None/"" = declared absent.
        overrides: dict[str, Any] = (
            entry.options.get(CONF_ENTITY_OVERRIDES) or {}
        )
        self.absent_keys: frozenset[str] = frozenset(
            key
            for key, value in overrides.items()
            if key in CHARGER_TRACKED_ENTITIES and not value
        )
        # key -> entity_id map of every tracked charger-node entity
        # (declared-absent keys are simply never tracked).
        # Override-only keys (law_drag) have NO generic default entity:
        # they are tracked only when entity_overrides maps them.
        self.tracked_entities: dict[str, str] = {
            key: overrides.get(key) or f"{platform}.{self._charger_slug}_{suffix}"
            for key, (platform, suffix) in CHARGER_TRACKED_ENTITIES.items()
            if key not in self.absent_keys
            and (key not in LAW_OVERRIDE_ONLY_KEYS or overrides.get(key))
        }
        # ---- Axis B state (all inert while unconfigured) ----------------
        phases: int = entry.options.get(
            CONF_PHASES, entry.data.get(CONF_PHASES, DEFAULT_PHASES)
        )
        vehicle_entity = entry.options.get(CONF_VEHICLE_CURRENT_ENTITY)
        self.vehicle_current_entity: Optional[str] = vehicle_entity or None
        default_l = (
            DEFAULT_MAX_CONDUCTOR_MONO_A
            if phases == 1
            else DEFAULT_MAX_CONDUCTOR_TRI_A
        )
        self.control_params = ControlParams(
            bias_max_a=BIAS_MAX_MONO_A if phases == 1 else BIAS_MAX_A,
            max_conductor_a=float(
                entry.options.get(CONF_MAX_CONDUCTOR_A, default_l)
            ),
        )
        self.trim_enabled: bool = bool(
            entry.options.get(CONF_TRIM_ENABLED, False)
        )
        self._active_phase_names: list[str] = (
            PHASE_NAMES[:1] if phases == 1 else list(PHASE_NAMES)
        )
        self._unsub_tick: Optional[CALLBACK_TYPE] = None
        self._charge_cap_a: float = 0.0
        self._prev_cap_a: float = 0.0
        self._last_own_bias: Optional[float] = None
        self._trim_state = TrimState()
        self._distrust_state = DistrustState()
        self._distrust_active_since: Optional[datetime] = None
        # BOOT / essentials-return detection for the knob re-application
        # (B3). Flags are SET synchronously by _compute (event path, so a
        # transient BOOT is never missed) and CONSUMED by the async tick.
        self._essentials_seen: Optional[bool] = None
        self._prev_source: Optional[str] = None
        self._reapply_knobs_pending: bool = False
        self._trim_inert_logged: bool = False
        self._tick_running: bool = False

    # ------------------------------------------------------------------ setup
    async def async_setup(self) -> None:
        """Subscribe to state changes and start the control tick."""
        listened = list(self.tracked_entities.values())
        if self.vehicle_current_entity:
            listened.append(self.vehicle_current_entity)
        self._unsub_state = async_track_state_change_event(
            self.hass,
            listened,
            self._handle_state_change,
        )
        # Slow orchestration tick (axis B): cap loop, trim machine,
        # distrust detector, knob re-application. The real-time law stays
        # firmware (D2); with default options this tick produces NO effect.
        self._unsub_tick = async_track_time_interval(
            self.hass,
            self._async_control_tick,
            timedelta(seconds=CONTROL_TICK_S),
        )

    async def async_shutdown(self) -> None:
        """Tear down listeners."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None
        await super().async_shutdown()

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Recompute the snapshot on any tracked state change."""
        self.async_set_updated_data(self._compute())

    # ---------------------------------------------------------------- helpers
    def _state_str(self, key: str) -> Optional[str]:
        entity_id = self.tracked_entities.get(key)
        if entity_id is None:  # declared absent (entity_overrides)
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        return state.state

    def _state_float(self, key: str) -> Optional[float]:
        raw = self._state_str(key)
        if raw is None:
            return None
        try:
            value = float(raw)
        except ValueError:
            return None
        # A sensor publishing "nan"/"inf" parses fine but must never
        # reach the control tick as a number (A3 guard).
        return value if math.isfinite(value) else None

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

        # The 6 ESSENTIAL measures (per active phase): when they all flow,
        # the node is observably alive even if some NON-essential tracked
        # entity is declared absent (entity_overrides) or transiently gone.
        essentials_present = all(
            real_current[phase] is not None
            and published_current[phase] is not None
            for phase in phase_names
        )

        # B3 enforcement: flag the knob re-application on a node BOOT or
        # on the essentials coming back (flash/reboot resets the
        # restore_value:false law numbers). Flag set here (sync event
        # path, transient BOOTs included), consumed by the async tick.
        # RISING EDGE only: one flag per entry INTO BOOT, not one per
        # _compute while the source sits in BOOT.
        if source == SOURCE_BOOT and self._prev_source != SOURCE_BOOT:
            self._reapply_knobs_pending = True
        self._prev_source = source
        if essentials_present and self._essentials_seen is False:
            self._reapply_knobs_pending = True
        self._essentials_seen = essentials_present

        vehicle_a, vehicle_fresh = self._vehicle_snapshot()

        data = LoadPilotData(
            state=self._derive_state(
                source,
                control_enabled,
                escalation,
                real_current,
                phase_names,
                essentials_present,
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
            vehicle_current_a=vehicle_a,
            vehicle_fresh=vehicle_fresh,
            charge_cap_a=self._charge_cap_a,
            cap_active=self._charge_cap_a >= 1.0
            and self.vehicle_current_entity is not None,
            distrust_active=(
                self._distrust_state.active
                if self.vehicle_current_entity
                else None
            ),
            trim_phase=self._trim_state.phase,
        )
        self._update_issues(data)
        return data

    def _vehicle_snapshot(self) -> tuple[Optional[float], bool]:
        """Vehicle current (A) + freshness from the mapped source entity.

        Freshness is judged on ``last_reported`` against
        VEHICLE_CURRENT_MAX_AGE_S (60 s: tolerates the ~30 s poll of the
        official Wall Connector integration with a x2 margin).
        """
        if not self.vehicle_current_entity:
            return None, False
        state = self.hass.states.get(self.vehicle_current_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return None, False
        try:
            value = float(state.state)
        except ValueError:
            return None, False
        if not math.isfinite(value):  # "nan"/"inf" payloads (A3 guard)
            return None, False
        last = state.last_reported or state.last_updated
        fresh = (
            last is not None
            and (dt_util.utcnow() - last).total_seconds()
            < VEHICLE_CURRENT_MAX_AGE_S
        )
        return value, fresh

    @staticmethod
    def _published_max(data: LoadPilotData) -> Optional[float]:
        """Max of the published currents over the active phases.

        The pilot prototype reads L1 only; the firmware publication being
        symmetric by design, max == L1 there. The max() form is the
        strictly more robust generic reading (theoretical).
        """
        values = [
            value
            for value in data.published_current.values()
            if value is not None
        ]
        return max(values) if values else None

    @staticmethod
    def _derive_state(
        source: Optional[str],
        control_enabled: Optional[bool],
        escalation: Optional[bool],
        real_current: dict[str, Optional[float]],
        phase_names: list[str],
        essentials_present: bool,
    ) -> str:
        """Map the firmware observables to the contract §3.3 state machine."""
        if control_enabled is False or source == SOURCE_OFF:
            return STATE_OFF
        if source in (SOURCE_FAILSAFE, SOURCE_BOOT):
            return STATE_FAILSAFE
        if source is None and not essentials_present:
            # No source telemetry AND the essential measures are gone: the
            # node is unreachable, report the safe truth (firmware publishes
            # main_breaker whenever no source is healthy). When the six
            # essentials still flow, a missing source_active alone (declared
            # absent via entity_overrides, or transient) must NOT force
            # failsafe - the failsafe judgement rests on the essentials.
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

        # Meter distrust suspected (B4): the charger stopped listening to
        # the emulated meter. Informational, auto-cleared on release
        # (same pattern as source_failsafe).
        distrust_issue = f"{ISSUE_METER_DISTRUST}_{entry_id}"
        if data.distrust_active is True:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                distrust_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_METER_DISTRUST,
                learn_more_url=(
                    "https://github.com/zany92/tesla-loadpilot"
                    "/blob/main/docs/en/BEHAVIOR.md"
                ),
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, distrust_issue)

        # Charge cap restored > 0 while the vehicle-current key was
        # removed: the cap is inoperative. Informational, auto-cleared
        # when the key comes back (or the cap returns to 0). This is the
        # ONLY unconfigured-state Repair: a plain unconfigured entry
        # (cap 0) never gets notified about an opt-in it never asked for.
        cap_issue = f"{ISSUE_CHARGE_CAP_INOPERATIVE}_{entry_id}"
        if data.charge_cap_a >= 1.0 and self.vehicle_current_entity is None:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                cap_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_CHARGE_CAP_INOPERATIVE,
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, cap_issue)

        # A law_* option is set but its target number cannot be resolved
        # (override-only key left unmapped, or entity missing on the
        # node): the enforcement cannot act. Auto-cleared as soon as the
        # entity appears (this runs on every recompute).
        law_issue = f"{ISSUE_LAW_KNOB_TARGET_MISSING}_{entry_id}"
        missing = self._missing_law_knob_targets()
        if missing:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                law_issue,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_LAW_KNOB_TARGET_MISSING,
                translation_placeholders={"knobs": ", ".join(missing)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, law_issue)

    def _missing_law_knob_targets(self) -> list[str]:
        """Law keys whose option is SET but whose target is unresolvable."""
        missing: list[str] = []
        for key, option in LAW_KNOB_OPTION_BY_KEY.items():
            if self.config_entry.options.get(option) is None:
                continue
            entity_id = self.tracked_entities.get(key)
            if entity_id is None or self.hass.states.get(entity_id) is None:
                missing.append(key)
        return missing

    # ----------------------------------------------------------- control tick
    @callback
    def set_charge_cap(self, value: float) -> None:
        """Store the user cap (charge-cap number) and tick immediately."""
        self._charge_cap_a = float(value)
        self.async_set_updated_data(self._compute())
        self.hass.async_create_task(self._async_control_tick())

    async def _async_control_tick(
        self, _now: Optional[datetime] = None
    ) -> None:
        """One CONTROL_TICK_S step: snapshot, pure policies, effects.

        At most ONE bias write per tick (axis B invariant 7). With default
        options (no vehicle source, trim off, cap 0) this produces no
        effect at all (invariant 1): the firmware stays sovereign (D2).
        """
        if self._tick_running:
            return
        self._tick_running = True
        try:
            await self._async_control_tick_locked()
        finally:
            self._tick_running = False

    async def _async_control_tick_locked(self) -> None:
        # B3: deferred knob re-application (node BOOT / essentials back:
        # a flash resets the restore_value:false law numbers, the options
        # restore them within seconds). Best effort, never blocking.
        if self._reapply_knobs_pending:
            self._reapply_knobs_pending = False
            await self.async_apply_config_knobs()

        data = self.data
        if data is None:
            return

        now_mono = time.monotonic()
        params = self.control_params
        vehicle_a, vehicle_fresh = self._vehicle_snapshot()
        published_max = self._published_max(data)
        current_bias = self._state_float("bias_target")
        worst = (
            data.headroom.get(data.worst_phase)
            if data.worst_phase is not None
            else None
        )
        # Without the vehicle source the cap is INOPERATIVE (entity
        # unavailable): treat it as 0 so the loop stays inert.
        cap = self._charge_cap_a if self.vehicle_current_entity else 0.0
        wrote_bias = False

        # B4: distrust detector (DISABLED, not degraded, without the
        # vehicle source: a published-only threshold is structurally
        # false-positive prone, 17/08 23:04 and the firmware stage 2).
        if self.vehicle_current_entity:
            new_distrust = distrust_step(
                self._distrust_state,
                published_max,
                vehicle_a if vehicle_fresh else None,
                now_mono,
                params,
            )
            if new_distrust.active != self._distrust_state.active:
                self._distrust_active_since = (
                    dt_util.utcnow() if new_distrust.active else None
                )
            self._distrust_state = new_distrust

        # B1: cap loop. Impure guards here (cap >= 1, freshness,
        # headroom available, bias readable); ownership guard, dead band,
        # kick and asymmetry are pure (control.py).
        if cap >= 1.0:
            if (
                vehicle_a is not None
                and vehicle_fresh
                and worst is not None
                and current_bias is not None
            ):
                target = compute_cap_bias_target(
                    worst, vehicle_a, cap, params
                )
                write = (
                    decide_cap_write(
                        target,
                        current_bias,
                        self._last_own_bias,
                        vehicle_a,
                        cap,
                        published_max,
                        params,
                    )
                    if target is not None
                    else None
                )
                if write is not None:
                    await self.async_write_number("bias_target", write)
                    self._last_own_bias = write
                    wrote_bias = True
        elif self._prev_cap_a >= 1.0 and current_bias is not None:
            # Cap just went back to 0: conditional release. Write bias 0
            # ONLY when the current bias is ours (a pause or an external
            # shedding wins otherwise).
            release = decide_cap_release(current_bias, self._last_own_bias)
            if release is not None and current_bias > 0:
                await self.async_write_number("bias_target", release)
                wrote_bias = True
            self._last_own_bias = None
        self._prev_cap_a = cap

        # B2: trim state machine (opt-in, default OFF). Without the
        # vehicle source the machine is inert (the option stays visible).
        if not wrote_bias:
            if self.trim_enabled and not self.vehicle_current_entity:
                if not self._trim_inert_logged:
                    _LOGGER.debug(
                        "Trim enabled but no vehicle_current_entity is "
                        "configured: the trim state machine stays inert "
                        "(the 'real charge > 6.5 A' guard needs it)"
                    )
                    self._trim_inert_logged = True
            inputs = TrimInputs(
                enabled=self.trim_enabled
                and self.vehicle_current_entity is not None,
                cap_a=cap,
                state=data.state,
                distrust=(
                    self._distrust_state.active
                    if self.vehicle_current_entity
                    else None
                ),
                worst_headroom_a=worst,
                published_max_a=published_max,
                current_bias_a=current_bias,
                vehicle_current_a=vehicle_a,
                vehicle_fresh=vehicle_fresh,
            )
            new_trim, trim_write = trim_step(
                self._trim_state, inputs, now_mono, params
            )
            if trim_write is not None:
                await self.async_write_number("bias_target", trim_write)
                wrote_bias = True
            self._trim_state = new_trim

        # Publish the refreshed derived snapshot if anything changed.
        new_data = self._compute()
        if new_data != self.data:
            self.async_set_updated_data(new_data)

    def control_snapshot(self) -> dict[str, Any]:
        """Axis-B control state for diagnostics.py."""
        return {
            "vehicle_current_entity_configured": bool(
                self.vehicle_current_entity
            ),
            "charge_cap_a": self._charge_cap_a,
            "last_own_bias_a": self._last_own_bias,
            "trim_enabled": self.trim_enabled,
            "trim_phase": self._trim_state.phase,
            "distrust_active": (
                self._distrust_state.active
                if self.vehicle_current_entity
                else None
            ),
            "distrust_active_since": (
                self._distrust_active_since.isoformat()
                if self._distrust_active_since
                else None
            ),
            "max_conductor_a": self.control_params.max_conductor_a,
            "bias_max_a": self.control_params.bias_max_a,
        }

    @property
    def distrust_active_since(self) -> Optional[datetime]:
        """Wall-clock start of the current distrust episode (or None)."""
        return self._distrust_active_since

    # ---------------------------------------------------------------- actions
    async def async_write_number(self, key: str, value: float) -> None:
        """Write a node-resident number entity (best effort, logged)."""
        entity_id = self.tracked_entities.get(key)
        if entity_id is None:  # declared absent (entity_overrides)
            _LOGGER.warning(
                "Cannot write %s: entity declared absent on this node", key
            )
            return
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
            # B3 law-settings enforcement: only when the option is set
            # (None is skipped below = the integration never touches the
            # corresponding number, exactly the pre-axis-B behaviour).
            "law_gain": entry.options.get(CONF_LAW_GAIN_A),
            "law_excursion": entry.options.get(CONF_LAW_EXCURSION_A),
            "law_drag": entry.options.get(CONF_LAW_DRAG_A),
        }
        for key, value in knobs.items():
            if value is None:
                continue
            entity_id = self.tracked_entities.get(key)
            if entity_id is None:
                # Declared absent (entity_overrides) or override-only key
                # (law_drag) left unmapped. For a law knob the user SET a
                # value: elevate the silent skip (a Repairs issue
                # law_knob_target_missing is raised alongside).
                if key in LAW_KNOB_OPTION_BY_KEY:
                    _LOGGER.warning(
                        "Law knob %s is configured (value %s) but has no "
                        "target entity on this node (unmapped or declared "
                        "absent): enforcement skipped",
                        key,
                        value,
                    )
                else:
                    _LOGGER.debug("Knob %s declared absent on this node", key)
                continue
            if self.hass.states.get(entity_id) is None:
                if key in LAW_KNOB_OPTION_BY_KEY:
                    _LOGGER.warning(
                        "Law knob %s is configured (value %s) but its "
                        "target entity %s is missing right now: "
                        "enforcement skipped",
                        key,
                        value,
                        entity_id,
                    )
                else:
                    _LOGGER.debug(
                        "Knob entity %s not (yet) present", entity_id
                    )
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
        for key in self.absent_keys:
            snapshot[key] = {"entity_id": None, "state": "absent (override)"}
        return snapshot
