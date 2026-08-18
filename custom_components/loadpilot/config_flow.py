"""Config flow for Tesla LoadPilot.

Field labels/descriptions come from translations/ - the UX designer owns the
copy (dashboards/UX_COPY.md); this module only defines keys and validation.

Flow layout (UX.md §2.0, five steps):
  user (country profile) -> nodes (the two ESP32 nodes, existence-checked)
  -> electrical (phases + contract limit + buffer, kVA presets for fr_tic)
  -> mirror (optional HA backup path, L1-only when single-phase)
  -> confirm (recap, then create the entry).
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
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
    CHARGER_TRACKED_ENTITIES,
    CONF_BUFFER_PCT,
    CONF_CHARGER_NODE,
    CONF_CONTRACT_LIMIT_A,
    CONF_CONTRACT_PRESET,
    CONF_COUNTRY_PROFILE,
    CONF_ENTITY_OVERRIDES,
    CONF_LAW_DRAG_A,
    CONF_LAW_EXCURSION_A,
    CONF_LAW_GAIN_A,
    CONF_MAX_CONDUCTOR_A,
    CONF_METER_NODE,
    CONF_MIRROR_ENTITIES,
    CONF_PHASES,
    CONF_TRIM_ENABLED,
    CONF_VEHICLE_CURRENT_ENTITY,
    LAW_OVERRIDE_ONLY_KEYS,
    CONTRACT_PRESET_CUSTOM,
    CONTRACT_PRESETS_A,
    CONTRACT_PRESETS_MONO_A,
    CONTRACT_PRESETS_TRI_A,
    COUNTRY_PROFILE_FR_TIC,
    COUNTRY_PROFILES,
    DEFAULT_BUFFER_PCT,
    DEFAULT_CONTRACT_LIMIT_A,
    DEFAULT_COUNTRY_PROFILE,
    DEFAULT_MAX_CONDUCTOR_MONO_A,
    DEFAULT_MAX_CONDUCTOR_TRI_A,
    DEFAULT_PHASES,
    DOMAIN,
    METER_NODE_DEFAULT_NAME,
    MIN_CHARGE_BUDGET_A,
    MIRROR_KEYS,
    TRI_LIMIT_SUSPICIOUS_A,
)

_LOGGER = logging.getLogger(__name__)

# Options-flow-only form field (never stored): opt-in checkbox that routes
# to the advanced entity-mapping step.
CONF_CONFIGURE_MAPPING = "configure_entity_mapping"

# Labels used in the confirm-step recap placeholder {country_profile}.
# Deliberately language-neutral-ish (proper nouns / protocol names): HA
# description placeholders cannot vary per viewer language.
_PROFILE_RECAP_LABELS = {
    "fr_tic": "France - Linky (TIC)",
    "dsmr_p1": "DSMR P1",
    "sml_de": "SML",
    "ct_clamps": "CT clamps",
}

STEP_USER_SCHEMA = vol.Schema(
    {
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

STEP_NODES_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_CHARGER_NODE, default=CHARGER_NODE_DEFAULT_NAME
        ): TextSelector(),
        vol.Required(
            CONF_METER_NODE, default=METER_NODE_DEFAULT_NAME
        ): TextSelector(),
    }
)


def _node_entities_present(hass: HomeAssistant, node_name: str) -> bool:
    """True when at least one entity of the given ESPHome node exists.

    ESPHome object_ids are prefixed with the slugified node name (that is
    exactly how the coordinator builds its tracked entity ids), so a single
    prefix scan is the honest existence test - the node must be adopted in
    ESPHome and visible in HA before the flow proceeds (UX.md §2.2).
    """
    prefix = f"{slugify(node_name)}_"
    return any(
        entity_id.split(".", 1)[1].startswith(prefix)
        for entity_id in hass.states.async_entity_ids()
    )


def _phases_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=["1", "3"],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="phases",
        )
    )


def _limits_schema(
    contract_limit: float = DEFAULT_CONTRACT_LIMIT_A,
    buffer_pct: int = DEFAULT_BUFFER_PCT,
    *,
    phases: Optional[int] = None,
    with_presets: bool = False,
) -> vol.Schema:
    """Electrical-limits schema (limit + buffer, optional kVA presets).

    Selector bounds are the FIRMWARE bounds (twc-core.yaml): contract limit
    6..120 A, buffer 0..30 % - the plausibility rules (UX.md §2.3) live in
    ``_validate_limits``. ``with_presets`` adds the French kVA helper
    dropdown (fr_tic profile): a preset OVERRIDES the amps field; what is
    stored is always ``contract_limit_a`` in amps per phase. ``phases``
    filters the preset list (None = both, config flow: phases is picked on
    the same screen so the full list is shown, as in the UX.md mockup).
    """
    schema: dict[Any, Any] = {}
    if with_presets:
        if phases == 1:
            presets: list[str] = list(CONTRACT_PRESETS_MONO_A)
        elif phases == 3:
            presets = list(CONTRACT_PRESETS_TRI_A)
        else:
            presets = list(CONTRACT_PRESETS_A)
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


def _electrical_schema(
    contract_limit: float,
    buffer_pct: int,
    phases_default: int,
    with_presets: bool,
) -> vol.Schema:
    """Config-flow electrical step: installation type + limits (UX.md §2.3)."""
    schema = vol.Schema(
        {
            vol.Required(
                CONF_PHASES, default=str(phases_default)
            ): _phases_selector()
        }
    )
    return schema.extend(
        _limits_schema(
            contract_limit, buffer_pct, phases=None, with_presets=with_presets
        ).schema
    )


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


def _mirror_keys_for(phases: int) -> list[str]:
    """Single-phase mirror is L1-only (firmware forces B/C to 0)."""
    if phases == 1:
        return [key for key in MIRROR_KEYS if key.endswith("_l1")]
    return list(MIRROR_KEYS)


def _mirror_schema(
    defaults: Optional[dict[str, str]] = None, *, phases: int = DEFAULT_PHASES
) -> vol.Schema:
    """Optional backup measure path (mirror wiring is documented, physically
    configured in the ESPHome substitutions).

    Every field is ``vol.Optional`` with a ``suggested_value`` (never a
    Required with default): a previously saved entity is pre-filled but can
    be CLEARED in the options flow - clearing removes it from the mapping.
    """
    defaults = defaults or {}
    schema: dict[Any, Any] = {}
    for key in _mirror_keys_for(phases):
        device_class = "current" if key.startswith("current") else "apparent_power"
        marker = (
            vol.Optional(key, description={"suggested_value": defaults[key]})
            if key in defaults
            else vol.Optional(key)
        )
        schema[marker] = EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class=device_class)
        )
    return vol.Schema(schema)


# --- Axis B options (all opt-in; the INITIAL config flow is unchanged) ----
# Law-option selector bounds: (min, max, step, unit). Gain and excursion
# mirror the firmware knob ranges (twc-core.yaml); the drag (variant B
# tail) validated range is 0..2.5 A.
_LAW_OPTION_BOUNDS: dict[str, tuple[float, float, float, Optional[str]]] = {
    CONF_LAW_GAIN_A: (0.1, 1.0, 0.05, None),
    CONF_LAW_EXCURSION_A: (0.1, 1.0, 0.1, "A"),
    CONF_LAW_DRAG_A: (0.0, 2.5, 0.1, "A"),
}


def _default_max_conductor(phases: int) -> float:
    """L default: 21 A three-phase (field-validated), 32 A single-phase
    (theoretical, BEHAVIOR annex §11)."""
    return (
        DEFAULT_MAX_CONDUCTOR_MONO_A
        if phases == 1
        else DEFAULT_MAX_CONDUCTOR_TRI_A
    )


def _axis_b_schema(options: dict[str, Any], phases: int) -> vol.Schema:
    """Options-flow fields for the axis-B capabilities (all optional).

    Only the plausibility floor max_conductor_a >= 6 is enforced (the TWC
    firmware bounds differ per market, stay permissive). Empty law fields
    = the integration never touches the corresponding node number.
    """
    schema: dict[Any, Any] = {
        vol.Required(
            CONF_MAX_CONDUCTOR_A,
            default=float(
                options.get(
                    CONF_MAX_CONDUCTOR_A, _default_max_conductor(phases)
                )
            ),
        ): NumberSelector(
            NumberSelectorConfig(
                min=6,
                max=48,
                step=1,
                unit_of_measurement="A",
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_TRIM_ENABLED,
            default=bool(options.get(CONF_TRIM_ENABLED, False)),
        ): BooleanSelector(),
    }
    for key, (low, high, step, unit) in _LAW_OPTION_BOUNDS.items():
        current = options.get(key)
        marker = (
            vol.Optional(key, description={"suggested_value": current})
            if current is not None
            else vol.Optional(key)
        )
        config: dict[str, Any] = {
            "min": low,
            "max": high,
            "step": step,
            "mode": NumberSelectorMode.BOX,
        }
        if unit is not None:
            config["unit_of_measurement"] = unit
        schema[marker] = NumberSelector(NumberSelectorConfig(**config))
    return vol.Schema(schema)


class LoadPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the LoadPilot config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        # Limit value for which the non-blocking three-phase warning was
        # already shown - resubmitting the same value acknowledges it.
        self._tri_warned_limit: Optional[float] = None

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 1 - country / meter profile (UX.md §2.1)."""
        if user_input is not None:
            self._data = {
                CONF_COUNTRY_PROFILE: user_input[CONF_COUNTRY_PROFILE],
            }
            return await self.async_step_nodes()

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

    async def async_step_nodes(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 2 - the two ESPHome nodes, existence-checked (UX.md §2.2)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            charger_node = user_input[CONF_CHARGER_NODE].strip()
            meter_node = user_input[CONF_METER_NODE].strip()
            await self.async_set_unique_id(slugify(charger_node))
            self._abort_if_unique_id_configured()
            if not _node_entities_present(self.hass, charger_node):
                errors[CONF_CHARGER_NODE] = "charger_not_found"
            if not _node_entities_present(self.hass, meter_node):
                errors[CONF_METER_NODE] = "meter_not_found"
            if not errors:
                self._data[CONF_CHARGER_NODE] = charger_node
                self._data[CONF_METER_NODE] = meter_node
                return await self.async_step_electrical()

        return self.async_show_form(
            step_id="nodes", data_schema=STEP_NODES_SCHEMA, errors=errors
        )

    async def async_step_electrical(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 3 - installation type + electrical limits (UX.md §2.3).

        The limits are later written to the NODE-RESIDENT knobs (D2).
        """
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        with_presets = (
            self._data.get(CONF_COUNTRY_PROFILE) == COUNTRY_PROFILE_FR_TIC
        )
        phases = self._data.get(CONF_PHASES, DEFAULT_PHASES)
        limit = DEFAULT_CONTRACT_LIMIT_A
        buffer_pct = DEFAULT_BUFFER_PCT
        if user_input is not None:
            phases = int(user_input[CONF_PHASES])
            limit = _resolve_limit(user_input)
            buffer_pct = int(user_input[CONF_BUFFER_PCT])
            errors, placeholders = _validate_limits(
                limit, buffer_pct, phases, self._tri_warned_limit == limit
            )
            if errors.get(CONF_CONTRACT_LIMIT_A) == "tri_limit_suspicious":
                self._tri_warned_limit = limit
            if not errors:
                self._data[CONF_PHASES] = phases
                self._data[CONF_CONTRACT_LIMIT_A] = limit
                self._data[CONF_BUFFER_PCT] = buffer_pct
                return await self.async_step_mirror()

        return self.async_show_form(
            step_id="electrical",
            data_schema=_electrical_schema(limit, buffer_pct, phases, with_presets),
            errors=errors,
            description_placeholders=placeholders or None,
        )

    async def async_step_mirror(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 4 - optional HA-mirror entities (backup measure path)."""
        phases: int = self._data.get(CONF_PHASES, DEFAULT_PHASES)
        if user_input is not None:
            self._data[CONF_MIRROR_ENTITIES] = {
                key: user_input[key]
                for key in _mirror_keys_for(phases)
                if key in user_input
            }
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="mirror", data_schema=_mirror_schema(phases=phases)
        )

    async def async_step_confirm(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Step 5 - recap before creating the entry (UX.md §2.5)."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._data[CONF_CHARGER_NODE], data=self._data
            )

        limit = float(self._data[CONF_CONTRACT_LIMIT_A])
        buffer_pct = float(self._data[CONF_BUFFER_PCT])
        budget = limit * (1 - buffer_pct / 100)
        profile = self._data.get(CONF_COUNTRY_PROFILE, DEFAULT_COUNTRY_PROFILE)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "country_profile": _PROFILE_RECAP_LABELS.get(profile, profile),
                "phases": str(self._data.get(CONF_PHASES, DEFAULT_PHASES)),
                "contract_limit_a": f"{limit:g}",
                "buffer_pct": f"{buffer_pct:g}",
                "budget_a": f"{budget:.1f}",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "LoadPilotOptionsFlow":
        """Return the options flow."""
        return LoadPilotOptionsFlow()


class LoadPilotOptionsFlow(OptionsFlow):
    """Runtime-adjustable options (limits + mirror + entity mapping)."""

    def __init__(self) -> None:
        self._tri_warned_limit: Optional[float] = None
        # Options gathered by the init step, completed by advanced_mapping.
        self._options: dict[str, Any] = {}

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
            # A cleared entity selector is simply absent from user_input:
            # rebuilding the mapping from what was submitted is what makes
            # the mirror REMOVABLE here.
            current_mirror = {
                key: user_input[key]
                for key in _mirror_keys_for(phases)
                if key in user_input
            }
            if not errors:
                options = {
                    CONF_CONTRACT_LIMIT_A: current_limit,
                    CONF_BUFFER_PCT: current_buffer,
                    CONF_MIRROR_ENTITIES: current_mirror,
                    # Preserved as-is unless the mapping step rewrites it.
                    CONF_ENTITY_OVERRIDES: entry.options.get(
                        CONF_ENTITY_OVERRIDES, {}
                    ),
                }
                # Axis B fields: stored ONLY when they deviate from the
                # inert defaults (or were already stored): an options
                # submit that does not touch them produces the same
                # options dict as before axis B (non-regression rule).
                max_conductor = float(user_input[CONF_MAX_CONDUCTOR_A])
                if (
                    max_conductor != _default_max_conductor(phases)
                    or CONF_MAX_CONDUCTOR_A in entry.options
                ):
                    options[CONF_MAX_CONDUCTOR_A] = max_conductor
                trim_enabled = bool(user_input.get(CONF_TRIM_ENABLED, False))
                if trim_enabled or CONF_TRIM_ENABLED in entry.options:
                    options[CONF_TRIM_ENABLED] = trim_enabled
                for law_key in _LAW_OPTION_BOUNDS:
                    # A cleared number selector is absent from user_input:
                    # clearing removes the option (enforcement off).
                    if user_input.get(law_key) is not None:
                        options[law_key] = float(user_input[law_key])
                # Preserved as-is unless the mapping step rewrites it.
                vehicle_entity = entry.options.get(
                    CONF_VEHICLE_CURRENT_ENTITY
                )
                if vehicle_entity:
                    options[CONF_VEHICLE_CURRENT_ENTITY] = vehicle_entity
                if user_input.get(CONF_CONFIGURE_MAPPING):
                    self._options = options
                    return await self.async_step_advanced_mapping()
                return self.async_create_entry(title="", data=options)

        schema = _limits_schema(
            current_limit,
            current_buffer,
            phases=phases,
            with_presets=with_presets,
        ).extend(_mirror_schema(current_mirror, phases=phases).schema)
        schema = schema.extend(
            _axis_b_schema(dict(entry.options), phases).schema
        )
        schema = schema.extend(
            {vol.Optional(CONF_CONFIGURE_MAPPING, default=False): BooleanSelector()}
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders or None,
        )

    async def async_step_advanced_mapping(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> ConfigFlowResult:
        """Optional per-key remapping of the tracked charger-node entities.

        For historic nodes whose object_ids do not follow the generic
        contract. Each field holds a FULL entity_id; empty = generic
        default. Keys previously DECLARED ABSENT (stored as None/"") stay
        declared absent unless an entity is picked for them - an empty
        selector cannot distinguish "back to default" from "still absent".
        """
        entry = self.config_entry
        slug = slugify(entry.data[CONF_CHARGER_NODE])
        generic = {
            key: f"{platform}.{slug}_{suffix}"
            for key, (platform, suffix) in CHARGER_TRACKED_ENTITIES.items()
        }
        existing = entry.options.get(CONF_ENTITY_OVERRIDES) or {}
        if user_input is not None:
            overrides: dict[str, Optional[str]] = {
                key: user_input[key]
                for key in CHARGER_TRACKED_ENTITIES
                if user_input.get(key) and user_input[key] != generic[key]
            }
            for key, value in existing.items():
                if (
                    key in CHARGER_TRACKED_ENTITIES
                    and not value
                    and not user_input.get(key)
                ):
                    overrides[key] = None  # keep the declared-absent marker
            self._options[CONF_ENTITY_OVERRIDES] = overrides
            # Axis B: dedicated option key (NOT a tracked-entities entry:
            # its correct default is ABSENT). Same clearing mechanic as
            # the mirror: a cleared selector removes the option.
            if user_input.get(CONF_VEHICLE_CURRENT_ENTITY):
                self._options[CONF_VEHICLE_CURRENT_ENTITY] = user_input[
                    CONF_VEHICLE_CURRENT_ENTITY
                ]
            else:
                self._options.pop(CONF_VEHICLE_CURRENT_ENTITY, None)
            return self.async_create_entry(title="", data=self._options)

        schema: dict[Any, Any] = {}
        current_vehicle = entry.options.get(CONF_VEHICLE_CURRENT_ENTITY)
        vehicle_marker = (
            vol.Optional(
                CONF_VEHICLE_CURRENT_ENTITY,
                description={"suggested_value": current_vehicle},
            )
            if current_vehicle
            else vol.Optional(CONF_VEHICLE_CURRENT_ENTITY)
        )
        schema[vehicle_marker] = EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="current")
        )
        for key, (platform, _suffix) in CHARGER_TRACKED_ENTITIES.items():
            # Effective current value: override if set, else the generic
            # default; declared-absent keys show an empty field.
            # Override-only keys (law_drag: variant-B pilot firmware only)
            # have NO generic default: empty until the user maps one.
            if key in LAW_OVERRIDE_ONLY_KEYS:
                effective = existing.get(key)
            else:
                effective = existing[key] if key in existing else generic[key]
            marker = (
                vol.Optional(key, description={"suggested_value": effective})
                if effective
                else vol.Optional(key)
            )
            schema[marker] = EntitySelector(
                EntitySelectorConfig(domain=platform)
            )
        return self.async_show_form(
            step_id="advanced_mapping", data_schema=vol.Schema(schema)
        )
