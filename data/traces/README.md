# Raw traces (pilot site, 17 Aug 2026)

Every instrumented episode from the day the law was built, in chronological
order. Format per line: local timestamp, then key=value pairs. Common keys:
`car` = charger vehicle current (A, cable side, sometimes `contactor|evse|current`),
`pub` = published/reported current (worst phase, symmetric), `pire` = worst
incomer phase in % of the 21.7 A contract (includes the charger's own draw),
`biais` = pause lever offset (A), `cyc`/`cycles` = lifetime contactor closures.
Sampling 3 to 5 s. L = 21 A. Some drops are the owner's app actions; episodes
where attribution matters are flagged in [docs/en/BEHAVIOR.md](../../docs/en/BEHAVIOR.md).

| File | Episode |
|---|---|
| 0013_probe_A | One phase published high, average below limit: pilot never moved (service law probe) |
| 0036_symmetric | First symmetric publication: engagement at the mean, closed-loop yo-yo, protective trip |
| 1054_raw_mode | RAW mode session failures (protection-only regime, vehicle abandonment) |
| 1121_clamped_law | The clamped law's textbook validation (clamp 21.0, steps down, autonomous recovery) |
| 1245_observation | The 45 s observation window before pausing (car-first doctrine) |
| 1312_distrust_entry | Distrust entry #2: startup ramp absorbed under the pinned clamp, stop order ignored |
| 1418 / 1457_probe_below_limit | Soft probes during the honest-signal cure (30 min / 70 min): still deaf |
| 1619_probe_post_powercycle | Probe after the wall connector power-cycle |
| 1834_evening_hold | Hold-at-L behavior and the 1 A escalation nibble (trust returning) |
| 1925_boundary_dance | Covariant law at equilibrium: the +/-1 A boundary dance |
| 1929_descent_cascade | Covariant law under a 4-AC step: continuous descent, pause cascade, autonomous resume |
| 2031_deadband | The dead band (70 s at L+0.5, no reaction) and the gain-dilution re-distrust |
| 2256_variantB (PARTIAL) | Variant B closed-loop test, in progress at commit time |

These are debugging-grade primary data: if you are reproducing our findings
or challenging the behavior model, start here.
