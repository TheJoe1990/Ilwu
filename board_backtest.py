#!/usr/bin/env python3
# Written by Claude Code (AI) for the ILWU spin-calendar repo, 2026-10-20.
"""Backtest: predict each archived day board's ship list from the vessel schedule saved the day before.

For every day board in data/boards/, takes data/vessels/<day before>.xlsx, applies outlook.py's day-shift rules
(no night-only terminals, no afternoon arrivals, no grain) and compares with the ships on the final board.
Prints hits, misses (on the board, not predicted) and extras (predicted, not on the board) so rules can be tuned.
"""
import datetime as dt
import difflib
import html
import json
import pathlib
import re
import sys

import outlook

HERE = pathlib.Path(__file__).resolve().parent
# Board rows that are house/yard work, not ships
HOUSE = re.compile(r"\b(YARD|SHOP|GATE|RAIL|TRAIN|HOUSE|BUS)\b|^C\.?G\b|^EB#?\d|^NIM\b|^W/HYL")


def board_ships(path):
    """Vessel rows from a day board: (name, terminal, first job cell)."""
    t = path.read_text(errors="replace")
    t = t.split("HOUSE WORK")[0]
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        c = [html.unescape(x).strip() for x in re.findall(r'">([^<]*)</a></td>', row)]
        if not c or not c[0] or HOUSE.search(c[0].upper()):
            continue
        out.append((c[0].upper(), c[1].upper() if len(c) > 1 else "", c[2] if len(c) > 2 else ""))
    return out


def predicted(day):
    f = HERE / "data" / "vessels" / f"{day - dt.timedelta(days=1)}.xlsx"
    if not f.exists():
        return None
    vessels, _ = outlook.load_vessels(f.read_bytes(), f.name)
    lo, hi = (dt.datetime.combine(day, t) for t in outlook.SHIFT)
    return [v for v in vessels if v["eta"] and v["etd"] and v["eta"] < hi and v["etd"] > lo
            and outlook.day_shift(v) and outlook.arrived_for_day(v, day)
            and outlook.stays_for_day(v, day)]


def same(a, b):
    a, b = re.sub(r"[^A-Z]", "", a), re.sub(r"[^A-Z]", "", b)
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def main():
    idx = json.load(open(HERE / "data" / "boards" / "index.json"))["day"]
    tot = {"hit": 0, "miss": 0, "extra": 0}
    for d in sorted(idx):
        day = dt.date.fromisoformat(d)
        pred = predicted(day)
        if pred is None:
            continue
        # Final board = the version with the most ships (late versions can be the next day's empty skeleton)
        boards = [board_ships(HERE / "data" / "boards" / "day" / v["file"]) for v in idx[d]]
        board = max(reversed(boards), key=len)
        grain = [b for b in board if re.match(r"C\.?G$", b[1])]
        board = [b for b in board if b not in grain]
        names = [v["vessel"].upper() for v in pred]
        hit = [b for b in board if any(same(b[0], n) for n in names)]
        miss = [b for b in board if b not in hit]
        extra = [v for v in pred if not any(same(b[0], v["vessel"].upper()) for b in board)]
        tot["hit"] += len(hit); tot["miss"] += len(miss); tot["extra"] += len(extra)
        print(f"{d} {day:%a}  board {len(board)}{' + grain' if grain else ''}  predicted {len(pred)}  hit {len(hit)}")
        for b in miss:
            print(f"    on board, not predicted: {b[0]} @ {b[1]} ({b[2]})")
        for v in extra:
            print(f"    predicted, not on board: {v['vessel']} @ {v['terminal']} {v['type']} "
                  f"ETA {v['eta']:%a %H:%M} ETD {v['etd']:%a %H:%M} [{v['status']}]")
    print(f"\ntotal: {tot['hit']} hit, {tot['miss']} missed, {tot['extra']} extra")


if __name__ == "__main__":
    sys.exit(main())
