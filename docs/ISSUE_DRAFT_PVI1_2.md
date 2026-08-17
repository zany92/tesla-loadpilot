# Commentaire posté (n° 2) - issue #1 de PVi1/esphome-twc-control

Statut : POSTÉ le 17/08/2026 au soir -
https://github.com/PVi1/esphome-twc-control/issues/1#issuecomment-5318829962
Texte conservé tel que publié (archive).
Contexte : suite du commentaire posté le 17/08 à 13:37 (qui promettait les
résultats du test de récupération « we're testing this right now »).

---

Quick follow-up with the results we promised this morning - plus two heads-ups about corners of your own design that our afternoon findings suggest you might want to look at. Everything below was measured today on fw 26.18, three-phase.

## 1. Exiting distrust - we have a working protocol (partially confounded)

This morning's distrust episode (L+0.1 ignored for 8 minutes) did NOT clear with: an app-side current renegotiation, a brand-new charging session, a reboot of the meter-emulating node, or value-dithering. What DID work, by the evening: **wall-connector power-cycle + ~2 h of honest raw publication + the first session started with a calm house** (so the whole startup ramp gets echoed 1:1, nothing absorbed). After that, the same L+0.1 order was executed in ~5 s. Attribution between the power-cycle and the honest-signal hours is still confounded (they happened in the same window - a later accidental re-entry suggests the honest hours matter most), but operationally: that combination restores trust. We also confirmed **your "honored at rest" observation holds during distrust**: session-start gating (refuses if reported > L−5, accepts below) kept working off the meter even while in-session service was deaf.

## 2. Heads-up #1 - your clamp has the same blind spot that bit us

Your `avail` floors at 0, so `reported` pins at `twc_breaker` (constant) whenever demand exceeds availability. If the car ever ramps **while** that pin is active, its ramp is invisible in the reported value - the exact correlation break that latched distrust for us (8 A of ramp echoed as +0.7 A). You've probably never hit it because in PV-surplus mode saturation coincides with a low pilot (the car *can't* ramp). But any glitch that installs distrust first (our entry #1: a meter reading below the charger's own draw for ~2 s) makes the pilot untrustworthy, ramps happen against the pin, and the state deepens. A cheap vaccine we now run: replace the flat pin with a **bounded slope above the limit** - `reported = L + clamp(k×excess, 0.1, 1.0)` - so the echo never dies (details below).

## 3. Heads-up #2 - a static fail-safe can neutralize itself

Your stale-meter fail-safe reports `twc_breaker` as a **constant**. But a constant is exactly what the TWC distrusts within seconds (your own master-off finding!) - so a long meter outage could flip the charger to *ignoring* the fail-safe and charging at its internal ceiling: the opposite of the intent. One line fixes it: dither the fail-safe value (±0.05 A alternating). We just did.

## 4. The covariant law - and the tuning floor we found the hard way

The bounded-slope law above is now our production replacement for the clamp. Validated end-to-end tonight: continuous descent under a big house step (16→12 A tracking a L+0.95 slope), a ±1 A "boundary dance" at equilibrium, and autonomous session resume. Two calibration data points you may find useful:

- **Your k=0.75 choice is quantitatively vindicated.** We tried gain 0.25 on the constrained-zone slope to soften oscillations → that's a 4:1 dilution of the charger's own ramp echo → distrust latched within one startup ramp. Gain 0.5 works. So the "never dilute" rule appears to have a hard floor somewhere in the ~0.4-0.5 region - your 0.75 sits comfortably above it.
- **There's a dead band above L**: at reported ≈ L+0.5 sustained, the pilot didn't move for 70 s (and the protection integral tolerated 35 A·s - so the ~20-21 A·s constant we published this morning only applies to excursions ≥ ~1 A). Firm pull starts around L+0.9. If you ever rely on the +0.1 escalation for a *fast* stop, that dead band is worth knowing about.

Remaining known issue on our side: with gain 0.5 and a house load hovering exactly at the budget, we get a ±2.5 A limit cycle (~20 s period) that can accumulate integral and bite. We're designing an asymmetric/one-cycle-nudge variant (inspired by the TWCManager#20 findings) - happy to share results.

## Raw data

All traces behind the claims above (and this morning's comment) are published here, with a README mapping each file to its claim: https://gist.github.com/zany92/50080065a4c7662d36b81b9b90f8c44a - 3-5 s resolution, 8 episodes from probe A to tonight's dead-band measurement. Happy to add specific windows on request.

Still very interested in your answers to the two questions from this morning whenever you have time - and in the licensing conversation. Thanks again!

---

## Notes internes (ne pas poster)

- Valeurs issues de : épisodes 16:20-16:28 (power-cycle), 18:47-18:50 (validation loi), 19:29 (descente continue), 20:20-20:35 (yo-yo, leçon 31, bande morte).
- Aucune IP, aucun identifiant site. Ton : fraternel, données brutes, zéro leçon.
