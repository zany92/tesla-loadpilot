# Publication checklist (go-public gate)

The repo stays private until EVERY box is ticked. Status 17 Aug 2026, midnight.

- [x] **PVi1 licensing resolved** : 17 Aug 21:12 UTC, PVi1 added an MIT
  LICENSE to esphome-twc-control (based on Klangen82's) and answered on
  issue #1. Verified via the GitHub API (spdx MIT).
- [x] **LICENSE file** added : MIT, with an explicit attribution notice for
  PVi1 and Klangen82 covering the derived ESPHome-node portions.
- [ ] **Courtesy window (short)** : PVi1 asked for "a few days" to review
  our data before commenting. Wait for his follow-up or until ~22 Aug
  before flipping public; reply on issue #1 first (thanks + heads-up that
  we will publish under MIT with attribution).
- [ ] **Project name reviewed** : "Tesla LoadPilot" contains a trademark;
  decide keep (community precedent) vs rename, deliberately.
- [ ] **Hero image retouched** : remove the TESLA lettering on the charger
  (and regenerate without the V1.0 caption while at it).
- [ ] **CI re-hardened** : remove `continue-on-error` from the HACS job
  (license now present; the remaining checks pass once public), open the
  home-assistant/brands PR for the logo.
- [ ] **Secrets final sweep** : re-run the value-scan and gitleaks on the
  full history (history was already rewritten and the UDP key rotated on
  17 Aug; verify nothing regressed since).
- [ ] **From-scratch install test** (TESTPLAN volet B) on a clean HA.

When all boxes are ticked: flip visibility, tag the release, publish the
HACS custom-repository instructions, and answer the community threads.
