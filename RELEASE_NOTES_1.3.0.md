# Tesla LoadPilot 1.3.0

The integration learns the control patterns that were prototyped and
field-validated on the pilot site. Everything is strictly opt-in: an
existing entry keeps byte-identical behavior until you enable a feature.

## Charge cap (number.loadpilot_charge_cap)

A user-set ceiling in amps (0 = automatic). The coordinator runs a 10 s
control tick that steers the node's bias channel: target = worst-phase
headroom + vehicle current - cap, raised immediately, released at most
0.5 A per tick (the asymmetry that killed the 11-16 A limit cycle), with
an anti-hysteresis kick when the vehicle idles above the cap while the
published value sits in the dead band. Field-validated on the pilot
(13 A target held at 13.2 A steady). Requires mapping a vehicle-current
entity (new field in advanced mapping); without it the number stays
unavailable and nothing runs.

## Automatic budget trim (option, default off)

When the cap is 0, an IDLE / ARMED / KICKING / COOLDOWN state machine
detects the parked-above-budget condition (negative headroom held 3 min,
published in the dead band, bias at 0) and applies a transient 2 A kick,
releasing it only if the bias is still its own. Layered under the
firmware stage-2 escalation of core 1.2.0: the integration acts at
3 min, the firmware backstops at 4 min with no Home Assistant needed.

## Law settings enforcement (options, default off)

Optional gain / max-excursion (and site-mapped drag) values that the
integration re-applies when the node reboots or comes back: this closes
the real gap where a reflash silently resets the law numbers to their
initial values (lived on the pilot: the tail fell back to 0 after a
flash). A Repair is raised if an enforced knob has no resolvable target
entity. Note: the generic core ships law variant A; the decaying-tail
knob is a site-specific override with no generic default.

## Meter distrust detector (binary_sensor.loadpilot_meter_distrust)

A PROBLEM binary sensor plus a pedagogical Repair when the published
value stays in the pull zone for 120 s while the vehicle keeps drawing:
the signature of the charger silently distrusting the meter (BEHAVIOR
section 4). Thresholds derive from the new max-conductor option.
Disabled without a vehicle-current mapping (a published-only variant is
structurally false-positive prone; the 17 Aug false alert is now a
regression test).

## Engineering

The decision logic lives in a pure module (control.py, injected clock,
no Home Assistant imports) covered by 36 pytest cases anchored on the
real traces of 17-18 Aug, and the CI now runs them on every push.
