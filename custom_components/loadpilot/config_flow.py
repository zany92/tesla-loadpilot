"""Config flow for Tesla LoadPilot.

Field labels/descriptions come from translations/ — the UX designer owns the
copy (dashboards/UX_COPY.md); this module only defines keys and validation.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import slugify

from .const import (
    CHARGER_NODE_DEFAULT_NAME,
    CONF_BUFFER_PCT,
    CONF_CHARGER_NODE,
    CONF_CONTRACT_LIMIT_A,
    CONF_COUNTRY_PROFILE,
    CONF_METER_NODE,
    CONF_MIRROR_ENTITIES,
    CONF_PHASES,
    COUNTRY_PROFILES,
    DEFAULT_BUFFER_PCT,
    DEFAULT_CONTRACT_LIMIT_A,
    DEFAULT_COUNTRY_PROFILE,
    DEFAULT_PHASES,
    DOMAIN,
    METER_NODE_DEFAULT_NAME,
    MIRROR_KEYS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CHARGER_NODE, default=CHARGER_NODE_DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_METER_NODE, default=METER_NODE_DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_PHASES, default=str(DEFAULT_PHASES)): SelectSelector(
            SelectSelectorConfig(
                options=["1", "3"],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="phases",
            )
        ),
        vol.Required(
            CONF_COUNTRY_PROFILE, default=DEFAULT_COUNTRY_PROFILE
        ): SelectSelector(
            SelectSelectorConfig(
                options=COUNTRY_PROFILES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="country_profile",
            )
        ),
    }
)


def _limits_schema(
    contract_limit: float = DEFAULT_CONTRACT_LIMIT_A,
    buffer_pct: int = DEFAULT_BUFFER_PCT,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_CONTRACT_LIMIT_A, default=contract_limit
            ): NumberSelector(
                NumberSelectorConfig(
                    min=6,
                    max=120,
                    step=0.1,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_BUFFER_PCT, default=buffer_pct): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=30,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _mirror_schema(defaults: Optional[dict[str, str]] = None) -> vol.Schema:
    """Optional 6-entity backup measure path (mirror wiring is documented,
    physically configured in the ESPHome substitutions)."""
    defaults = defaults or {}
    schema: dict[Any, Any] = {}
    for key in MIRROR_KEYS:
        device_class = "current" if key.startswith("current") else "apparent_power"
        marker = (
            vol.Required(key, default=defaults[key])
            if key in defaults
            else vol.Optional(key)
        )
        schema[marker] = EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class=device_class)
        )
    return vol.Schema(schema)


class LoadPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the LoadPilot config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 1 — node names, phase topology, country profile."""
        errors: dict[str, str] = {}
        if user_input is not None:
            charger_node = user_input[CONF_CHARGER_NODE].strip()
            await self.async_set_unique_id(slugify(charger_node))
            self._abort_if_unique_id_configured()
            self._data = {
                CONF_CHARGER_NODE: charger_node,
                CONF_METER_NODE: user_input[CONF_METER_NODE].strip(),
                CONF_PHASES: int(user_input[CONF_PHASES]),
                CONF_COUNTRY_PROFILE: user_input[CONF_COUNTRY_PROFILE],
            }
            return await self.async_step_limits()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_limits(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 2 — electrical limits (written to the node-resident knobs)."""
        if user_input is not None:
            self._data[CONF_CONTRACT_LIMIT_A] = float(
                user_input[CONF_CONTRACT_LIMIT_A]
            )
            self._data[CONF_BUFFER_PCT] = int(user_input[CONF_BUFFER_PCT])
            return await self.async_step_mirror()

        return self.async_show_form(
            step_id="limits", data_schema=_limits_schema()
        )

    async def async_step_mirror(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 3 — optional HA-mirror entities (backup measure path)."""
        if user_input is not None:
            self._data[CONF_MIRROR_ENTITIES] = {
                key: user_input[key] for key in MIRROR_KEYS if key in user_input
            }
            return self.async_create_entry(
                title=self._data[CONF_CHARGER_NODE], data=self._data
            )

        return self.async_show_form(
            step_id="mirror", data_schema=_mirror_schema()
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "LoadPilotOptionsFlow":
        """Return the options flow."""
        return LoadPilotOptionsFlow()


class LoadPilotOptionsFlow(OptionsFlow):
    """Runtime-adjustable options (limits + mirror entities)."""

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Single options step."""
        entry = self.config_entry
        if user_input is not None:
            options = {
                CONF_CONTRACT_LIMIT_A: float(user_input[CONF_CONTRACT_LIMIT_A]),
                CONF_BUFFER_PCT: int(user_input[CONF_BUFFER_PCT]),
                CONF_MIRROR_ENTITIES: {
                    key: user_input[key]
                    for key in MIRROR_KEYS
                    if key in user_input
                },
            }
            return self.async_create_entry(title="", data=options)

        current_limit = entry.options.get(
            CONF_CONTRACT_LIMIT_A,
            entry.data.get(CONF_CONTRACT_LIMIT_A, DEFAULT_CONTRACT_LIMIT_A),
        )
        current_buffer = entry.options.get(
            CONF_BUFFER_PCT, entry.data.get(CONF_BUFFER_PCT, DEFAULT_BUFFER_PCT)
        )
        current_mirror = entry.options.get(
            CONF_MIRROR_ENTITIES, entry.data.get(CONF_MIRROR_ENTITIES, {})
        )
        schema = _limits_schema(current_limit, current_buffer).extend(
            _mirror_schema(current_mirror).schema
        )
        return self.async_show_form(step_id="init", data_schema=schema)
