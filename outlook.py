#!/usr/bin/env python3
"""Day-off outlook: which upcoming day shifts look worst to work (best to take off).

Combines, per day:
  - Tacoma vessel calls overlapping the day shift (NWSA schedule, ~3 weeks out)
  - how often each terminal has given you Strad/Top Pick (your private timebook)
  - your spin number (spins.json) and weekend/holiday status

It is a heuristic, not a trained model: the board archive in data/ is too young to learn from yet.

Usage: outlook.py [--start YYYY-MM-DD] [--days N] [--reg REG] [--json]
"""
import argparse
import collections
import csv
import datetime as dt
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spin  # noqa: E402

VESSELS_URL = "https://docs.nwseaportalliance.com/Vessel/Schedule.xlsx"
SPINS_URL = "https://thejoe1990.github.io/Ilwu/spins.json"
GOOD_JOBS = {"STRAD", "TOP PICK"}
SHIFT = (dt.time(8), dt.time(17))          # day shift window a vessel must overlap
TIMEBOOK_SINCE = dt.date(2024, 1, 1)
TIME_OFF = [(dt.date(2026, 4, 1), dt.date(2026, 6, 30))]   # user was off work; not "no work available"

# ILWU/PMA 2026 longshore calendar (NWSA "Longshore Holiday Calendar"). Update each December.
NO_WORK = {"2026-06-19", "2026-09-07", "2026-11-26", "2026-12-25", "2027-01-01"}
OT_DAYS = {"2026-01-19", "2026-02-12", "2026-02-16", "2026-03-31", "2026-05-25", "2026-06-19", "2026-07-06",
           "2026-07-28", "2026-09-07", "2026-11-11", "2026-11-26", "2026-12-24", "2026-12-25", "2026-12-31",
           "2027-01-01"}

# NWSA terminal code -> timebook location bucket
TERMINAL = {"PCT": "PCT", "HUSKY": "HUSKY", "WUT": "WUT", "WST": "MATSON/WST", "TOTE": "TOTE",
            "T7": "T7", "EB1": "EB1", "BLAIR": "BLAIR"}


def timebook_bucket(loc):
    loc = loc.strip().lower()
    for key, bucket in [("husky", "HUSKY"), ("p4", "HUSKY"), ("p3", "HUSKY"), ("wut", "WUT"), ("pct", "PCT"),
                        ("evergreen", "PCT"), ("matson", "MATSON/WST"), ("wst", "MATSON/WST"), ("tote", "TOTE"),
                        ("p7", "T7"), ("t7", "T7"), ("eb", "EB1"), ("blair", "BLAIR")]:
        if key in loc:
            return bucket
    return None


def load_timebook():
    files = sorted((HERE / "private").glob("timebook-*.csv"))
    if not files:
        return []
    rows = []
    for r in csv.DictReader(open(files[-1])):
        m, d, y = map(int, r["DATE"].split("-"))
        day = dt.date(y, m, d)
        if day >= TIMEBOOK_SINCE and not any(a <= day <= b for a, b in TIME_OFF) and r["SHIFT"].strip() == "1":
            rows.append((day, r["JOB"].strip().upper(), timebook_bucket(r["LOCATION"])))
    return rows


def terminal_odds(tb):
    """P(Strad/Top Pick | dispatched to terminal), Laplace-smoothed so thin data stays near 50/50."""
    n, good = collections.Counter(), collections.Counter()
    for _, job, bucket in tb:
        if bucket:
            n[bucket] += 1
            good[bucket] += job in GOOD_JOBS
    return {b: {"shifts": n[b], "good": good[b], "rate": (good[b] + 1) / (n[b] + 2)} for b in set(TERMINAL.values())}


def weekday_history(tb):
    out = {}
    for wd in range(7):
        days = [(job in GOOD_JOBS) for day, job, _ in tb if day.weekday() == wd]
        out[dt.date(2024, 1, 1 + wd).strftime("%a")] = {"shifts": len(days), "good": sum(days)}
    return out


def excel_dt(v):
    if not v:
        return None
    try:
        return dt.datetime(1899, 12, 30) + dt.timedelta(days=float(v))
    except ValueError:
        return dt.datetime.fromisoformat(v)


def load_vessels():
    try:
        data, source = spin.fetch(VESSELS_URL, binary=True), "live NWSA"
    except Exception:
        files = sorted((HERE / "data" / "vessels").glob("*.xlsx"))
        if not files:
            sys.exit("no vessel schedule available (live fetch failed, no archive)")
        data, source = files[-1].read_bytes(), f"archive {files[-1].name}"
    rows = next(iter(spin.xlsx_tabs(data).values()))
    hdr = rows[0]
    col = {h: i for i, h in enumerate(hdr)}
    seen, out = set(), []
    for r in rows[1:]:
        r = r + [""] * (len(hdr) - len(r))
        if r[col["Harbor"]] != "Tacoma":
            continue
        key = (r[col["Terminal"]], r[col["Vessel Name"]], r[col["Voyage"]])
        if key in seen:
            continue
        seen.add(key)
        out.append({"terminal": r[col["Terminal"]], "vessel": r[col["Vessel Name"]], "type": r[col["Vessel Type"]],
                    "eta": excel_dt(r[col["ETA"]]), "etd": excel_dt(r[col["ETD"]]), "status": r[col["Status"]]})
    return out, source


