# Post-publication TODO

The repository went public on 17 Aug 2026 under MIT, with attribution to
PVi1 and Klangen82. Remaining polish items, none of them blocking:

- [ ] **Hero image retouch** : remove the TESLA lettering on the charger in
  `docs/assets/hero.png` and regenerate without the V1.0 caption.
- [ ] **CI re-hardening** : remove `continue-on-error` from the HACS job in
  `.github/workflows/validate.yml` (repo-view checks can now run) and open
  the home-assistant/brands PR for the logo.
- [ ] **From-scratch install test** (TESTPLAN volet B) on a clean HA.
- [ ] **HACS custom-repository instructions** : verify the install flow end
  to end once the brands PR is merged.

Decisions taken: project name "Tesla LoadPilot" kept (community precedent,
descriptive use); publication done with PVi1's blessing window open (he has
the raw traces and a few days to review).
