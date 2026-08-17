# Publication checklist (go-public gate)

The repo stays private until EVERY box is ticked. Status 17 Aug 2026, midnight.

- [ ] **PVi1 licensing/attribution resolved** : answer received on issue #1,
  OR the courtesy window (2 weeks, until 31 Aug) has lapsed and the framing
  has been reworked (our law documented as original work, PVi1 credited as
  inspiration and prior art, no derived-code claim anywhere).
- [ ] **LICENSE file** chosen and added (MIT presumed, decision pending the
  point above).
- [ ] **Project name reviewed** : "Tesla LoadPilot" contains a trademark;
  decide keep (community precedent) vs rename, deliberately.
- [ ] **Hero image retouched** : remove the TESLA lettering on the charger
  (and regenerate without the V1.0 caption while at it).
- [ ] **CI re-hardened** : remove `continue-on-error` from the HACS job
  (its repo-view checks pass once public + licensed), open the
  home-assistant/brands PR for the logo.
- [ ] **Secrets final sweep** : re-run the value-scan and gitleaks on the
  full history (history was already rewritten and the UDP key rotated on
  17 Aug; verify nothing regressed since).
- [ ] **From-scratch install test** (TESTPLAN volet B) on a clean HA.

When all boxes are ticked: flip visibility, tag the release, publish the
HACS custom-repository instructions, and answer the community threads.
