"""Shared base entity for Tesla LoadPilot platforms.

Extracted from sensor.py (axis B) so number.py and binary_sensor.py share
the same LoadPilot device without duplicating it. Pure refactor: the
device info and the naming rules are byte-identical to the historic
LoadPilotBaseSensor.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LoadPilotCoordinator


class LoadPilotBaseEntity(CoordinatorEntity[LoadPilotCoordinator]):
    """Common device/base for the integration-owned entities.

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
