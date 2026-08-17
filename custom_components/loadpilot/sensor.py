"""Derived sensors for Tesla LoadPilot (contract /CONTRACTS.md §3.3).

sensor.loadpilot_state, sensor.loadpilot_headroom_l1/_l2/_l3,
sensor.loadpilot_worst_phase - pure derivations from the charger-node
entities, computed by the coordinator. No control logic here (D2).
"""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PHASES,
    DEFAULT_PHASES,
    DOMAIN,
    PHASE_NAMES,
    STATE_ESCALATING,
    STATE_FAILSAFE,
    STATE_IDLE,
    STATE_OFF,
    STATE_REGULATING,
)
from .coordinator import LoadPilotCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the derived sensors."""
    coordinator: LoadPilotCoordinator = entry.runtime_data
    phases: int = entry.data.get(CONF_PHASES, DEFAULT_PHASES)
    phase_names = PHASE_NAMES[:1] if phases == 1 else PHASE_NAMES

    entities: list[SensorEntity] = [
        LoadPilotStateSensor(coordinator, entry),
        LoadPilotWorstPhaseSensor(coordinator, entry, phase_names),
    ]
    entities.extend(
        LoadPilotHeadroomSensor(coordinator, entry, phase)
        for phase in phase_names
    )
    async_add_entities(entities)


class LoadPilotBaseSensor(
    CoordinatorEntity[LoadPilotCoordinator], SensorEntity
):
    """Common device/base for the derived sensors.

    Entity ids are CONTRACTUAL (/CONTRACTS.md §3.3): every subclass pins an
    English ``_attr_suggested_object_id``. Without it, HA derives the object
    id from the TRANSLATED friendly name at creation time - on a French
    instance sensor.loadpilot_state would be born sensor.loadpilot_etat,
    breaking the dashboards and the docs. ``has_entity_name`` +
    ``translation_key`` stay in place for the DISPLAY name only.
    """

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LoadPilotCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        # Device name "LoadPilot" => entity ids sensor.loadpilot_* (contract).
        device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="LoadPilot",
            manufacturer="Tesla LoadPilot project",
            model="TWC Gen 3 load manager",
        )
        # sw_version omis si inconnu : un None dans le registre des devices
        # casse la comparaison AwesomeVersion (bug vecu au premier run).
        if coordinator.integration_version:
            device_info["sw_version"] = str(coordinator.integration_version)
        self._attr_device_info = device_info


class LoadPilotStateSensor(LoadPilotBaseSensor):
    """Regulation state (contract: sensor.loadpilot_state)."""

    _attr_translation_key = "state"
    _attr_suggested_object_id = "loadpilot_state"  # contract §3.3, language-proof
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        STATE_REGULATING,
        STATE_IDLE,
        STATE_ESCALATING,
        STATE_FAILSAFE,
        STATE_OFF,
    ]

    def __init__(
        self, coordinator: LoadPilotCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_state"

    @property
    def native_value(self) -> Optional[str]:
        return self.coordinator.data.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "source_active": data.source_active,
            "bias_target_a": data.bias_target_a,
            "bias_applied_a": data.bias_applied_a,
            "budget_a": data.budget_a,
            "udp_fresh": data.udp_fresh,
            "polling_active": data.polling_active,
            "fw_version": data.fw_version,
        }


class LoadPilotHeadroomSensor(LoadPilotBaseSensor):
    """Per-phase headroom = budget − measure (contract §3.3)."""

    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: LoadPilotCoordinator,
        entry: ConfigEntry,
        phase: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self._phase = phase
        self._attr_translation_key = f"headroom_{phase}"
        # Contract §3.3, language-proof entity id.
        self._attr_suggested_object_id = f"loadpilot_headroom_{phase}"
        self._attr_unique_id = f"{entry.entry_id}_headroom_{phase}"

    @property
    def native_value(self) -> Optional[float]:
        return self.coordinator.data.headroom.get(self._phase)

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.coordinator.data.headroom.get(self._phase) is not None
        )


class LoadPilotWorstPhaseSensor(LoadPilotBaseSensor):
    """Name of the phase with the least headroom (contract §3.3)."""

    _attr_translation_key = "worst_phase"
    _attr_suggested_object_id = "loadpilot_worst_phase"  # contract §3.3
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        coordinator: LoadPilotCoordinator,
        entry: ConfigEntry,
        phase_names: list[str],
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_options = list(phase_names)
        self._attr_unique_id = f"{entry.entry_id}_worst_phase"

    @property
    def native_value(self) -> Optional[str]:
        return self.coordinator.data.worst_phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"headroom": self.coordinator.data.headroom}
