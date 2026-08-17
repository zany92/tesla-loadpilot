# Commentaire posté - issue #1 de PVi1/esphome-twc-control

Statut : **POSTÉ le 17/08/2026** -
https://github.com/PVi1/esphome-twc-control/issues/1#issuecomment-5315520912
Cible : commentaire de suivi sur l'issue #1 (ouverte par zany92). Le texte
ci-dessous est conservé tel que publié (archive) ; toute évolution passe
par un nouveau commentaire sur GitHub, pas par une édition de ce fichier.

---

Hi @PVi1 - following up on my earlier question, this time with a lot of data to share. First of all: thank you. Your firmware and your README notes (the correlation check, the "never dilute" lesson, the clamped `avail`) were the foundation that made everything below possible. We'd love your eyes on two open questions at the end.

## How our project differs from yours (for context)

We're building on your fundamentals but in a different setting, which is probably why we hit corners you never did:

- **No solar.** Our goal isn't zero grid exchange - it's sharing a **fixed utility contract** (France, 15 kVA three-phase, ~21.7 A/phase) between the house and the car: the car should take whatever the house isn't using, ramp down when the oven kicks in, and only stop when there's truly nothing left.
- **The meter is the French utility meter (Linky)**, read via its TIC serial output by a second ESP32 (Olimex ESP32-POE + a small TIC receiver hat) near the meter, ~500 ms updates, sub-amp current resolution computed from SINSTS/URMS. It broadcasts encrypted UDP to the charger-side node (~0.5-1 s end-to-end), with an HA-mirror fallback and a fail-safe that reports full consumption if both sources die.
- **The charger-side node is a Kincony KC868-A6** (same Neurio emulation as yours, reusing its RS485 bus).
- **It must work for ANY vehicle** - including guests' cars, any brand. So no vehicle API, no BLE, no cloud: the wall connector is the only lever.
- We're packaging it as an open HACS module ("Tesla LoadPilot") - your work will be credited prominently, and since your repo has no license file we'd like to discuss attribution/permission with you before anything is published. Nothing derived from your code is public yet.

## What we measured on fw 26.18 (three-phase, ~24 h of instrumented episodes)

**Service vs protection are two different laws, watching two different things:**

- **Service (pilot modulation) engages on a symmetric function of the 3 reported CTs** - in 20+ discriminating episodes where one phase's reported current exceeded the limit while the phase average stayed below, the pilot never moved (up to 3 minutes, flat to ±0.1 A). Modulation was only ever observed when the *average* of the three reported values reached the limit. (This is why we ended up publishing the worst phase **symmetrically on all three CTs** - min = mean = max, so service engages at the true constraint whatever the exact functional is.)
- **Protection watches the WORST phase**: recoverable "bites" (2-6 A drops, recovery in ~8 s) within ~5 s of a phase crossing ~21.3 A reported, and a hard contactor cut on an **integral criterion ≈ 20-21 A·s** above the limit (we measured 55 s tolerated at 21.8 A, but ~20 s at 22+; brief repeated crossings shaved fast → no cut for minutes).
- **Session give-up**: ~3 disturbed sessions in a short window → the *vehicle* abandons (charger EVSE state 9, zero charger alerts, charge-cycles counter frozen) and needs an app-level restart. The vehicle re-applies its per-location amp memory on every session start.
- **With the worst-phase-symmetric, clamped publication, the loop is textbook**: house appliance starts → reported hits the limit (clamped, never above) → pilot steps down ~1 A per step, car follows within ~19-25 s → stable plateau → loads stop → autonomous recovery at ~1 A/30 s back to full amps. Zero contactor cycles across the whole validation session.

## The distrust state - your master-off behavior, hit accidentally (this is the important part)

You document that reporting a static 0 A makes the TWC distrust the meter within seconds and fall back to its internal ceiling - you use it deliberately as the master-off escape hatch, and your "attempt 1" (averaging) hit the same wall via correlation mismatch. We fell into that state **accidentally**, and once in, it's brutal:

- **Entry #1 (measured)**: a one-off meter glitch published ~0.6 A on a phase for ~2 s **while the charger itself was drawing 16 A** - a real meter on the incomer can physically never read below the charger's own branch, so this is maximally implausible. Distrust appears to have latched right there.
- **Entry #2 (measured)**: with the reported value pinned at the clamp (limit), the car ramped 8→16 A and the reported value echoed only +0.7 A - eight amps of the charger's own current invisible in the meter. Session-level distrust was immediate. (Note: with trust intact this corner is unreachable - at 0 availability the pilot is low, so the car *can't* ramp. It only happened because distrust was already installed.)
- **Once distrusted, the TWC ignores EVERYTHING**: no service modulation at sustained clamp, no protection bites, and - the strongest evidence - **the L+0.1 escalation was ignored for 8 minutes** with the contactor closed. At 0.1 A over the limit for 480 s, the integral protection (~20 A·s) should have cut at ~200 s if the meter were still being read. It wasn't. The charger simply charges at its internal ceiling.
- **What does NOT clear it (all measured)**: a charging-current renegotiation from the app, a brand-new charging session, a reboot of the meter-emulating node (~1 min Modbus dropout), and a value-dithered signal (±0.05 A at 1 Hz - we added that specifically so the TWC never sees a "dead" value).
- **What DID clear it, apparently**: an overnight gap during which the node published the **honest raw measurement for hours** (our "shadow" mode). Next morning, trust was back and the loop worked beautifully. Our current working hypothesis: **trust is a score, rebuilt by time spent on a plausible, 1:1-correlated signal** - not an event flag. We're testing this right now (honest signal for 1-2 h, then a re-test), and we've added a detector that timestamps every entry/exit of the distrust state.

## Two questions where your experience would help enormously

1. **Service law, per-phase**: on your three-phase rig, do you have any *logged* episode where a single CT reported high (low availability) while the other two stayed free - and did the pilot actually follow that one phase's availability, on what timescale? Our data says the pilot ignores a single high phase (service = symmetric/average-engaged), which is why we ask whether your "attempt 2" bottleneck (one importing phase pinning the session to ~0 A) was a live logged session or design reasoning. In symmetric publication min = mean = max so it doesn't matter for our fix - but it matters for the behavioral model we're documenting.
2. **Exiting distrust**: between your averaging "attempt 1" (mismatch → stopped charging within seconds) and your later successful attempts, did recovery involve a TWC power-cycle, a long idle period, or nothing you noticed? Any observation - even "it just worked the next day" - would be a data point. If distrust really is sticky-until-proven-honest, that's a big deal for anyone shipping an emulated-meter controller, and worth a paragraph in both our READMEs.

Happy to share raw traces (3-5 s resolution) for any of the episodes above, and again - we'd love to talk attribution/licensing whenever convenient. Thanks for the foundation this all stands on!

---

## Notes internes (ne pas poster)

- Toutes les valeurs citées sont issues de : sonde A 17/08 00:13, test ACTIF-MAX 00:36, test validation 11:21-11:35, épisodes 12:03/12:39/12:47/13:13, trancheur interne (57 coupures).
- Aucune IP, aucun identifiant, aucun détail réseau du site. Relu sous cet angle.
- Le « shadow mode » est nommé sans détailler l'architecture des 3 modes.
