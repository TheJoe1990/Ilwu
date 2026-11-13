#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Score saved guesses (data/guess/history.json) against reported cutoffs (data/outcomes/cutoffs.csv).

Error = guessed hours minus reported hours for the last skill-3 / skill job (an "at_least" report only counts
a guess that was too shallow; "not_out" = it never ran out among B men, right if the guess said it likely
wouldn't, and a guess that said it would run out counts as a miss with no hours). Writes data/guess/score.json for the app and prints a table.
"""
import csv
import json
import pathlib

from guess import people_ahead

HERE = pathlib.Path(__file__).resolve().parent


def main():
    hist = json.loads((HERE / "data" / "guess" / "history.json").read_text())
    rows, tot, missed = [], {"schedule": [], "board": []}, {"schedule": [], "board": []}
    ppl = {"schedule": [], "board": []}   # people off (user, 2026-11-13: hours off means more early in the week)
    reports = list(csv.DictReader(open(HERE / "data" / "outcomes" / "cutoffs.csv")))
    form = HERE / "data" / "outcomes" / "form_cutoffs.csv"   # from form_reports.py
    if form.exists():
        reports += list(csv.DictReader(open(form)))
    # One report per day and kind: an exact cutoff beats a lower bound (same rule as guess.reported()).
    best = {}
    for c in reports:
        k = (c["date"], c["kind"], c["shift"])
        if k not in best or (best[k]["bound"] == "at_least" and c["bound"] != "at_least"):
            best[k] = c
    for c in best.values():
        if c["shift"] != "day":
            continue
        for basis, g in hist.get(c["date"], {}).items():
            if basis.startswith("_"):
                continue
            mid = g.get(c["kind"], {}).get("mid")
            if c["bound"] == "not_out":
                # Reported: that kind never ran out among B men. Right if the guess said it likely wouldn't.
                ok = not mid or g[c["kind"]].get("p_runs_out", 1) < 0.5
                rows.append({"date": c["date"], "kind": c["kind"], "basis": basis, "guess": [mid["hours"], mid["spin"]] if mid else None,
                             "reported": "not out", "off_hours": 0.0 if ok else None})
                tot[basis].append(0.0) if ok else missed[basis].append(c["date"])
                continue
            if not mid:
                continue
            err = mid["hours"] - float(c["hours"])
            if c["spin"]:   # spin breaks ties in line: a full spin range (~350) counts as 2 hrs, one weekday truck
                err += (mid["spin"] - int(c["spin"])) / 175
            if c["bound"] == "at_least" and err >= 0:
                err = 0.0
            # People off: B men the model expects in line between the guessed and reported cutoff. Uses the line
            # saved with the guess, or one rebuilt later for older guesses (history "_line").
            line = g.get("line") or hist[c["date"]].get("_line")
            po = None
            if line:
                rs = int(c["spin"]) if c["spin"] else None
                po = people_ahead(line, mid["hours"], mid["spin"] if rs is not None else None) - people_ahead(line, float(c["hours"]), rs)
                if c["bound"] == "at_least" and po >= 0:
                    po = 0.0
                po = round(po)
                ppl[basis].append(abs(po))
            rows.append({"date": c["date"], "kind": c["kind"], "basis": basis, "guess": [mid["hours"], mid["spin"]],
                         "reported": [float(c["hours"]), int(c["spin"]) if c["spin"] else None], "off_hours": round(err, 1),
                         "off_people": po})
            tot[basis].append(abs(err))
    summary = {b: {"days": len(v), "avg_off_hours": round(sum(v) / len(v), 1) if v else None,
                   "avg_off_people": round(sum(ppl[b]) / len(ppl[b])) if ppl[b] else None, "people_days": len(ppl[b]),
                   "missed_not_out": len(missed[b])} for b, v in tot.items()}
    (HERE / "data" / "guess" / "score.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    for r in rows:
        print(f"{r['date']} {r['kind']:<6} {r['basis']:<8} guessed {r['guess']}  reported {r['reported']}  off {r['off_hours']} hrs / {r.get('off_people')} people")
    for b, s in summary.items():
        print(f"{b}: {s['days']} days scored, avg off {s['avg_off_hours']} hrs, {s['avg_off_people']} people ({s['people_days']} days); "
              f"{s['missed_not_out']} said it would run out when it didn't")


if __name__ == "__main__":
    main()
