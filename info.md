# Tesla LoadPilot

**Local, cloud-free dynamic charging for the Tesla Wall Connector Gen 3.**

An ESP32 emulates the discontinued Neurio meter on the wallbox's RS485 bus
and publishes your home's real consumption, measured at the utility meter
(France: Linky) and shipped over encrypted UDP. The wallbox's own load
management then modulates the vehicle — smoothly, locally, and **without
ever tripping: the published signal is clamped below the limit by
construction.**

This integration provides the config flow, derived sensors (regulation
state, per-phase headroom, worst phase), services (bias, pause/resume) and
Repairs. It is an observer and installer — **regulation and protection run
entirely in the ESP32 firmware** and keep working with Home Assistant down.

The matching firmware is consumed as ESPHome remote packages from the same
repository, pinned to the same release tag. See the README for the full
hardware list, the installation guide, and the measured behaviour model of
the TWC Gen 3 (firmware 26.18).

Works with any vehicle plugged into the wallbox, guests included.

> This project is not affiliated with, endorsed by, or sponsored by
> Tesla, Inc. Prior art and inspiration:
> [PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control).
