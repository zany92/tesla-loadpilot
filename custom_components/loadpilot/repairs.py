"""Repairs support for Tesla LoadPilot.

Issues raised by the coordinator (never blocking regulation, D4):
- firmware_version_skew_<entry_id>: charger-node package version differs
  from the integration version (lockstep releases, ARCHITECTURE.md D4);
- source_failsafe_<entry_id>: no healthy measure source, the node publishes
  main_breaker and the charge is blocked (this is the SAFE behaviour);
- charger_node_missing_<entry_id>: no entity of the configured charger node
  exists at all (node renamed / deleted / never adopted) - the firmware
  keeps regulating on its own (D2), but HA is blind to it.

All are informational: the fix is updating the pinned ESPHome package / the
HACS integration, restoring the meter feed, or restoring the charger node
(or re-adding the integration with the right node name). The flows below
simply let the user acknowledge after acting.
"""

from __future__ import annotations

from typing import Optional

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: Optional[dict] = None,
) -> RepairsFlow:
    """Create a fix flow (simple acknowledge)."""
    return ConfirmRepairFlow()
