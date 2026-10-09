#!/usr/bin/env python3
"""Monte Carlo of the B-board dispatch line to plan which days to work in a pay period (Sat-Fri).

Each simulated day: available B men line up by (logged hours, spin); the first G get Strad/Top Pick,
the next D-G get other work (mostly Hustler), the rest get nothing. You take whatever you're offered.
Hours reset Sat 00:00 and Mon 00:00, so weekend hours don't count against the weekday period.
Each run re-rolls vessel arrivals (delays, no-shows), so a plan that depends on one ship shows its risk.

Goal: reach a weekly pre-tax pay target on as few days as possible, with an optional backup day you only
work if you're behind by then. Also tracks the chance of a Matson Hustler (the one to avoid).

All rates live in params.json and are guesses until calibrated against daily feedback.

Usage: sim.py [--start YYYY-MM-DD] [--days N] [--goal $] [--confidence P] [--hours H] [--runs N] [--calibrate]
  --hours: your logged hours so far in the current period if starting mid-period (default 0)
"""
import argparse
import collections
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


def hustler_weights(tb):
    """Share of your Hustler/other shifts each terminal produced per shift there (Laplace-smoothed)."""
    n, h = collections.Counter(), collections.Counter()
    for _, job, bucket in tb:
        if bucket:
            n[bucket] += 1
            h[bucket] += job not in outlook.GOOD_JOBS
    return {b: (h[b] + 1) / (n[b] + 2) for b in set(outlook.TERMINAL.values())}


def setup(start, days):
    """Days in range (with every B's spin), the vessel list, and per-terminal odds from your timebook."""
    tb = outlook.load_timebook()
    good_rate = {b: v["rate"] for b, v in outlook.terminal_odds(tb).items()}
    vessels, source = outlook.load_vessels()
    data = json.load(open(HERE / "spins.json"))
    spins = {}
    for w in data["weeks"]:
        s0 = dt.date.fromisoformat(w["start"])
        for i in range(7):
            spins[s0 + dt.timedelta(days=i)] = {r: v[1 + i] for r, v in w["regs"].items()
                                                if v[0] == "B" and v[1 + i] is not None}
    out = []
    for i in range(days):
        day = start + dt.timedelta(days=i)
        iso = day.isoformat()
        my = spins.get(day, {}).get(REG)
        out.append({"day": day, "spins": spins.get(day, {}), "spin": my, "no_work": iso in outlook.NO_WORK,
                    "full": day.weekday() >= 5 or iso in outlook.OT_DAYS})
    return {"days": out, "vessels": [v for v in vessels if v["eta"] and v["etd"]], "source": source,
            "good_rate": good_rate, "hustler_w": hustler_weights(tb)}


def on_shift(v, day, delay):
    lo, hi = dt.datetime.combine(day, outlook.SHIFT[0]), dt.datetime.combine(day, outlook.SHIFT[1])
    return v["eta"] + delay < hi and v["etd"] + delay > lo


LASHED = {"Container", "Multipurpose", "Ro-Ro"}


