#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-23.
"""Count skill-3 (strad/top pick) and truck jobs on a posted day board.

Board columns: VESSEL, TERMINAL, UNITS (gangs: "4 NEW", "3 BACK"), CRANE, X-MEN, SK, PD, LASH, BUS, then free text.
Columns are hand-typed and drift, so this reads job words from every cell instead of trusting positions.

Rules (user, 2026-10-23):
- NEW gangs = newly hired cranes, one gang per crane. BACK gangs are A men holding, not open.
- PCT (Evergreen): 4 strads per gang.
- WUT: 5-6 trucks and at least one top pick per gang.
- Husky (P3/P4): wild card, up to 8 trucks per gang.
- Reach stacker and side pick (S/PICK) count as top picks. T/TAINER (transtainer) needs crane training and is
  A men only, so it's not counted. H/LIFT = forklift, POWER = mechanic, DRIVERS/AUTOS = car ship,
  STRYKER = military equipment with its own certification: none of these are skill 3 or trucks.
When a ship row lists STRAD or HUST explicitly, the explicit count wins over the per-gang rule.
"""
import argparse
import html
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
SKILL3 = re.compile(r"(\d+)\s*(?:STRADS?|T/PICKS?|R/STACK|S/PICKS?)\b")
TRUCK = re.compile(r"(\d+)\s*(?:TOTE\s+)?(?:HUST\.?|HT)\b")
GANGS = re.compile(r"(\d+)\s*NEW\b")
PER_GANG = {"PCT": (4, 0), "WUT": (1, 5.5), "HUSKY": (0, 6)}   # (skill 3, trucks) per new gang when not listed


def terminal(t):
    t = t.replace(" ", "").replace("-", "").upper()
    if t.startswith("PCT"):
        return "PCT"
    if t.startswith("WUT"):
        return "WUT"
    if t.startswith(("P3", "P4", "HUSKY")):
        return "HUSKY"
    return t


def rows(path):
    t = path.read_text(errors="replace")
    for row in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        c = [html.unescape(x).strip().upper() for x in re.findall(r'">([^<]*)</a></td>', row)]
        if any(c):
            yield c


def count(path):
    """{'skill3', 'trucks', 'detail': [...]} for one board version."""
    s3 = tr = 0
    detail = []
    for c in rows(path):
        name, term = c[0], terminal(c[1]) if len(c) > 1 else ""
        if term.startswith(("CG", "C.G")) or name.startswith("C.G"):
            continue   # grain: HT/WD there aren't skill trucks
        cells = " | ".join(c[1:])
        a = sum(int(n) for n in SKILL3.findall(cells))
        b = sum(int(n) for n in TRUCK.findall(cells))
        gangs = sum(int(n) for n in GANGS.findall(c[2] if len(c) > 2 else ""))
        ga, gb = PER_GANG.get(term, (0, 0))
        how = []
        if not a and gangs and ga:
            a, how = gangs * ga, how + [f"{gangs} new gangs x {ga} skill 3"]
        if not b and gangs and gb:
            b, how = round(gangs * gb), how + [f"{gangs} new gangs x {gb:g} trucks"]
        if a or b:
            detail.append({"row": name, "terminal": term, "skill3": a, "trucks": b, "from": how or ["listed"]})
        s3 += a
        tr += b
    return {"skill3": s3, "trucks": tr, "detail": detail}


def final_versions():
    idx = json.load(open(HERE / "data" / "boards" / "index.json"))["day"]
    out = {}
    for d, versions in sorted(idx.items()):
        # Prefer versions whose header matches the date (others can be the prior day's board still up);
        # if none match (header lag), take the fullest version.
        good = [e for e in versions if e.get("header", d) == d] or versions
        best = max(reversed(good), key=lambda e: len(list(rows(HERE / "data" / "boards" / "day" / e["file"]))))
        if list(rows(HERE / "data" / "boards" / "day" / best["file"])):
            out[d] = HERE / "data" / "boards" / "day" / best["file"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="one day (YYYY-MM-DD) with per-row detail")
    a = ap.parse_args()
    boards = final_versions()
    if a.date:
        r = count(boards[a.date])
        for x in r["detail"]:
            print(f"  {x['row']:<22} {x['terminal']:<8} skill3 {x['skill3']:>3}  trucks {x['trucks']:>3}  ({'; '.join(x['from'])})")
        print(f"{a.date}: skill 3 {r['skill3']}, trucks {r['trucks']}")
        return
    for d, p in boards.items():
        r = count(p)
        print(f"{d}: skill 3 {r['skill3']:>3}  trucks {r['trucks']:>3}")


if __name__ == "__main__":
    main()
