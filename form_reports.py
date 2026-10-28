#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-28.
"""Pull job reports from the Google Form's published responses sheet into data/outcomes/.

The sheet's "Publish to web -> CSV" link goes in form_csv_url.txt (one line). Writes:
- data/outcomes/form.csv: one row per response (date, shift, pick, class, got, hours, spin, offered, cutoff, notes)
- data/outcomes/form_cutoffs.csv: day/regular-pick B reports that give where skill 3 / skill ran out, parsed
  from "hours/spin" text, for score.py. Free-text answers are kept as written; review them before relying on them.
Columns are found by their question wording, so reordering the form is fine; renaming a question needs a tweak here.
"""
import csv
import datetime as dt
import io
import pathlib
import re
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "data" / "outcomes"
Q = {"date": "date you are reporting", "shift": "day or night", "class": "b man or casual", "got": "what did you get",
     "hs": "what hours and spin", "offered": "were you offered", "notes": "any other information", "cutoff": "ran out"}


def hours_spin(text):
    """'12/94', '12 hrs spin 94', '12 / 94' -> (12.0, 94); None if not found."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)?\s*[/,\s]\s*(?:spin\s*)?(\d{1,3})\b", text or "", re.I)
    return (float(m.group(1)), int(m.group(2))) if m else None


def cutoff_kind(text):
    """Which cutoff a free-text answer describes: 'skill3' (strad/top pick), 'skill' (trucks etc.), or None if unclear."""
    t = (text or "").lower()
    if re.search(r"skill\s*3|strad|top\s*pick|t/?p\b|skill3", t):
        return "skill3"
    if re.search(r"truck|hust|\bskill\b", t):
        return "skill"
    return None


def parse_date(text, stamp):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    try:   # fall back to the response timestamp's date
        return dt.datetime.strptime(stamp.split()[0], "%m/%d/%Y").date()
    except ValueError:
        return None


def main():
    url = (HERE / "form_csv_url.txt").read_text().strip()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    rows = list(csv.reader(io.StringIO(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))))
    hdr = [h.lower() for h in rows[0]]
    col = {k: next((i for i, h in enumerate(hdr) if q in h), None) for k, q in Q.items()}
    get = lambda r, k: r[col[k]].strip() if col[k] is not None and col[k] < len(r) else ""
    out, cuts = [], []
    for r in rows[1:]:
        day = parse_date(get(r, "date"), r[0])
        if not day:
            continue
        sp = get(r, "shift").lower()
        shift, pick = ("night" if "night" in sp else "day"), ("flex" if "flex" in sp else "regular")
        hs = hours_spin(get(r, "hs"))
        out.append({"date": day.isoformat(), "shift": shift, "pick": pick, "class": get(r, "class"), "got": get(r, "got"),
                    "hours": hs[0] if hs else "", "spin": hs[1] if hs else "", "offered": get(r, "offered"),
                    "cutoff": get(r, "cutoff"), "notes": get(r, "notes")})
        c = hours_spin(get(r, "cutoff"))
        if c and shift == "day" and pick == "regular":
            kind = cutoff_kind(get(r, "cutoff"))
            if kind:
                cuts.append({"date": day.isoformat(), "shift": "day", "kind": kind, "hours": c[0], "spin": c[1],
                             "bound": "exact", "notes": f"Form report: {get(r, 'cutoff')}"})
    for path, data, fields in ((OUT / "form.csv", out, list(out[0]) if out else []),
                               (OUT / "form_cutoffs.csv", cuts, ["date", "shift", "kind", "hours", "spin", "bound", "notes"])):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields or ["date"])
            w.writeheader()
            w.writerows(data)
    print(f"{len(out)} responses, {len(cuts)} usable day/regular cutoffs")


if __name__ == "__main__":
    main()
