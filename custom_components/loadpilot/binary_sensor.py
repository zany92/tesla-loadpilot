"""Meter-distrust binary sensor for Tesla LoadPilot (axis B4).

binary_sensor.loadpilot_meter_distrust (device_class PROBLEM): on when
the charger has stopped listening to the emulated meter (published value
saturated at L + 0.85 for 120 s while the vehicle still pulls > 9 A).
Logic is pure (control.distrust_step), evaluated on the coordinator tick.
Requires the vehicle-current source: without it the detector is DISABLED,
not degraded (a published-only threshold is structurally false-positive
prone: the 17/08 23:04 false alert, and the firmware stage-2 escalation
legitimately publishes >= L + 0.9).
"""

from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LoadPilotCoordinator
from .entity import LoadPilotBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the meter-distrust binary sensor."""
    coordinator: LoadPilotCoordinator = entry.runtime_data
    async_add_entities([LoadPilotMeterDistrustSensor(coordinator, entry)])


class LoadPilotMeterDistrustSensor(LoadPilotBaseEntity, BinarySensorEntity):
    """Meter distrust suspected (binary_sensor.loadpilot_meter_distrust)."""

    _attr_translation_key = "meter_distrust"
    _attr_suggested_object_id = "loadpilot_meter_distrust"  # language-proof
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: LoadPilotCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_meter_distrust"

    @property
    def available(self) -> bool:
        """Only meaningful with a vehicle-current source configured."""
        return (
            super().available
            and self.coordinator.data.distrust_active is not None
        )

    @property
    def is_on(self) -> Optional[bool]:
        return self.coordinator.data.distrust_active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        since = self.coordinator.distrust_active_since
        published = [
            value
            for value in data.published_current.values()
            if value is not None
        ]
        return {
            "published_max_a": max(published) if published else None,
            "vehicle_current_a": data.vehicle_current_a,
            "active_since": since.isoformat() if since else None,
        }
