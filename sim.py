#!/usr/bin/env python3
"""Monte Carlo of the B-board dispatch line to compare day-off plans.

Each simulated day: available B men line up by (logged hours, spin); the first G get Strad/Top Pick,
the next D-G get other work, the rest get nothing. Hours accumulate and reset at the period
boundaries (Sat 00:00 and Mon 00:00), so a good job today pushes you down the line tomorrow,
and a day off moves you up. G, D and night work scale with the Tacoma vessels in port that day.

All rates live in params.json and are guesses until calibrated against daily feedback.

Goal: reach a weekly pre-tax pay target on as few days as possible. Every combination of days is
simulated; for each number of days worked it reports the best plan's expected pay and its chance of
reaching the goal.

Usage: sim.py [--start YYYY-MM-DD] [--days N] [--goal $] [--confidence P] [--hours H] [--runs N] [--calibrate]
  --hours: your logged hours so far in the current period if starting mid-period (default 0)
"""
import argparse
import datetime as dt
import itertools
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import outlook  # noqa: E402

REG = "230374"


def load_params():
    return json.load(open(HERE / "params.json"))


def period_start(day):
    return day.weekday() in (0, 5)   # Monday or Saturday: hours reset to 0


def day_inputs(start, days, P):
    """Per-day expected demand from the vessel schedule, plus every B's spin."""
    o = outlook.outlook(start, days, REG)
    data = json.load(open(HERE / "spins.json"))
    spins = {}
    for w in data["weeks"]:
        s0 = dt.date.fromisoformat(w["start"])
        for i in range(7):
            spins[s0 + dt.timedelta(days=i)] = {r: v[1 + i] for r, v in w["regs"].items() if v[0] == "B" and v[1 + i] is not None}
    out = []
    for d in o["days"]:
        day = dt.date.fromisoformat(d["date"])
        ships = len(d["vessels"])
        good_ships = d["pct_vessels"] * P["good_per_pct_ship"] + d["husky_vessels"] * P["good_per_husky_ship"]
        out.append({
            "day": day, "info": d, "spins": spins.get(day, {}),
            "no_work": d["no_work"], "full": d["full_hours_day"],
            "good_mean": P["good_base"] + good_ships,
            "day_mean": P["day_jobs_base"] + P["day_jobs_per_ship"] * ships,
            "night_mean": P["night_jobs_base"] + P["night_jobs_per_ship"] * ships,
        })
    return out


