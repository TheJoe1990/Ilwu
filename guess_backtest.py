#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Try different guess weightings against reported skill-3 cutoffs (data/outcomes + notes).

Each variant changes how much turnout follows today's work and the day before's, and whether the posted board's
skill-3 count (times the share left after A men) replaces the per-ship guess. Prints each variant's guessed
cutoff next to what was reported. Very few reports so far: treat the ranking as a hint, not a fit.
"""
import datetime as dt
import itertools

import board_jobs
import guess
import sim

# Reported last skill-3 job (hours, spin). 10-22 is a lower bound (a friend got a strad at 18/283).
OBSERVED = {"2026-10-21": (12, 94), "2026-10-22": (18, 283), "2026-10-23": (28, 185)}


def run(day, P, boards, b_share, runs=150):
    start = guess.last_reset(day)
    world = sim.setup(start, (day - start).days + 1)
    world["board"] = {d: sim.board_vessels(world, r) for d, r in boards.items() if start <= d <= day}
    if b_share is not None:
        counts = board_jobs.final_versions()
        world["good_override"] = {d: board_jobs.count(counts[d.isoformat()])["skill3"] * b_share
                                  for d in world["board"] if d.isoformat() in counts}
    res = sim.simulate(world, P, None, runs)
    return guess.summary(res["cut_good"][len(world["days"]) - 1])


def main():
    boards = guess.posted_boards()
    base = sim.load_params()
    variants = [("now", 0, 0, None)]
    variants += [(f"today^{a} prev^{b} board x{k}", a, b, k)
                 for a, b, k in itertools.product((0, 1, 2), (0, 1, 2), (None, 0.5, 0.75))][1:]
    rows = []
    for name, a, b, k in variants:
        P = dict(base, turnout_today_exp=a, turnout_prev_exp=b)
        err, cells = 0, []
        for d, (h, sp) in OBSERVED.items():
            g = run(dt.date.fromisoformat(d), P, boards, k)
            mid = g.get("mid")
            gh = mid["hours"] if mid else 40
            err += abs(gh - h)
            cells.append(f"{gh:>4g}/{mid['spin'] if mid else '-':<4}")
        rows.append((err, name, cells))
        print(f"{name:<28} err {err:>5g} hrs   " + "  ".join(cells), flush=True)
    print("\nobserved                                 " + "  ".join(f"{h:>4g}/{s:<4}" for h, s in OBSERVED.values()))
    print("best:", sorted(rows)[:3])


if __name__ == "__main__":
    main()
