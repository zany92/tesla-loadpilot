# Post-publication TODO

The repository went public on 17 Aug 2026 under MIT, with attribution to
PVi1 and Klangen82. Remaining polish items, none of them blocking:

- [x] **Hero image** : final render chosen by the site owner on 18 Aug
  (titled, realistic boards, full Linky to charger chain).
- [x] **CI re-hardened** : `continue-on-error` removed from the HACS job
  (17 Aug); only the brands check stays ignored until the brands PR merges.
- [x] **Brand icons shipped in the integration** (`custom_components/
  loadpilot/brand/`), per the HA 2026.3 mechanism. The home-assistant/brands
  PR (#10992) was auto-closed: that repo no longer accepts custom
  integrations, no action needed.
- [x] **License detection fixed** : pure MIT text in LICENSE (GitHub SPDX
  detection broke on the inline attribution paragraph), attribution moved
  to NOTICE.md, stale LICENSE.placeholder removed.
- [ ] **HACS default store PR** : first attempt (hacs/default#10084) closed
  by the bot (template checklist + 3 links required, HACS action run must
  be green without `ignore`). Reopen with the full template once CI is
  green and a fresh release exists.
- [ ] **From-scratch install test** (TESTPLAN volet B) on a clean HA.
- [ ] **HACS custom-repository instructions** : verify the install flow end
  to end once the brands PR is merged.

Decisions taken: project name "Tesla LoadPilot" kept (community precedent,
descriptive use); publication done with PVi1's blessing window open (he has
the raw traces and a few days to review).
