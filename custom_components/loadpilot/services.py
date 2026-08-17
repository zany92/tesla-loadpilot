"""Services for Tesla LoadPilot (contract /CONTRACTS.md §4).

loadpilot.set_bias / loadpilot.pause / loadpilot.resume all write the bias
TARGET number on the charger node. The RAMP (and every protection) stays
firmware - these services are convenience levers only.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    BIAS_MAX_A,
    BIAS_MIN_A,
    BIAS_STEP_A,
    DOMAIN,
    SERVICE_ATTR_AMPS,
    SERVICE_PAUSE,
    SERVICE_RESUME,
    SERVICE_SET_BIAS,
)
from .coordinator import LoadPilotCoordinator

_LOGGER = logging.getLogger(__name__)


def _validate_step(value: float) -> float:
    """Enforce the 0.5 A step of the firmware number entity."""
    if round(value / BIAS_STEP_A) * BIAS_STEP_A != value:
        raise vol.Invalid(f"amps must be a multiple of {BIAS_STEP_A}")
    return value


SET_BIAS_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_AMPS): vol.All(
            vol.Coerce(float),
            vol.Range(min=BIAS_MIN_A, max=BIAS_MAX_A),
            _validate_step,
        )
    }
)


def _coordinators(hass: HomeAssistant) -> list[LoadPilotCoordinator]:
    """Every loaded LoadPilot coordinator (usually exactly one)."""
    coordinators = [
        entry.runtime_data
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if isinstance(entry.runtime_data, LoadPilotCoordinator)
    ]
    if not coordinators:
        raise HomeAssistantError("No LoadPilot config entry is loaded")
    return coordinators


async def _async_write_bias(hass: HomeAssistant, amps: float) -> None:
    for coordinator in _coordinators(hass):
        await coordinator.async_write_number("bias_target", amps)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the loadpilot.* services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_BIAS):
        return

    async def handle_set_bias(call: ServiceCall) -> None:
        await _async_write_bias(hass, call.data[SERVICE_ATTR_AMPS])

    async def handle_pause(call: ServiceCall) -> None:
        # Full bias = clean charge pause (the firmware escalation forces a
        # proper stop after 120 s at zero availability).
        await _async_write_bias(hass, BIAS_MAX_A)

    async def handle_resume(call: ServiceCall) -> None:
        # Bias back to 0. The anti-yo-yo/projection guard is a later HA
        # policy, deliberately NOT v0 (contract §4).
        await _async_write_bias(hass, BIAS_MIN_A)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_BIAS, handle_set_bias, schema=SET_BIAS_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_PAUSE, handle_pause)
    hass.services.async_register(DOMAIN, SERVICE_RESUME, handle_resume)
