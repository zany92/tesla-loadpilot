# Post-publication TODO

The repository went public on 17 Aug 2026 under MIT, with attribution to
PVi1 and Klangen82. Remaining polish items, none of them blocking:

- [ ] **Hero image retouch** : remove the TESLA lettering on the charger in
  `docs/assets/hero.png` and regenerate without the V1.0 caption.
- [x] **CI re-hardened** : `continue-on-error` removed from the HACS job
  (17 Aug); only the brands check stays ignored until the brands PR merges.
- [x] **Brands PR opened** : home-assistant/brands#10992 (icon 256 + 512,
  original artwork, `docs/assets/icon.png` in this repo).
- [x] **HACS default store PR opened** : hacs/default#10084. Its checks
  depend on the brands PR being merged first; expect a few weeks of review.
- [ ] **After the brands PR merges** : drop the `ignore: brands` line in
  `.github/workflows/validate.yml`.
- [ ] **From-scratch install test** (TESTPLAN volet B) on a clean HA.
- [ ] **HACS custom-repository instructions** : verify the install flow end
  to end once the brands PR is merged.

Decisions taken: project name "Tesla LoadPilot" kept (community precedent,
descriptive use); publication done with PVi1's blessing window open (he has
the raw traces and a few days to review).
