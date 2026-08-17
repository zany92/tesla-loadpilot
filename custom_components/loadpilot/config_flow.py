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
    CONF_CONTRACT_PRESET,
    CONF_COUNTRY_PROFILE,
    CONF_METER_NODE,
    CONF_MIRROR_ENTITIES,
    CONF_PHASES,
    CONTRACT_PRESET_CUSTOM,
    CONTRACT_PRESETS_A,
    CONTRACT_PRESETS_MONO_A,
    CONTRACT_PRESETS_TRI_A,
    COUNTRY_PROFILE_FR_TIC,
    COUNTRY_PROFILES,
    DEFAULT_BUFFER_PCT,
    DEFAULT_CONTRACT_LIMIT_A,
    DEFAULT_COUNTRY_PROFILE,
    DEFAULT_PHASES,
    DOMAIN,
    METER_NODE_DEFAULT_NAME,
    MIN_CHARGE_BUDGET_A,
    MIRROR_KEYS,
    TRI_LIMIT_SUSPICIOUS_A,
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
    *,
    phases: int = DEFAULT_PHASES,
    with_presets: bool = False,
) -> vol.Schema:
    """Electrical-limits schema.

    Selector bounds are the FIRMWARE bounds (twc-core.yaml): contract limit
    6..120 A, buffer 0..30 % — the plausibility rules (UX.md §2.3) live in
    ``_validate_limits``. ``with_presets`` adds the French kVA helper
    dropdown (fr_tic profile): a preset OVERRIDES the amps field; what is
    stored is always ``contract_limit_a`` in amps per phase.
    """
    schema: dict[Any, Any] = {}
    if with_presets:
        presets = (
            CONTRACT_PRESETS_MONO_A if phases == 1 else CONTRACT_PRESETS_TRI_A
        )
        schema[
            vol.Required(CONF_CONTRACT_PRESET, default=CONTRACT_PRESET_CUSTOM)
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[CONTRACT_PRESET_CUSTOM, *presets],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="contract_preset",
            )
        )
    schema[
        vol.Required(CONF_CONTRACT_LIMIT_A, default=contract_limit)
    ] = NumberSelector(
        NumberSelectorConfig(
            min=6,
            max=120,
            step=0.1,
            unit_of_measurement="A",
            mode=NumberSelectorMode.BOX,
        )
    )
    schema[vol.Required(CONF_BUFFER_PCT, default=buffer_pct)] = NumberSelector(
        NumberSelectorConfig(
            min=0,
            max=30,
            step=1,
            unit_of_measurement="%",
            mode=NumberSelectorMode.SLIDER,
        )
    )
    return vol.Schema(schema)


def _resolve_limit(user_input: dict[str, Any]) -> float:
    """Amps per phase from the submitted step (preset wins over free entry)."""
    preset = user_input.get(CONF_CONTRACT_PRESET, CONTRACT_PRESET_CUSTOM)
    if preset != CONTRACT_PRESET_CUSTOM and preset in CONTRACT_PRESETS_A:
        return CONTRACT_PRESETS_A[preset]
    return float(user_input[CONF_CONTRACT_LIMIT_A])


def _validate_limits(
    limit_a: float,
    buffer_pct: int,
    phases: int,
    tri_warning_acknowledged: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    """Cross-field validation (UX.md §2.3).

    Returns (errors, description_placeholders). ``tri_limit_suspicious`` is
    NON-blocking: it is raised once, and an unchanged resubmission passes
    (``tri_warning_acknowledged``).
    """
    errors: dict[str, str] = {}
    budget_a = limit_a * (1 - buffer_pct / 100)
    placeholders = {
        "budget_a": f"{budget_a:.1f}",
        "contract_limit_a": f"{limit_a:g}",
    }
    if budget_a < MIN_CHARGE_BUDGET_A:
        errors[CONF_CONTRACT_LIMIT_A] = "budget_too_small"
    elif (
        phases == 3
        and limit_a > TRI_LIMIT_SUSPICIOUS_A
        and not tri_warning_acknowledged
    ):
        errors[CONF_CONTRACT_LIMIT_A] = "tri_limit_suspicious"
    return errors, placeholders


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
        # Limit value for which the non-blocking three-phase warning was
        # already shown — resubmitting the same value acknowledges it.
        self._tri_warned_limit: Optional[float] = None

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
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        phases: int = self._data.get(CONF_PHASES, DEFAULT_PHASES)
        with_presets = (
            self._data.get(CONF_COUNTRY_PROFILE) == COUNTRY_PROFILE_FR_TIC
        )
        limit = DEFAULT_CONTRACT_LIMIT_A
        buffer_pct = DEFAULT_BUFFER_PCT
        if user_input is not None:
            limit = _resolve_limit(user_input)
            buffer_pct = int(user_input[CONF_BUFFER_PCT])
            errors, placeholders = _validate_limits(
                limit, buffer_pct, phases, self._tri_warned_limit == limit
            )
            if errors.get(CONF_CONTRACT_LIMIT_A) == "tri_limit_suspicious":
                self._tri_warned_limit = limit
            if not errors:
                self._data[CONF_CONTRACT_LIMIT_A] = limit
                self._data[CONF_BUFFER_PCT] = buffer_pct
                return await self.async_step_mirror()

        return self.async_show_form(
            step_id="limits",
            data_schema=_limits_schema(
                limit, buffer_pct, phases=phases, with_presets=with_presets
            ),
            errors=errors,
            description_placeholders=placeholders or None,
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

    def __init__(self) -> None:
        self._tri_warned_limit: Optional[float] = None

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Single options step."""
        entry = self.config_entry
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        phases: int = entry.data.get(CONF_PHASES, DEFAULT_PHASES)
        with_presets = (
            entry.data.get(CONF_COUNTRY_PROFILE) == COUNTRY_PROFILE_FR_TIC
        )
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
        if user_input is not None:
            current_limit = _resolve_limit(user_input)
            current_buffer = int(user_input[CONF_BUFFER_PCT])
            errors, placeholders = _validate_limits(
                current_limit,
                current_buffer,
                phases,
                self._tri_warned_limit == current_limit,
            )
            if errors.get(CONF_CONTRACT_LIMIT_A) == "tri_limit_suspicious":
                self._tri_warned_limit = current_limit
            if not errors:
                options = {
                    CONF_CONTRACT_LIMIT_A: current_limit,
                    CONF_BUFFER_PCT: current_buffer,
                    CONF_MIRROR_ENTITIES: {
                        key: user_input[key]
                        for key in MIRROR_KEYS
                        if key in user_input
                    },
                }
                return self.async_create_entry(title="", data=options)
            current_mirror = {
                key: user_input[key] for key in MIRROR_KEYS if key in user_input
            }

        schema = _limits_schema(
            current_limit,
            current_buffer,
            phases=phases,
            with_presets=with_presets,
        ).extend(_mirror_schema(current_mirror).schema)
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders or None,
        )
