"""Tesla LoadPilot — local, cloud-free load management for the Tesla Wall
Connector Gen 3.

The integration configures and observes the ESPHome nodes; the control law
itself lives in firmware and never depends on Home Assistant (see
/ARCHITECTURE.md, decision D2). This package therefore contains NO real-time
logic: config flow, derived sensors, services, diagnostics and Repairs only.

This project is not affiliated with, endorsed by, or sponsored by
Tesla, Inc.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import LoadPilotCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register domain services (config-flow-only integration)."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tesla LoadPilot from a config entry."""
    integration = await async_get_integration(hass, DOMAIN)
    coordinator = LoadPilotCoordinator(hass, entry, integration.version)

    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    # Best-effort push of the configured limits to the node-resident knobs.
    # The node keeps safe flash-restored values if it is offline right now.
    await coordinator.async_apply_config_knobs()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (re-pushes the knobs)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LoadPilotCoordinator = entry.runtime_data
        await coordinator.async_shutdown()
    return unload_ok
