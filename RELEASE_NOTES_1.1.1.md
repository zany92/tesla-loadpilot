# Tesla LoadPilot 1.1.1

Documentation and field-data release. No code change in the integration
or the firmware packages; the version bump ships the knowledge gained
on the pilot site on 18 Aug 2026.

## Firmware 26.26.1 revalidated

Tesla started rolling out wall connector firmware 26.26.1 overnight.
The pilot site updated under supervision and revalidated the whole
behavior model in a real charge session: the commissioned emulated
meter survives the update, and every measured behavior (echo
correlation, dead band, pull, pause, autonomous resume) is identical
to 26.18, including a real 115 percent house-spike stress test with a
clean floor stop and resume. Details and raw traces: BEHAVIOR section
12 and `data/traces/` (both languages).

## Behavior model refined: the dead band is a hysteresis

From rest the pilot engages at about L + 0.85 published; once pulling
it follows down to published = L and holds there. Consequence for any
external bias controller: raise fast, release slowly, kick through the
threshold when the vehicle idles above target. Documented in BEHAVIOR
(EN and FR) and applied to the manual-limit pattern in the roadmap.

## Manual cap pattern field-tuned

The 13 A manual cap was exercised on a live charge: a fast symmetric
loop produced an 11-16 A limit cycle; the shipped pattern (immediate
raise, 0.5 A per 10 s decay, anti-hysteresis kick, 5 s local vitals
source) held 13.2 A steady. TESTPLAN record A16.

## New runbook signature

"charging failed" right after a pause with a calm house: a pause bias
posted while no charge is running can survive every release path and
silently block session starts. Signature, remedy and the permanent
"empty pause" exemption deployed on the pilot are documented in
RUNBOOK_INCIDENTS (EN and FR).
