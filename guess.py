#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Guess where skill jobs run out on upcoming day shifts, for the app's "Guess" button.

For each target day, simulates the B line from the last hours reset (Sat/Mon) through that day with sim.py's
model, and reports the typical (hours, spin) of the last B to get a skill-3 job (strad/top pick) and the last
B to get any skill job (incl. trucks). Writes data/guess/latest.json.

The model is still rough: it is calibrated on one person's timebook and gets better with reported outcomes.
"""
import argparse
import datetime as dt
import json
import pathlib

import sim

HERE = pathlib.Path(__file__).resolve().parent
PT = dt.timezone(dt.timedelta(hours=-7))   # close enough for picking "today"; DST error only shifts the cutoff hour


def last_reset(day):
    while not sim.period_start(day):
        day -= dt.timedelta(days=1)
    return day


def summary(cuts):
    """cuts: per-run (hours, spin) or None. Middle of the runs that ran out, in line order, plus a range."""
    hit = sorted(c for c in cuts if c is not None)
    out = {"p_runs_out": round(len(hit) / len(cuts), 2) if cuts else None}
    if hit:
        q = lambda f: {"hours": hit[int(f * (len(hit) - 1))][0], "spin": hit[int(f * (len(hit) - 1))][1]}
        out.update(mid=q(.5), early=q(.25), late=q(.75))
    return out


def guess(day, runs):
    start = last_reset(day)
    world = sim.setup(start, (day - start).days + 1)
    res = sim.simulate(world, sim.load_params(), None, runs)
    i = len(world["days"]) - 1
    d = world["days"][i]
    ships = sim.demand(world, sim.load_params(), [dt.timedelta(0)] * len(world["vessels"]))[i]
    return {"date": day.isoformat(), "no_work": d["no_work"], "ships": ships["ships"], "pct": ships["pct"],
            "skill3": summary(res["cut_good"][i]), "skill": summary(res["cut_skill"][i])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="how many days to guess, starting with the next day shift")
    ap.add_argument("--runs", type=int, default=400)
    a = ap.parse_args()
    now = dt.datetime.now(PT)
    first = now.date() + dt.timedelta(days=0 if now.hour < 8 else 1)   # day dispatch is done by ~8am
    out = {"made": now.isoformat(timespec="minutes"), "basis": "vessel schedule (not yet the posted board)",
           "days": [guess(first + dt.timedelta(days=k), a.runs) for k in range(a.days)]}
    p = HERE / "data" / "guess" / "latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + "\n")
    for g in out["days"]:
        s3, sk = g["skill3"], g["skill"]
        f = lambda s: f"{s['mid']['hours']:g} hrs / spin {s['mid']['spin']} (ran out in {s['p_runs_out']:.0%} of runs)" if "mid" in s else "didn't run out"
        print(f"{g['date']}: skill 3 out ~{f(s3)}; all skill out ~{f(sk)}")


if __name__ == "__main__":
    main()
