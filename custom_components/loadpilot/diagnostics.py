"""Diagnostics support for Tesla LoadPilot."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import LoadPilotCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Nothing here is secret by design: node names, limits and entity states.
    """
    coordinator: LoadPilotCoordinator = entry.runtime_data
    return {
        "entry": {
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "integration_version": coordinator.integration_version,
        "derived": asdict(coordinator.data),
        "tracked_entities": coordinator.diagnostics_snapshot(),
        "control": coordinator.control_snapshot(),
    }
