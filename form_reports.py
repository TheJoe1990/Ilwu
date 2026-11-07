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
    """'12/94', '12 hrs spin 94', '8 with a 122' -> (12.0, 94): first number is hours, second is spin; None if not two."""
    text = re.sub(r"skill\s*3", " ", text or "", flags=re.I)   # the "3" in "skill 3" isn't hours
    n = re.findall(r"\d+(?:\.\d+)?", text)
    if len(n) < 2:
        return None
    a, b = float(n[0]), float(n[1])
    if a > 40 >= b:   # "85 with 0": logged hours never get that high in a week, so it's spin first
        a, b = b, a
    return (a, int(b)) if b <= 400 else None


def cutoff_kind(text):
    """Which cutoff a free-text answer describes: 'skill3' (strad/top pick), 'skill' (trucks etc.), or None if unclear."""
    t = (text or "").lower()
    if re.search(r"skill\s*3|strad|top\s*pick|toppick|t/?p\b|skill3", t):
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
            # Cutoff answers are skill 3 unless they say trucks (user, 2026-10-28: truck cutoffs are rarely seen).
            kind = cutoff_kind(get(r, "cutoff")) or "skill3"
            if kind:
                cuts.append({"date": day.isoformat(), "shift": "day", "kind": kind, "hours": c[0], "spin": c[1],
                             "bound": "exact", "notes": f"Form report: {get(r, 'cutoff')}"})
    # Someone at regular pick who got skill 3 shows it went at least that deep (lower bound), unless the day
    # already has a reported cutoff.
    have = {(c["date"], c["kind"]) for c in cuts}
    deepest = {}
    for o in out:
        if o["shift"] == "day" and o["pick"] == "regular" and o["hours"] != "" and cutoff_kind(o["got"]) == "skill3":
            k = o["date"]
            if (k, "skill3") not in have and (k not in deepest or (o["hours"], o["spin"]) > deepest[k][:2]):
                deepest[k] = (o["hours"], o["spin"], o["got"])
    for k, (h, s, got) in sorted(deepest.items()):
        cuts.append({"date": k, "shift": "day", "kind": "skill3", "hours": h, "spin": s, "bound": "at_least",
                     "notes": f"Form report: a B at {h:g}/{s} got {got}"})
    for path, data, fields in ((OUT / "form.csv", out, list(out[0]) if out else []),
                               (OUT / "form_cutoffs.csv", cuts, ["date", "shift", "kind", "hours", "spin", "bound", "notes"])):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields or ["date"])
            w.writeheader()
            w.writerows(data)
    print(f"{len(out)} responses, {len(cuts)} usable day/regular cutoffs")


if __name__ == "__main__":
    main()