def demand(world, P, delays):
    """Per-day job means and Matson-Hustler share, given one draw of vessel delays.
    'magnet' jobs are ones B men ahead of you often prefer (you don't): lashing on a ship's start/finish
    day, any job on a finishing ship (chance to go home early), and car-ship driving. They pull labor
    from ahead of you in line."""
    out = []
    for d in world["days"]:
        # Weekends/holidays pay OT, so companies order less labor (and more B men show up; see simulate()).
        wk = P["weekend_jobs_factor"] if d["full"] else 1.0
        here = [v for v, dl in zip(world["vessels"], delays) if dl is not None and on_shift(v, d["day"], dl)]
        day0 = dt.datetime.combine(d["day"], dt.time(0))
        starting = finishing = 0
        for v, dl in zip(world["vessels"], delays):
            if dl is None or v["type"] not in LASHED:
                continue
            eta, etd = v["eta"] + dl, v["etd"] + dl
            starting += day0 - dt.timedelta(hours=6) <= eta < day0 + dt.timedelta(hours=17)
            finishing += day0 + dt.timedelta(hours=6) <= etd < day0 + dt.timedelta(hours=30)
        cars = sum(v["type"] == "Car Carrier" for v in here)
        terms = [outlook.TERMINAL.get(v["terminal"].upper()) for v in here]
        pct, husky = terms.count("PCT"), terms.count("HUSKY")
        hw = [world["hustler_w"].get(t, 0.5) for t in terms]
        # Matson turns a ship in one day (usually Wed/Fri), so each call means a burst of extra work there.
        matson = terms.count("MATSON/WST")
        labor = [P["day_jobs_per_ship"] * w + (P["matson_extra_jobs_per_ship"] if t == "MATSON/WST" else 0)
                 for w, t in zip(hw, terms)]
        out.append({
            "ships": len(here), "pct": pct, "husky": husky,
            "good_mean": wk * (P["good_base"] + pct * P["good_per_pct_ship"] + husky * P["good_per_husky_ship"]),
            "day_mean": wk * (P["day_jobs_base"] + P["day_jobs_per_ship"] * len(here) + P["matson_extra_jobs_per_ship"] * matson),
            "night_mean": P["night_jobs_base"] + P["night_jobs_per_ship"] * len(here),
            "matson_share": (sum(x for x, t in zip(labor, terms) if t == "MATSON/WST") / sum(labor)) if labor else 0.0,
            "starting": starting, "finishing": finishing, "cars": cars,
            "magnet_mean": (P["lash_per_ship_event"] * (starting + finishing) + P["finish_draw_per_ship"] * finishing
                            + P["car_jobs_per_ship"] * cars),
        })
    return out


def draw_delays(world, P, rng):
    """One plausible version of the schedule: each ship slips (or rarely misses the window entirely)."""
    out = []
    for v in world["vessels"]:
        if rng.random() < P["vessel_miss_prob"] and v["status"] != "At berth":
            out.append(None)
            continue
        sd = P["berth_slip_sd_h"] if v["status"] == "At berth" else P["eta_slip_sd_h"]
        out.append(dt.timedelta(hours=rng.gauss(P["eta_slip_mean_h"], sd)))
    return out


