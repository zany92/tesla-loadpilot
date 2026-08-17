"""Repairs support for Tesla LoadPilot.

Issues raised by the coordinator (never blocking regulation, D4):
- firmware_version_skew_<entry_id>: charger-node package version differs
  from the integration version (lockstep releases, ARCHITECTURE.md D4);
- source_failsafe_<entry_id>: no healthy measure source, the node publishes
  main_breaker and the charge is blocked (this is the SAFE behaviour).

Both are informational: the fix is either updating the pinned ESPHome
package / the HACS integration, or restoring the meter feed. The flows
below simply let the user acknowledge after acting.
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
