# Tesla LoadPilot 0.1.0

First tagged release. One SemVer tag covers the whole repository: the HACS
integration and the ESPHome firmware packages ship in lockstep and both
report version `0.1.0`.

Tesla LoadPilot is local, cloud-free charging power regulation for the
Tesla Wall Connector Gen 3: an ESP32 emulates the discontinued Neurio meter
on the wallbox's RS485 bus and feeds it real per-phase measurements taken at
the utility meter, so the wallbox's own load management modulates the
vehicle without ever tripping.

**Status: private beta.** Validated on a single pilot site (France,
three-phase 15 kVA, Linky meter, TWC firmware 26.18). The repository is
private; nothing is published to HACS or home-assistant/brands yet.

## Firmware (ESPHome packages)

- **Co-variant worst-phase law (v2)**: the published signal always echoes
  real load variations, even in constraint, via bounded compression above
  the Max Conductor Limit (knobs `Law Echo Gain` 0.5, `Law Max Excursion`
  1.0 A). This removes the "frozen published value" failure mode that
  latched the wallbox's distrust state. Validated in closed loop on the
  pilot site on 17 Aug 2026 (load steps absorbed, autonomous session
  recovery, zero contactor events). Design: `docs/DESIGN_LOI_COVARIANTE.md`.
- **Variant B (release drag)**: the asymmetric-release design that removes
  the exit yo-yo is fully specified with an inert-by-default kill switch
  (drag depth 0 restores the exact v2 law). It is delivered as design only
  in this release and is not part of the generic firmware packages. Design:
  `docs/DESIGN_VARIANTE_B.md`.
- **TIC watchdog (meter provider)**: without it, a dead TIC hat on a live
  ESP32 rebroadcasts frozen values forever and no fallback engages (proven
  by ESPHome source reading, QA finding M3). The watchdog (`tic_timeout_ms`,
  default 15 s) invalidates the six broadcast quantities to NAN, which
  cascades to fail-safe on the charger node.
- **Anti-glitch plausibility firewall**: measurement input filter on the
  charger node. R1: physical floor with the contactor closed (a service
  meter can never read below the wallbox's own draw). R2: sudden drops
  above 5 A must be confirmed by a second sample. Rises always pass
  immediately (the transient error is on the safe side). Design:
  `docs/DESIGN_ANTI_GLITCH.md`.
- **Direct STOP**: the `Charge Stop` switch immediately publishes the stop
  order (limit plus nudge, dithered). Never restored at boot: a deliberate
  stop cannot silently survive a reboot.
- **Meter-absent test switch**: `Meter Absent (test)` silences the Modbus
  server at runtime (hot slave-address change) to exercise the wallbox's
  documented "loss of meter" 6 A fallback. Shipped OFF, never restored at
  boot. Design: `docs/DESIGN_METER_ABSENT.md`.
- Escalation stop (120 s at zero headroom publishes limit + 0.1 A,
  dithered), bias target with firmware-side ramp, fail-safe publication of
  the main breaker value with source priority UDP > HA mirror > fail-safe,
  all carried over from the production-validated reference block.

## Integration (custom_components/loadpilot)

- **Config flow, 5 steps**: meter profile, node names (existence checked),
  electrical parameters (installation type, France kVA presets, contract
  limit, buffer, with `budget_too_small` and `tri_limit_suspicious`
  validations), HA mirror mapping, confirmation summary. Options flow for
  later adjustments.
- **Entity mapping layer**: `entity_overrides` (opt-in "advanced mapping"
  options step) remaps any tracked charger-node entity to an arbitrary
  entity_id; fail-safe detection depends only on the six essential
  measurements.
- **5 derived sensors**: regulation state (enum), per-phase headroom (3),
  worst phase. Contractual entity ids pinned in English
  (`sensor.loadpilot_state`, `sensor.loadpilot_headroom_l1/l2/l3`,
  `sensor.loadpilot_worst_phase`).
- **3 services**: `loadpilot.set_bias`, `loadpilot.pause`,
  `loadpilot.resume`.
- **Repairs**: firmware/integration version skew, fail-safe source active,
  charger node missing from the entity registry.
- **Diagnostics** export for support bundles.
- Full EN/FR translations (identical key trees).

## Known limitations

- **Entity ids on translated instances**: recent Home Assistant releases
  (observed on 2026.8) ignore `suggested_object_id`, so the derived sensors
  can be created with translated object ids on a non-English instance (for
  example `sensor.loadpilot_etat` instead of `sensor.loadpilot_state`).
  Workaround: rename the five entities to the contractual ids listed above
  (Settings > Devices and services > Entities). The dashboards and docs
  assume the English ids.
- **Pilot node requires mapping**: the pilot site's charger node predates
  the generic package naming, so the advanced entity mapping step is
  required there. Fresh installs that follow `twc-core.yaml` naming do not
  need it.
- **Variant B is not closed-loop tested**: design only, see above. The exit
  yo-yo of the v2 law is a known, bounded behaviour until then.
- **Distrust layer is partially inferred**: the wallbox's latched distrust
  state is characterised from field episodes and community corroboration,
  with statements labelled MEASURED / INFERRED / REPORTED in
  `docs/BEHAVIOR.md` section 4. Expect refinements at the next episode.
- **Physical fault-injection tests remain**: the TIC watchdog was proven by
  source reading; the physical unplug test (TESTPLAN case C6, QA finding
  M3) and the meter-absent 6 A fallback test have not been run yet.
- **Calibration is tied to TWC firmware 26.18**: a wallbox firmware update
  requires re-calibration of the measured law.

## Documentation

- `docs/BEHAVIOR.md`: the measured behaviour model of the TWC Gen 3 load
  management (English), including the distrust state (section 4).
- `docs/RUNBOOK_INCIDENTS.md`: operator runbook for incidents.
- `docs/TESTPLAN.md`: acceptance and fault-injection test plan.
- `docs/INSTALL_FR.md`: step-by-step installation guide (French).

## Credits and license

Founding prior art: [PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control)
(Neurio emulation concept, Modbus register structure, escalation stop
technique). Licensing conversation in progress; nothing derived is
published. Neurio identity block constants from LucaTNT's register-map
gist. No license is granted yet (see `LICENSE.placeholder`); all rights
reserved until the attribution agreement is settled.

This project is not affiliated with, endorsed by, or sponsored by
Tesla, Inc.