def poisson(rng, lam):
    if lam > 30:
        return max(0, round(rng.gauss(lam, lam ** 0.5)))
    L, k, p = pow(2.718281828, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def simulate(world, P, workdays, runs, start_hours=0.0, backup=None, goal=0.0, seed=1,
             random_spin=False, attend=None):
    """Simulate one plan. Returns per-run results and per-day hit rates.
    workdays: dates you plan to show up (None = every day). backup: a date you show up only if
    pay so far + the minimum (Hustler) pay of your remaining planned days would fall short of goal.
    random_spin/attend: calibration mode (a random B who shows up with probability attend)."""
    rng = random.Random(seed)
    days = world["days"]
    regs = sorted({r for d in days for r in d["spins"]} | {REG})
    others = [r for r in regs if r != REG]
    pay = P["pay"]
    n = len(days)
    res = {"good": [0] * n, "work": [0] * n, "matson": [0.0] * n, "shown": 0,
           "earn": [], "worked": [], "matson_runs": []}
    for _ in range(runs):
        dem = demand(world, P, draw_delays(world, P, rng))
        alias = rng.choice(others) if random_spin else REG
        swap = {REG: alias, alias: REG}
        night_people = {r for r in others if rng.random() < P["night_share"]}
        # Each B has their own attendance habit (some show almost daily, some rarely), mean = show_rate.
        c = P["show_concentration"]
        habit = {r: rng.betavariate(P["show_rate"] * c, (1 - P["show_rate"]) * c) for r in others}
        qualified = {r for r in others if rng.random() < P["qualified_share"]} | {REG}
        hours = dict.fromkeys(regs, 0.0)
        hours[REG] = start_hours
        earned, worked, matson = 0.0, 0, 0.0
        for i, d in enumerate(days):
            if i > 0 and period_start(d["day"]):
                hours = dict.fromkeys(regs, 0.0)
            if d["no_work"]:
                continue
            m = dem[i]
            n_night = poisson(rng, m["night_mean"])
            night = sorted((r for r in night_people if rng.random() < habit[r]),
                           key=lambda r: (hours[r], rng.random()))[:n_night]
            for r in night:
                hours[r] += 8
            if attend is not None:
                me = rng.random() < attend
            elif backup is not None and d["day"] == backup:
                rest = [x for x in days[i + 1:] if x["day"] in workdays and not x["no_work"]]
                me = earned + sum(pay["other"][1 if x["full"] else 0] for x in rest) < goal
            else:
                me = workdays is None or d["day"] in workdays
            boost = P["weekend_show_boost"] if d["full"] else 1.0
            avail = [r for r in others if r not in night and rng.random() < min(1.0, habit[r] * boost)]
            if me:
                avail.append(REG)
                res["shown"] += 1
            spins = d["spins"]
            avail.sort(key=lambda r: (hours[r], spins.get(swap.get(r, r), 999)))
            magnet_left = poisson(rng, m["magnet_mean"])
            n_good = poisson(rng, m["good_mean"])
            jobs_left = max(n_good, poisson(rng, m["day_mean"]))
            good_left = n_good
            n_other = jobs_left - n_good
            other_rank = 0          # position among people getting non-good jobs (earlier = more choice)
            for r in avail:
                if r != REG and magnet_left and rng.random() < P["magnet_pref"]:
                    magnet_left -= 1          # lashing / finishing ship / car ship: gone from the line ahead of you
                    hours[r] += 8 if d["full"] else 6
                    continue
                if jobs_left == 0:
                    break
                if good_left and r in qualified:
                    good_left -= 1
                    hours[r] += 10 if d["full"] else 8
                    got = "good"
                elif jobs_left > good_left:
                    hours[r] += 8 if d["full"] else 6
                    got = "other"
                    other_rank += 1
                else:
                    continue   # only good jobs left and r isn't qualified
                jobs_left -= 1
                if r == REG:
                    worked += 1
                    earned += pay[got][1 if d["full"] else 0]
                    res["work"][i] += 1
                    if got == "good":
                        res["good"][i] += 1
                    elif other_rank > n_other * (1 - m["matson_share"]):
                        # You pick WUT/Husky over Matson; you only get Matson once those are gone.
                        res["matson"][i] += 1
                        matson += 1
        res["earn"].append(earned)
        res["worked"].append(worked)
        res["matson_runs"].append(matson)
    return res


def summarize(res, goal):
    e = sorted(res["earn"])
    k = len(e)
    return {"p_goal": sum(x >= goal for x in e) / k, "expected": sum(e) / k, "p10": e[k // 10],
            "days_worked": sum(res["worked"]) / k, "good": sum(res["good"]) / k,
            "other": (sum(res["work"]) - sum(res["good"])) / k, "matson": sum(res["matson_runs"]) / k}


def calibrate(P, a):
    """Grid-search day/good job scales over the next 3 weeks so that a random-spin B who shows up like you
    (attendance rate) gets work and good jobs at your historical per-day rates."""
    tw, tg, att = P["target_work_per_shown_day"], P["target_good_per_shown_day"], P["your_attendance"]
    world = setup(a.start - dt.timedelta(days=a.start.weekday()), 19)
    best = None
    for kd in (0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0):
        for kg in (0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0):
            Q = dict(P, **{k: P[k] * kd for k in ("day_jobs_base", "day_jobs_per_ship", "matson_extra_jobs_per_ship")},
                     **{k: P[k] * kg for k in ("good_base", "good_per_pct_ship", "good_per_husky_ship")})
            r = simulate(world, Q, None, 40, random_spin=True, attend=att)
            ws, gs = sum(r["work"]) / max(1, r["shown"]), sum(r["good"]) / max(1, r["shown"])
            err = ((ws - tw) / tw) ** 2 + ((gs - tg) / tg) ** 2
            if not best or err < best[0]:
                best = (err, kd, kg, ws, gs)
    err, kd, kg, ws, gs = best
    print(f"best scales: day jobs x{kd}, good jobs x{kg} -> per day shown: work {ws:.0%}, good {gs:.0%} "
          f"(target {tw:.0%}, {tg:.0%})")
    for k in ("day_jobs_base", "day_jobs_per_ship", "matson_extra_jobs_per_ship"):
        P[k] = round(P[k] * kd, 2)
    for k in ("good_base", "good_per_pct_ship", "good_per_husky_ship"):
        P[k] = round(P[k] * kg, 2)
    P["_note"] = (f"Calibrated {dt.date.today()}: work {tw:.0%} / good {tg:.0%} of days shown, attendance {att:.0%}, "
                  f"other B's show {P['show_rate']:.0%}. Mostly guesses until daily feedback.")
    json.dump(P, open(HERE / "params.json", "w"), indent=2)
    print("params.json updated")


def names(dates, fmt="%a"):
    return " ".join(d.strftime(fmt) for d in sorted(dates)) or "-"


def main():
    today = dt.date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=dt.date.fromisoformat,
                    default=today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7))   # next Saturday
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--goal", type=float, default=2000)
    ap.add_argument("--confidence", type=float, default=0.9)
    ap.add_argument("--hours", type=float, default=0.0)
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--calibrate", action="store_true", help="fit job counts to your history; writes params.json")
    a = ap.parse_args()
    P = load_params()
    if a.calibrate:
        return calibrate(P, a)
    world = setup(a.start, a.days)
    days = world["days"]
    open_days = [d["day"] for d in days if not d["no_work"]]
    goal = a.goal

    every = simulate(world, P, None, a.runs, a.hours)
    dem0 = demand(world, P, [dt.timedelta(0)] * len(world["vessels"]))
    if not a.json:
        print(f"Params: {P['_note']}\nVessels: {world['source']}\n")
        print(f"{'day':<10}{'spin':>5}{'ships':>6}{'PCT':>4}{'HSK':>4}{'start':>6}{'fin':>4}{'cars':>5}"
              f"   if you worked every day: {'good':>5}{'other':>6}{'Matson':>7}")
        for d, m, g, w, mt in zip(days, dem0, every["good"], every["work"], every["matson"]):
            print(f"{d['day']:%a %m-%d}{str(d['spin'] or '-'):>5}{m['ships']:>6}{m['pct']:>4}{m['husky']:>4}"
                  f"{m['starting']:>6}{m['finishing']:>4}{m['cars']:>5}   "
                  f"{'':>23}{g / a.runs:>5.0%}{(w - g) / a.runs:>6.0%}{mt / a.runs:>7.0%}"
                  + ("  NO WORK" if d["no_work"] else "  OT day" if d["full"] else ""))

    # 1) Fixed plans: every combination of days; keep the best per number of days.
    #    Rank: chance of goal, then bad-week pay, then fewer Matson Hustlers.
    fixed, ranked = {}, collections.defaultdict(list)
    for k in range(1, len(open_days) + 1):
        for combo in itertools.combinations(open_days, k):
            s = summarize(simulate(world, P, set(combo), a.runs, a.hours), goal)
            key = (round(s["p_goal"], 2), s["p10"], -s["matson"])
            ranked[k].append((key, set(combo), s))
            if k not in fixed or key > fixed[k][0]:
                fixed[k] = (key, set(combo), s)
    # 2) Fixed plan + one backup day (only worked if you're behind by then): the top few 2- and 3-day
    #    plans, plus the best ones with a single weekend day (the Melissa option).
    bases = []
    for k in (2, 3):
        top = sorted(ranked[k], key=lambda x: x[0], reverse=True)
        bases += [c for _, c, _ in top[:4]]
        bases += [c for _, c, _ in top if sum(x.weekday() >= 5 for x in c) <= 1][:3]
    backups, seen = [], set()
    for base in bases:
        for b in open_days:
            key = (frozenset(base), b)
            if b in base or key in seen:
                continue
            seen.add(key)
            s = summarize(simulate(world, P, base | {b}, a.runs, a.hours, backup=b, goal=goal), goal)
            backups.append((base, b, s))

    candidates = [(names(c), None, s) for _, c, s in fixed.values()] + \
                 [(names(b), x, s) for b, x, s in backups]
    ok = [c for c in candidates if c[2]["p_goal"] >= a.confidence]
    pick = min(ok, key=lambda c: (round(c[2]["days_worked"] * 2) / 2, c[2]["other"], -c[2]["p10"])) if ok else None

    if a.json:
        print(json.dumps({"goal": goal, "fixed": {k: {"days": sorted(map(str, c)), **s} for k, (_, c, s) in fixed.items()},
                          "backup_plans": [{"days": sorted(map(str, b)), "backup": str(x), **s} for b, x, s in backups],
                          "pick": pick and {"days": pick[0], "backup": str(pick[1]) if pick[1] else None, **pick[2]}},
                         indent=1, default=str))
        return
    print(f"\nPay period goal ${goal:,.0f} pre-tax. Ships randomly delayed/missing in every run.")
    print(f"  {'plan':<34}{'P(goal)':>8}{'expected':>10}{'bad wk':>8}{'days':>6}{'good':>6}{'other':>6}{'Matson':>7}")
    def row(label, s):
        print(f"  {label:<34}{s['p_goal']:>8.0%}{'$' + format(round(s['expected']), ','):>10}"
              f"{'$' + format(round(s['p10']), ','):>8}{s['days_worked']:>6.1f}{s['good']:>6.2f}{s['other']:>6.2f}{s['matson']:>7.2f}")
    for k, (_, c, s) in sorted(fixed.items()):
        row(f"work {names(c)}", s)
    for base, b, s in sorted(backups, key=lambda x: (-x[2]["p_goal"], x[2]["days_worked"]))[:5]:
        row(f"work {names(base)} + backup {b:%a}", s)
    print("  bad wk = pay in a bad week (10th percentile). Matson = expected Matson Hustler shifts.")
    # Bonus (Melissa): best plan with at most one weekend shift, shown when it's close to the pick.
    one_wknd = []
    for _, c, s2 in fixed.values():
        if sum(x.weekday() >= 5 for x in c) <= 1:
            one_wknd.append((names(c), None, s2))
    for b, x, s2 in backups:
        if sum(y.weekday() >= 5 for y in b | {x}) <= 1:
            one_wknd.append((names(b), x, s2))
    one_ok = [c for c in one_wknd if c[2]["p_goal"] >= a.confidence]
    mel = min(one_ok, key=lambda c: (round(c[2]["days_worked"] * 2) / 2, c[2]["other"], -c[2]["p10"])) if one_ok else \
        max(one_wknd, key=lambda c: (c[2]["p_goal"], c[2]["expected"]), default=None)
    if pick:
        label = f"{pick[0]}" + (f", backup {pick[1]:%a %m-%d}" if pick[1] else "")
        print(f"\nPICK: work {label}: {pick[2]['p_goal']:.0%} chance of ${goal:,.0f}, "
              f"expected ${round(pick[2]['expected']):,}, bad week ${round(pick[2]['p10']):,}, "
              f"~{pick[2]['days_worked']:.1f} days")
    else:
        print(f"\nNo plan reaches ${goal:,.0f} with >= {a.confidence:.0%} confidence.")
    if mel:
        label = f"{mel[0]}" + (f", backup {mel[1]:%a %m-%d}" if mel[1] else "")
        print(f"ONE-WEEKEND-DAY option (Melissa): work {label}: {mel[2]['p_goal']:.0%} chance, "
              f"expected ${round(mel[2]['expected']):,}, bad week ${round(mel[2]['p10']):,}, ~{mel[2]['days_worked']:.1f} days")


if __name__ == "__main__":
    main()
