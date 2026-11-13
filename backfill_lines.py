#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-11-13.
"""One-off: rebuild the expected line ({logged hours: B men}) for past guesses saved before guess.py stored it,
so score.py can score them in people. Stored as history.json[date]["_line"]; existing guesses are untouched."""
import datetime as dt
import json
import pathlib

import guess

HERE = pathlib.Path(__file__).resolve().parent
hp = HERE / "data" / "guess" / "history.json"
hist = json.loads(hp.read_text())
boards = guess.posted_boards()
for d, entry in sorted(hist.items()):
    if "_line" in entry or all("line" in v for k, v in entry.items() if not k.startswith("_")):
        continue
    day = dt.date.fromisoformat(d)
    if day >= dt.date.today():
        continue
    entry["_line"] = guess.guess(day, 200, boards)["line"]
    print(d, entry["_line"], flush=True)
hp.write_text(json.dumps(hist, indent=1, sort_keys=True) + "\n")
