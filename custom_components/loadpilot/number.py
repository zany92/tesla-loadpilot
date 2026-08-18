"""Charge-cap number for Tesla LoadPilot (axis B1).

number.loadpilot_charge_cap: user-chosen charge ceiling in amps, 0 = auto
(default, no action: the cap loop in the coordinator stays inert). The
loop writes the node bias through the existing channel; the real-time law
stays firmware (D2). Requires the vehicle-current source
(CONF_VEHICLE_CURRENT_ENTITY): the entity is unavailable until that
option is configured.
"""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BIAS_MAX_A,
    BIAS_MAX_MONO_A,
    CONF_PHASES,
    DEFAULT_PHASES,
)
from .coordinator import LoadPilotCoordinator
from .entity import LoadPilotBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the charge-cap number."""
    coordinator: LoadPilotCoordinator = entry.runtime_data
    async_add_entities([LoadPilotChargeCapNumber(coordinator, entry)])


class LoadPilotChargeCapNumber(LoadPilotBaseEntity, RestoreNumber):
    """User charge ceiling (0 = auto). Contract: number.loadpilot_charge_cap."""

    _attr_translation_key = "charge_cap"
    _attr_suggested_object_id = "loadpilot_charge_cap"  # language-proof id
    _attr_icon = "mdi:car-speed-limiter"
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = 0.0
    _attr_native_step = 1.0

    def __init__(
        self, coordinator: LoadPilotCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_charge_cap"
        phases: int = entry.options.get(
            CONF_PHASES, entry.data.get(CONF_PHASES, DEFAULT_PHASES)
        )
        # Same ceiling rule as the bias services: 16 A three-phase,
        # 32 A single-phase.
        self._attr_native_max_value = (
            BIAS_MAX_MONO_A if phases == 1 else BIAS_MAX_A
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last cap and hand it to the coordinator."""
        await super().async_added_to_hass()
        restored = await self.async_get_last_number_data()
        value = 0.0
        if restored is not None and restored.native_value is not None:
            value = float(restored.native_value)
        self.coordinator.set_charge_cap(value)

    @property
    def available(self) -> bool:
        """Unavailable until a vehicle-current source is configured.

        Configuring CONF_VEHICLE_CURRENT_ENTITY (options flow, advanced
        mapping step) makes it available without re-creating the entry.
        """
        return (
            super().available
            and self.coordinator.vehicle_current_entity is not None
        )

    @property
    def native_value(self) -> float:
        return self.coordinator.data.charge_cap_a

    async def async_set_native_value(self, value: float) -> None:
        """Push the cap to the coordinator (forces an immediate tick)."""
        self.coordinator.set_charge_cap(value)
