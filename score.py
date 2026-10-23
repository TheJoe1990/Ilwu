#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Score saved guesses (data/guess/history.json) against reported cutoffs (data/outcomes/cutoffs.csv).

Error = guessed hours minus reported hours for the last skill-3 / skill job (an "at_least" report only counts
a guess that was too shallow). Writes data/guess/score.json for the app and prints a table.
"""
import csv
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def main():
    hist = json.loads((HERE / "data" / "guess" / "history.json").read_text())
    rows, tot = [], {"schedule": [], "board": []}
    for c in csv.DictReader(open(HERE / "data" / "outcomes" / "cutoffs.csv")):
        if c["shift"] != "day":
            continue
        for basis, g in hist.get(c["date"], {}).items():
            mid = g.get(c["kind"], {}).get("mid")
            if not mid:
                continue
            err = mid["hours"] - float(c["hours"])
            if c["bound"] == "at_least" and err >= 0:
                err = 0.0
            rows.append({"date": c["date"], "kind": c["kind"], "basis": basis, "guess": [mid["hours"], mid["spin"]],
                         "reported": [float(c["hours"]), int(c["spin"])], "off_hours": err})
            tot[basis].append(abs(err))
    summary = {b: {"days": len(v), "avg_off_hours": round(sum(v) / len(v), 1) if v else None} for b, v in tot.items()}
    (HERE / "data" / "guess" / "score.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n")
    for r in rows:
        print(f"{r['date']} {r['kind']:<6} {r['basis']:<8} guessed {r['guess'][0]:g}/{r['guess'][1]}  "
              f"reported {r['reported'][0]:g}/{r['reported'][1]}  off {r['off_hours']:+g} hrs")
    for b, s in summary.items():
        print(f"{b}: {s['days']} days scored, avg off {s['avg_off_hours']} hrs")


if __name__ == "__main__":
    main()