def load_spins(reg):
    try:
        data = json.loads(spin.fetch(SPINS_URL))
    except Exception:
        data = json.load(open(HERE / "spins.json"))
    out = {}
    for w in data["weeks"]:
        if reg in w["regs"]:
            start = dt.date.fromisoformat(w["start"])
            for i, s in enumerate(w["regs"][reg][1:]):
                out[start + dt.timedelta(days=i)] = s
    return out


def outlook(start, days, reg):
    tb = load_timebook()
    odds = terminal_odds(tb)
    vessels, source = load_vessels()
    spins = load_spins(reg)
    result = []
    for i in range(days):
        day = start + dt.timedelta(days=i)
        lo, hi = dt.datetime.combine(day, SHIFT[0]), dt.datetime.combine(day, SHIFT[1])
        working = [v for v in vessels if v["eta"] and v["etd"] and v["eta"] < hi and v["etd"] > lo]
        good_signal = 0.0
        for v in working:
            bucket = TERMINAL.get(v["terminal"].upper())
            v["good_rate"] = round(odds[bucket]["rate"], 2) if bucket else None
            good_signal += odds[bucket]["rate"] if bucket else 0
        iso = day.isoformat()
        result.append({
            "date": iso, "weekday": day.strftime("%a"), "spin": spins.get(day),
            "no_work": iso in NO_WORK,
            "full_hours_day": day.weekday() >= 5 or iso in OT_DAYS,   # weekend/holiday: OT pay, logs all hours
            "vessels": [{k: (v[k].strftime("%a %m-%d %H:%M") if isinstance(v[k], dt.datetime) else v[k])
                         for k in ("terminal", "vessel", "type", "status", "eta", "etd", "good_rate")} for v in working],
            "pct_vessels": sum(v["terminal"].upper() == "PCT" for v in working),
            "husky_vessels": sum(v["terminal"].upper() == "HUSKY" for v in working),
            "good_job_signal": round(good_signal, 2),
        })
    # Day-off rank: lowest good-job signal first; weekends/holidays pay OT so rank them later;
    # a high spin (worse tiebreak, assuming low spin dispatches first) nudges a day toward "take off".
    max_spin = max([d["spin"] for d in result if d["spin"]] or [1])
    for d in result:
        d["day_off_score"] = round(-d["good_job_signal"] - (0.6 if d["full_hours_day"] else 0)
                                   + 0.4 * ((d["spin"] or 0) / max_spin), 2)
    ranked = sorted((d for d in result if not d["no_work"]), key=lambda d: -d["day_off_score"])
    for n, d in enumerate(ranked, 1):
        d["day_off_rank"] = n
    return {"generated": dt.datetime.now().isoformat(timespec="minutes"), "vessel_source": source,
            "timebook_shifts_used": len(tb), "terminal_odds": odds, "weekday_history": weekday_history(tb),
            "days": result}


def main():
    ap = argparse.ArgumentParser()
    today = dt.date.today()
    ap.add_argument("--start", type=dt.date.fromisoformat,
                    default=today + dt.timedelta(days=(5 - today.weekday()) % 7 or 7))   # next Saturday
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--reg", default="230374")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    o = outlook(a.start, a.days, a.reg)
    if a.json:
        print(json.dumps(o, indent=1, default=str))
        return
    print(f"Vessels: {o['vessel_source']} · timebook shifts used: {o['timebook_shifts_used']}")
    print("Terminal odds of Strad/Top Pick (your history): " + ", ".join(
        f"{b} {v['good']}/{v['shifts']}" for b, v in sorted(o["terminal_odds"].items(), key=lambda x: -x[1]["rate"]) if v["shifts"]))
    print("Your day shifts by weekday (good/total): " + ", ".join(
        f"{k} {v['good']}/{v['shifts']}" for k, v in o["weekday_history"].items()))
    print()
    print(f"{'date':<11}{'day':<5}{'spin':>5}  {'PCT':>3} {'HSK':>3} {'all':>3}  {'signal':>6}  {'off#':>4}  notes")
    for d in o["days"]:
        notes = []
        if d["no_work"]:
            notes.append("NO WORK (holiday)")
        elif d["full_hours_day"]:
            notes.append("OT day")
        notes.append(", ".join(f"{v['terminal']}:{v['vessel']}" for v in d["vessels"]))
        print(f"{d['date']:<11}{d['weekday']:<5}{d['spin'] if d['spin'] is not None else '-':>5}  "
              f"{d['pct_vessels']:>3} {d['husky_vessels']:>3} {len(d['vessels']):>3}  {d['good_job_signal']:>6}  "
              f"{d.get('day_off_rank', '-'):>4}  {' · '.join(n for n in notes if n)}")


if __name__ == "__main__":
    main()
