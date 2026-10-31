#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Guess where skill jobs run out on upcoming day shifts, for the app's "Guess" button.

Before a day's board posts (~2pm the day before) the guess comes from the vessel schedule. After it posts, the
board's ship list and skill-3 count replace the schedule's for that day ("basis": "board"). Reported cutoffs on
earlier days of the same hours period steer the guess toward runs that matched them (weights()).

For each target day, simulates the B line from the last hours reset (Sat/Mon) through that day with sim.py's
model, and reports the typical (hours, spin) of the last B to get a skill-3 job (strad/top pick) and the last
B to get any skill job (incl. trucks). Writes data/guess/latest.json.

The model is still rough: it is calibrated on one person's timebook and gets better with reported outcomes.
"""
import argparse
import csv
import datetime as dt
import json
import math
import pathlib
import random

import board_backtest
import board_jobs
import outlook
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


def reported():
    """{(date, kind): (hours, spin or None, bound)} from data/outcomes/cutoffs.csv and the form import."""
    out = {}
    for name in ("cutoffs.csv", "form_cutoffs.csv"):
        f = HERE / "data" / "outcomes" / name
        if f.exists():
            for c in csv.DictReader(open(f)):
                if c["shift"] == "day":
                    out[(c["date"], c["kind"])] = (float(c["hours"]) if c["hours"] else None,
                                                   int(c["spin"]) if c["spin"] else None, c["bound"])
    return out


def weights(res, days, reports):
    """Per-run weights from reported cutoffs on the days before the target (user, 2026-10-31: yesterday's
    dispatch tells us who showed up and who is still low on hours). Runs whose earlier days ran out near where
    they really did count more. Beat the unweighted guess on the 6 reported days (15.1 vs 16.8 hrs off)."""
    n = len(res["cut_good"][0]) if res["cut_good"] else 0
    w = [1.0] * n
    pos = lambda h, s: h + (s if s is not None else 175) / 175   # a full spin range ~= 2 hrs
    for j, d in enumerate(days[:-1]):
        for kind, key in (("skill3", "cut_good"), ("skill", "cut_skill")):
            rep = reports.get((d["day"].isoformat(), kind))
            if not rep:
                continue
            h, s, bound = rep
            for r in range(n):
                c = res[key][j][r]
                if bound == "not_out":
                    w[r] *= 1.0 if c is None else 0.2
                elif h is not None:
                    e = 6.0 if c is None else pos(c[0], c[1] if s is not None else None) - pos(h, s)
                    if bound == "at_least":
                        e = min(e, 0)
                    w[r] *= math.exp(-0.5 * (e / 1.5) ** 2)
    return w


def posted_boards():
    """{date: board ship rows} for day boards that have posted (see board_jobs.final_versions)."""
    out = {}
    for d, path in board_jobs.final_versions().items():
        rows = board_backtest.board_ships(path)
        if rows:
            out[dt.date.fromisoformat(d)] = rows
    return out


def guess(day, runs, boards):
    start = last_reset(day)
    world = sim.setup(start, (day - start).days + 1)
    # Past days and the target day use their posted boards when we have them
    world["board"] = {d: sim.board_vessels(world, rows) for d, rows in boards.items() if start <= d <= day}
    # Posted boards also give the skill-3 job count (board_jobs.py); it beat the per-ship guess in guess_backtest.py
    P = sim.load_params()
    counts = board_jobs.final_versions()
    world["good_override"] = {d: board_jobs.count(counts[d.isoformat()])["skill3"] * P["board_skill3_share"]
                              for d in world["board"] if d.isoformat() in counts}
    res = sim.simulate(world, P, None, runs)
    i = len(world["days"]) - 1
    w = weights(res, world["days"], reported())
    if sum(w) > 0 and min(w) < 1:
        pick = random.Random(day.toordinal()).choices(range(len(w)), weights=w, k=len(w))
        for key in ("cut_good", "cut_skill"):
            res[key][i] = [res[key][i][r] for r in pick]
    d = world["days"][i]
    ships = sim.demand(world, sim.load_params(), [dt.timedelta(0)] * len(world["vessels"]))[i]
    if day in world["board"]:
        here = world["board"][day]
        grain = sum(t.replace(" ", "").upper().startswith(("CG", "C.G")) for _, t, _ in boards[day])
    else:
        here = [v for v in world["vessels"] if sim.on_shift(v, day, dt.timedelta(0)) and outlook.day_shift(v)]
        grain = None   # the NWSA schedule doesn't list grain ships; only the board shows them
    kinds = {"Container": "container", "Car Carrier": "car ship", "Ro-Ro": "ro-ro", "Multipurpose": "multipurpose"}
    ship_list = [{"name": v["vessel"].title(), "terminal": outlook.TERMINAL.get(v["terminal"].upper(), v["terminal"]),
                  "kind": kinds.get(v["type"], "ship")} for v in here]
    return {"date": day.isoformat(), "basis": "board" if day in world["board"] else "schedule",
            "list": ship_list, "grain": grain, "no_work": d["no_work"], "ships": ships["ships"], "pct": ships["pct"],
            "skill3": summary(res["cut_good"][i]), "skill": summary(res["cut_skill"][i])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="how many days to guess, starting with the next day shift")
    ap.add_argument("--runs", type=int, default=400)
    a = ap.parse_args()
    now = dt.datetime.now(PT)
    first = now.date() + dt.timedelta(days=0 if now.hour < 8 else 1)   # day dispatch is done by ~8am
    boards = posted_boards()
    out = {"made": now.isoformat(timespec="minutes"),
           "days": [guess(first + dt.timedelta(days=k), a.runs, boards) for k in range(a.days)]}
    p = HERE / "data" / "guess" / "latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + "\n")
    # Keep the last guess of each kind per day for scoring (score.py). Days drop out of the guess once dispatched,
    # and the before-board guess stops changing once the board posts, so each entry freezes at its final version.
    hp = HERE / "data" / "guess" / "history.json"
    hist = json.loads(hp.read_text()) if hp.exists() else {}
    for g in out["days"]:
        hist.setdefault(g["date"], {})[g["basis"]] = {"made": out["made"], "skill3": g["skill3"], "skill": g["skill"]}
    hp.write_text(json.dumps(hist, indent=1, sort_keys=True) + "\n")
    for g in out["days"]:
        s3, sk = g["skill3"], g["skill"]
        f = lambda s: f"{s['mid']['hours']:g} hrs / spin {s['mid']['spin']} (ran out in {s['p_runs_out']:.0%} of runs)" if "mid" in s else "didn't run out"
        print(f"{g['date']} ({g['basis']}): skill 3 out ~{f(s3)}; all skill out ~{f(sk)}")


if __name__ == "__main__":
    main()
