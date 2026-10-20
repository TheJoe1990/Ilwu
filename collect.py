#!/usr/bin/env python3
"""Archive public port/dispatch data so there is history to learn from.

Saves, under data/:
  boards/day/<board-date>_<hash>.html    each distinct version of the ILWU 23 day board (dated by fetch time if the header lags, see day_board_date)
  boards/night/<board-date>_<hash>.html  same for the night board
  boards/index.json                      {kind: {board-date: [{file, saved}]}}, oldest first, for the app's board viewer
  vessels/<YYYY-MM-DD>.xlsx              latest NWSA vessel schedule snapshot for that day (Pacific)

Only writes a file when content changed, so frequent runs are cheap. Stdlib only.
"""
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import sys
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent / "data"
BOARDS = {"day": "http://ilwu23.com/?screen=2", "night": "http://ilwu23.com/?screen=1"}
VESSELS = "https://docs.nwseaportalliance.com/Vessel/Schedule.xlsx"
UA = {"User-Agent": "Mozilla/5.0 (ilwu-archive)"}
PT = ZoneInfo("America/Los_Angeles")
DAY_CUTOFF_HOUR = 8   # Pacific; day boards fetched from this hour on are for the next day


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def save_board(kind, url):
    raw = fetch(url)
    text = raw.decode("utf-8", "replace")
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2})", text)
    if not m or "Server Error" in text:
        print(f"{kind}: no board date found, skipped", file=sys.stderr)
        return False
    mo, d, y = map(int, m.groups())
    header_date = dt.date(2000 + y, mo, d).isoformat()
    board_date = header_date
    if kind == "day":
        # The hall sometimes leaves yesterday's date in the header when posting the next board
        # (e.g. Tue 10-20's board was headed 10/19/26), so never file a day board earlier than its fetch time implies.
        # A header ahead of that is kept: the next day's board can go up before the cutoff.
        board_date = max(header_date, day_board_date(dt.datetime.now(PT)).isoformat())
        if board_date != header_date:
            print(f"day: header says {header_date}, filed as {board_date}", file=sys.stderr)
    # Hash the visible text only, so markup/whitespace churn doesn't create new versions.
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", "", text))).strip()
    h = hashlib.sha1(visible.encode()).hexdigest()[:8]
    out = ROOT / "boards" / kind / f"{board_date}_{h}.html"
    if out.exists():
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    index_board(kind, board_date, out.name, header_date)
    print(f"{kind}: saved {out.name}")
    return True


def day_board_date(fetched):
    """Day dispatch is done by ~8am Pacific; after that the board shows the next day's work."""
    return fetched.date() + dt.timedelta(days=0 if fetched.hour < DAY_CUTOFF_HOUR else 1)


def index_board(kind, board_date, name, header_date=None):
    """Record a saved board version (with when it was saved) so the app can list boards without a directory listing."""
    path = ROOT / "boards" / "index.json"
    idx = json.loads(path.read_text()) if path.exists() else {}
    versions = idx.setdefault(kind, {}).setdefault(board_date, [])
    if not any(v["file"] == name for v in versions):
        v = {"file": name, "saved": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
        if header_date and header_date != board_date:
            v["header"] = header_date
        versions.append(v)
    path.write_text(json.dumps(idx, indent=1, sort_keys=True))


def save_vessels():
    raw = fetch(VESSELS)
    if not raw.startswith(b"PK"):
        print("vessels: not an xlsx, skipped", file=sys.stderr)
        return False
    out = ROOT / "vessels" / f"{dt.datetime.now(PT).date().isoformat()}.xlsx"
    # xlsx bytes change on every export (timestamps), so compare by a stable digest of the sheet XML.
    def digest(b):
        z = zipfile.ZipFile(io.BytesIO(b))
        parts = [n for n in sorted(z.namelist()) if n.startswith("xl/worksheets/") or n == "xl/sharedStrings.xml"]
        return hashlib.sha1(b"".join(z.read(n) for n in parts)).hexdigest()
    if out.exists() and digest(out.read_bytes()) == digest(raw):
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    print(f"vessels: saved {out.name}")
    return True


def main():
    failures = 0
    for kind, url in BOARDS.items():
        try:
            save_board(kind, url)
        except Exception as e:
            failures += 1
            print(f"{kind}: {e}", file=sys.stderr)
    try:
        save_vessels()
    except Exception as e:
        failures += 1
        print(f"vessels: {e}", file=sys.stderr)
    # Fail the run (GitHub emails) only if every source failed.
    sys.exit(1 if failures == len(BOARDS) + 1 else 0)


if __name__ == "__main__":
    main()
