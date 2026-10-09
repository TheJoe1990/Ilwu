#!/usr/bin/env python3
"""Read ILWU Local 23 dispatch spin numbers for one registration number.

Scrapes https://www.ilwulocal23.org/ for date-labeled Google Sheets links,
keeps the ones laid out as spin sheets (tabs A/B/C, header row starting
"Reg #"), and reads each reg's spin for each day. Stdlib only, no login.

Usage: spin.py REG        print one reg's spins
       spin.py --all      compact JSON of every reg (for the web app)
"""
import datetime as dt
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

HOME = "https://www.ilwulocal23.org/"
DAYS = ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
UA = {"User-Agent": "Mozilla/5.0 (spin-calendar)"}


def fetch(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def dated_sheet_links(html):
    """Yield (week_start_date, sheet_id) for every link whose text is a MM-DD-YYYY date."""
    seen = set()
    for href, inner in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        text = re.sub(r"<[^>]+>", "", inner).strip()
        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", text)
        sid = re.search(r"docs\.google\.com/spreadsheets/d/([\w-]+)", href)
        if m and sid and sid.group(1) not in seen:
            seen.add(sid.group(1))
            mo, d, y = map(int, m.groups())
            yield dt.date(y, mo, d), sid.group(1)


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def col_index(ref):
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def workbook_tabs(sheet_id):
    """Return {tab_name: [[cell_text, ...], ...]} from the sheet's .xlsx export (stdlib only)."""
    z = zipfile.ZipFile(io.BytesIO(fetch(
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx", binary=True)))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    tabs = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", NS):
        target = rels[sh.get(f"{{{NS['r']}}}id")].lstrip("/")
        path = target if target.startswith("xl/") else "xl/" + target
        rows = []
        for row in ET.fromstring(z.read(path)).iter(f"{{{NS['m']}}}row"):
            cells = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if c.get("t") == "s" and v is not None:
                    val = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    val = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                else:
                    val = v.text if v is not None else ""
                cells[col_index(c.get("r"))] = val.strip()
            rows.append([cells.get(i, "") for i in range(max(cells, default=-1) + 1)])
        tabs[sh.get("name")] = rows
    return tabs


def parse_spin_sheet(sheet_id):
    """Return {reg: (class, [sat..fri spins as int or None])}; raise ValueError if not a spin sheet."""
    regs = {}
    is_spin_sheet = False
    for tab, rows in workbook_tabs(sheet_id).items():
        hdr = next((r for r in rows if r and r[0].lower().startswith("reg")), None)
        if not hdr or "Saturday" not in hdr:
            continue
        is_spin_sheet = True
        cols = {h: i for i, h in enumerate(hdr)}
        for r in rows:
            reg = r[0].split(".")[0] if r else ""
            if not reg.isdigit():
                continue
            spins = []
            for d in DAYS:
                v = r[cols[d]].split(".")[0] if d in cols and cols[d] < len(r) else ""
                spins.append(int(v) if v.isdigit() else None)
            regs[reg] = ((r[cols["Class"]] if "Class" in cols and cols["Class"] < len(r) else "") or tab, spins)
    if not is_spin_sheet:
        raise ValueError("not a spin sheet")
    return regs


def all_weeks():
    """Yield (week_start_date, {reg: (class, spins)}) for every spin sheet linked from the homepage."""
    for week_start, sid in sorted(dated_sheet_links(fetch(HOME))):
        try:
            yield week_start, parse_spin_sheet(sid)
        except ValueError:
            continue


def dump_all():
    """Compact JSON for the web app: {"generated", "weeks": [{"start", "regs": {reg: [class, sat..fri]}}]}."""
    weeks = [{"start": ws.isoformat(), "regs": {reg: [cls, *spins] for reg, (cls, spins) in regs.items()}}
             for ws, regs in all_weeks()]
    if not weeks:
        sys.exit("no spin sheets found; homepage layout may have changed")
    return {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "weeks": weeks}


def main():
    if "--all" in sys.argv:
        print(json.dumps(dump_all(), separators=(",", ":")))
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or not args[0].isdigit():
        sys.exit(__doc__)
    reg = args[0]
    for week_start, regs in all_weeks():
        if reg not in regs:
            print(f"Week of {week_start}: reg {reg} not listed")
            continue
        cls, spins = regs[reg]
        print(f"Week of {week_start} (class {cls}):")
        for i, (day, spin) in enumerate(zip(DAYS, spins)):
            if spin is not None:
                print(f"  {week_start + dt.timedelta(days=i)} {day[:3]}  spin {spin}")


if __name__ == "__main__":
    main()
