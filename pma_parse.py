#!/usr/bin/env python3
"""Parse PMA Tacoma day-shift Dispatch Summary PDFs (private/pma/*.pdf) into data/pma_tacoma_day.csv.

One row per day: registered-hall and casual-hall longshore jobs filled, unfilled counts, whether the casual
hall cycled, and New/Back totals by job category (vessel + rail only; yard/house jobs are in hall_ls but not
broken out). Needs pdftotext (poppler)."""
import csv, datetime as dt, pathlib, re, subprocess

HERE = pathlib.Path(__file__).resolve().parent
SRC, OUT = HERE / "private" / "pma", HERE / "data" / "pma_tacoma_day.csv"
CATS = {"Crane": "crane", "Other Skill": "skill", "Semi-Tractor": "semi", "Total Longshore": "ls", "Unskilled": "unsk"}


def num(pat, text, default=""):
    m = re.search(pat, text)
    return m.group(1) if m else default


def parse(path):
    t = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout
    t = re.sub(r"[ \t]+", " ", t)
    d = dt.date.fromisoformat(path.name[:10])
    lab = t[t.find("DISPATCH ACTUALS"):]
    casual = lab[lab.find("Casual Hall Dispatch"):]
    row = {
        "date": d.isoformat(), "dow": d.strftime("%a"),
        "hall_ls": num(r"No\. of L/S Jobs Filled (\d+)", lab),
        "hall_done": num(r"L/S Jobs Dispatch Completed (\d\d:\d\d)", lab),
        "casual_ls": num(r"No\. of L/S Jobs Filled (\d+)", casual, "0"),
        "casual_done": num(r"L/S Dispatch Completed (\d\d:\d\d)", casual),
        "casual_cycled": num(r"Casual Hall Cycled ([YN])", lab),
        "unfilled_ls": num(r"No\. of Unfilled L/S Jobs (\d+)", lab, "0"),
        "unfilled_skill": num(r"No\. of Unfilled Skill Jobs (\d+)", lab, "0"),
        "unfilled_gangs": num(r"Unfilled Gangs (\d+)", lab, "0"),
        "container_gangs": num(r"Total Gangs (\d+ \d+ \d+ \d+)", t).split(" ")[-1] if num(r"Total Gangs (\d+ \d+ \d+ \d+)", t) else "",
        "comments": num(r"COMMENTS (.*)", lab).strip(),
    }
    # Category totals: the "Total N N N N N" line following each category name (New Back Steady Cut Total).
    for name, key in CATS.items():
        m = re.search(re.escape(name) + r"(?:.|\n)*?Total (\d+) (\d+) (\d+) (\d+) (\d+)", lab)
        for i, col in enumerate(("new", "back", "steady", "cut", "total")):
            row[f"{key}_{col}"] = m.group(i + 1) if m else "0"
    return row


def main():
    rows = [parse(p) for p in sorted(SRC.glob("*_1st.pdf"))]
    if not rows:
        return print("no PDFs in", SRC)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} days -> {OUT}")


if __name__ == "__main__":
    main()