def poisson(rng, lam):
    # Knuth is fine for the small/medium lambdas here; normal approx above 30.
    if lam > 30:
        return max(0, round(rng.gauss(lam, lam ** 0.5)))
    L, k, p = pow(2.718281828, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def simulate(days, P, workdays, start_hours, runs, seed=1, random_spin=False, attend=None):
    """Return per-day P(you get Strad/Top Pick) and P(you get any work) for one plan.
    workdays: set of dates you show up (None = every day).
    random_spin: swap your spins with a random B each run (calibration).
    attend: if set, you show up on each day with this probability instead (calibration)."""
    rng = random.Random(seed)
    regs = sorted({r for d in days for r in d["spins"]} | {REG})
    n_days = len(days)
    good_hits, work_hits = [0] * n_days, [0] * n_days
    pay, earnings = P["pay"], []
    shown = [0] * n_days
    for _ in range(runs):
        alias = rng.choice([r for r in regs if r != REG]) if random_spin else REG
        swap = {REG: alias, alias: REG}
        night_people = {r for r in regs if r != REG and rng.random() < P["night_share"]}
        qualified = {r for r in regs if r != REG and rng.random() < P["qualified_share"]} | {REG}
        hours = {r: 0.0 for r in regs}
        hours[REG] = start_hours
        earned = 0.0
        for i, d in enumerate(days):
            if i > 0 and period_start(d["day"]):
                hours = dict.fromkeys(regs, 0.0)
            if d["no_work"]:
                continue
            full = d["full"]
            # Night shift first (previous evening's dispatch): night people by lowest hours, full hours logged.
            n_night = poisson(rng, d["night_mean"])
            night_avail = sorted((r for r in night_people if rng.random() < P["show_rate"]),
                                 key=lambda r: (hours[r], rng.random()))
            for r in night_avail[:n_night]:
                hours[r] += 8
            worked_night = set(night_avail[:n_night])
            # Day dispatch.
            spins = d["spins"]
            avail = [r for r in regs if r not in worked_night and
                     ((r == REG and (rng.random() < attend if attend is not None else
                                     workdays is None or d["day"] in workdays))
                      or (r != REG and rng.random() < P["show_rate"]))]
            avail.sort(key=lambda r: (hours[r], spins.get(swap.get(r, r), 999)))
            shown[i] += REG in avail
            n_good = poisson(rng, d["good_mean"])
            n_day = max(n_good, poisson(rng, d["day_mean"]))
            good_left, jobs_left = n_good, n_day
            for r in avail:
                if jobs_left == 0:
                    break
                if good_left and r in qualified:
                    good_left -= 1
                    hours[r] += 10 if full else 8
                    got = "good"
                elif jobs_left > good_left:
                    hours[r] += 8 if full else 6
                    got = "other"
                else:
                    continue   # only good jobs left and r isn't qualified
                jobs_left -= 1
                if r == REG:
                    work_hits[i] += 1
                    good_hits[i] += got == "good"
                    earned += pay[got][1 if full else 0]
        earnings.append(earned)
    if attend is not None:
        return sum(good_hits) / max(1, sum(shown)), sum(work_hits) / max(1, sum(shown))
    return ([g / runs for g in good_hits], [w / runs for w in work_hits], earnings)


def calibrate(P, a):
    """Grid-search day/good job scales over the next 3 weeks of real ship days so that a random-spin B
    who shows up like you do (attendance rate) gets work and good jobs at your historical per-day rates."""
    tw, tg, att = P["target_work_per_shown_day"], P["target_good_per_shown_day"], P["your_attendance"]
    start = a.start - dt.timedelta(days=a.start.weekday())          # a Monday
    base = day_inputs(start, 19, P)
    best = None
    for kd in (0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0):
        for kg in (0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
            days = [dict(d, day_mean=d["day_mean"] * kd, good_mean=d["good_mean"] * kg) for d in base]
            gs, ws = simulate(days, P, None, 0, 60, random_spin=True, attend=att)
            err = ((ws - tw) / tw) ** 2 + ((gs - tg) / tg) ** 2
            if not best or err < best[0]:
                best = (err, kd, kg, ws, gs)
    err, kd, kg, ws, gs = best
    print(f"best scales: day jobs x{kd}, good jobs x{kg} -> per day shown: work {ws:.0%}, good {gs:.0%} "
          f"(target {tw:.0%}, {tg:.0%})")
    for k in ("day_jobs_base", "day_jobs_per_ship"):
        P[k] = round(P[k] * kd, 2)
    for k in ("good_base", "good_per_pct_ship", "good_per_husky_ship"):
        P[k] = round(P[k] * kg, 2)
    P["_note"] = (f"Calibrated {dt.date.today()}: work {tw:.0%} / good {tg:.0%} of days shown, attendance {att:.0%}, "
                  f"other B's show {P['show_rate']:.0%}. Mostly guesses until daily feedback.")
    json.dump(P, open(HERE / "params.json", "w"), indent=2)
    print("params.json updated")


def main():
    today = dt.date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=dt.date.fromisoformat,
                    default=today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7))
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--goal", type=float, default=2000)
    ap.add_argument("--confidence", type=float, default=0.6)
    ap.add_argument("--hours", type=float, default=0.0)
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--calibrate", action="store_true",
                    help="scale job counts to match your per-day history; writes params.json")
    a = ap.parse_args()
    P = load_params()
    if a.calibrate:
        return calibrate(P, a)
    days = day_inputs(a.start, a.days, P)
    open_days = [d["day"] for d in days if not d["no_work"]]
    print(f"Params: {P['_note']}\n")
    # Per-day odds if you show up every day (context for the plans below).
    g_all, w_all, _ = simulate(days, P, None, a.hours, a.runs)
    print(f"{'day':<11}{'spin':>5} {'ships':>5}  {'P(good)':>8} {'P(hustler/other)':>17}   if you work every day")
    for d, g, w in zip(days, g_all, w_all):
        print(f"{d['day']:%a %m-%d}  {str(d['info']['spin'] or '-'):>5} {len(d['info']['vessels']):>5}  {g:>8.0%} {w - g:>17.0%}"
              + ("  NO WORK" if d["no_work"] else ""))
    # Every combination of days, scored by chance of reaching the weekly goal, then expected pay.
    best_by_k = {}
    for k in range(1, len(open_days) + 1):
        for combo in itertools.combinations(open_days, k):
            g, w, earn = simulate(days, P, set(combo), a.hours, a.runs)
            p_goal = sum(e >= a.goal for e in earn) / len(earn)
            mean = sum(earn) / len(earn)
            row = {"days": [str(c) for c in combo], "p_goal": round(p_goal, 2), "expected_pay": round(mean),
                   "good": round(sum(g), 2), "other": round(sum(w) - sum(g), 2)}
            cur = best_by_k.get(k)
            if not cur or (p_goal, mean) > (cur["p_goal"], cur["expected_pay"]):
                best_by_k[k] = row
    pick = next((r for k, r in sorted(best_by_k.items()) if r["p_goal"] >= a.confidence), None)
    if a.json:
        print(json.dumps({"goal": a.goal, "best_by_days": best_by_k, "recommended": pick}, indent=1))
        return
    print(f"\nWeekly goal ${a.goal:,.0f} pre-tax. Best plan for each number of days worked:")
    print(f"  {'days':>4}  {'work on':<30}{'P(goal)':>8}{'expected':>10}{'good':>6}{'other':>6}")
    for k, r in sorted(best_by_k.items()):
        names = " ".join(dt.date.fromisoformat(x).strftime("%a") for x in r["days"])
        print(f"  {k:>4}  {names:<30}{r['p_goal']:>8.0%}{'$' + format(r['expected_pay'], ','):>10}{r['good']:>6.2f}{r['other']:>6.2f}")
    if pick:
        names = " ".join(dt.date.fromisoformat(x).strftime("%a %m-%d") for x in pick["days"])
        print(f"\nFewest days with >= {a.confidence:.0%} chance of ${a.goal:,.0f}: {names} "
              f"({pick['p_goal']:.0%}, expected ${pick['expected_pay']:,})")
    else:
        print(f"\nNo plan reaches ${a.goal:,.0f} with >= {a.confidence:.0%} confidence this week.")

if __name__ == "__main__":
    main()
