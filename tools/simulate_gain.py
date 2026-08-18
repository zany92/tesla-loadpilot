#!/usr/bin/env python3
"""Closed-loop simulator: publication law + measured pilot hysteresis.

Composes the pure law mirror (tests/law_model.py, faithful to
esphome/packages/twc-core.yaml) with a pilot automaton built from the
measured TWC behavior model (docs/en/BEHAVIOR.md, sections 11-12):

- at rest the pilot only engages a downward correction once the
  published value reaches about L + 0.85;
- while pulling it follows down at ~1 A/s until published = L;
- below L it ramps back up toward the vehicle setpoint at ~1 A/s;
- in [L, L + 0.85) at rest it holds (dead band).

What this CAN answer: how law knobs (gain, excursion, tail, buffer)
shape engagement, equilibrium and oscillation against a house profile.
What it CANNOT answer: meter distrust (it lives inside the charger) and
protection integrals. Bench-test anything trust-related.

Key finding baked into the default report (18 Aug 2026): parking above
budget when approaching from below is governed by the pilot's ramp
overshoot (~0.5-0.9 A of reaction latency), not by the gain; the gain
would need to exceed ~1.1 for the overshoot to self-trigger the pull,
which is unexplored trust territory. External nudges (integration trim,
firmware stage-2 escalation) are the right tool for parking.

Usage:
  python3 tools/simulate_gain.py                # default report, 3 gains
  python3 tools/simulate_gain.py --gain 0.75 --house 5 --setpoint 16
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "law_model", _ROOT / "tests" / "law_model.py")
law = importlib.util.module_from_spec(_spec)
sys.modules["law_model"] = law
_spec.loader.exec_module(law)

ENGAGE_ABOVE_L = 0.85   # measured engagement threshold from rest
PILOT_RAMP_APS = 1.0    # measured pull/rise slope, A/s


def simulate(gain, house_fn, setpoint=16.0, t_end=900.0, dt=1.0,
             buffer_pct=8.0, tail_r0=0.0):
    params = law.LawParams(gain=gain, buffer_pct=buffer_pct,
                           tail_r0_a=tail_r0,
                           dither_a=0.0, escalation_kick_a=0.0)
    state = law.LawState()
    car, pulling = 0.0, False
    hist = []
    steps = int(t_end / dt)
    for i in range(steps):
        t = i * dt
        house = house_fn(t)
        worst = house + car
        inputs = law.LawInputs(
            t_s=t, currents_a=(worst, worst, worst),
            contactor_closed=car > 0.2, contactor_mirror_ok=True,
            have_measure=True, control_enabled=True,
            charge_stop=False, law_active=True)
        pub, state = law.publish(inputs, state, params)
        limit = params.conductor_limit_a
        if pulling:
            if pub > limit:
                car = max(0.0, car - PILOT_RAMP_APS * dt)
            else:
                pulling = False
        else:
            if pub >= limit + ENGAGE_ABOVE_L and car > 0.3:
                pulling = True
            elif pub < limit and car < setpoint:
                car = min(setpoint, car + PILOT_RAMP_APS * dt)
        hist.append((t, house, car, pub))
    return hist, params


def metrics(hist, budget, t_from=300.0):
    seg = [h for h in hist if h[0] >= t_from]
    worst = [h[1] + h[2] for h in seg]
    cars = [h[2] for h in seg]
    return (sum(worst) / len(worst) - budget,
            (max(cars) - min(cars)) / 2.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gain", type=float, default=None)
    ap.add_argument("--house", type=float, default=5.0)
    ap.add_argument("--setpoint", type=float, default=16.0)
    ap.add_argument("--buffer", type=float, default=8.0)
    ap.add_argument("--tail", type=float, default=0.0)
    args = ap.parse_args()

    gains = [args.gain] if args.gain else [0.5, 0.75, 1.0]
    budget = 21.7 * (1 - args.buffer / 100.0)
    print(f"budget = {budget:.2f} A (buffer {args.buffer:g} %)\n")

    print(f"S1: approach from below (house {args.house:g} A steady, "
          f"setpoint {args.setpoint:g} A)")
    for g in gains:
        hist, p = simulate(g, lambda t: args.house,
                           setpoint=args.setpoint,
                           buffer_pct=args.buffer, tail_r0=args.tail)
        park, amp = metrics(hist, budget)
        print(f"  gain {g}: parking {park:+.2f} A vs budget, "
              f"oscillation +/-{amp:.2f} A")

    print("\nS2: breathing house (steady + 3 A blocks every 120 s)")
    for g in gains:
        hist, p = simulate(
            g, lambda t: args.house + (3.0 if (t // 120) % 2 else 0.0),
            setpoint=args.setpoint, buffer_pct=args.buffer,
            tail_r0=args.tail)
        park, amp = metrics(hist, budget)
        print(f"  gain {g}: mean {park:+.2f} A vs budget, "
              f"oscillation +/-{amp:.2f} A")

    print("\nS3: deep constraint (8 A appliance between t=300 and 600)")
    for g in gains:
        hist, p = simulate(
            g, lambda t: 4.0 + (8.0 if 300 <= t < 600 else 0.0),
            setpoint=args.setpoint, buffer_pct=args.buffer,
            tail_r0=args.tail)
        cars = [h[2] for h in hist if 320 <= h[0] < 600]
        worst = [h[1] + h[2] for h in hist if 320 <= h[0] < 600]
        print(f"  gain {g}: vehicle min {min(cars):.1f} / "
              f"mean {sum(cars)/len(cars):.1f} A, worst-phase max "
              f"{max(worst):.1f} A, mean {sum(worst)/len(worst)-budget:+.2f} "
              f"vs budget")


if __name__ == "__main__":
    main()
