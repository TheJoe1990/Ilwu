# Where to look (ILWU Local 23 / Port of Tacoma)

All public, no login. The repo already archives the first three automatically (GitHub Actions).

| What | Where | Notes |
|---|---|---|
| **Spin numbers** (every reg, every day) | Google Sheets linked from https://www.ilwulocal23.org/ | `spin.py --all`. Posted weekly (Sat–Fri), tabs A/B/C. The union deletes past weeks, so `data/spins/<week>.json` keeps every week ever posted. |
| **Day board** (next day's jobs) | http://ilwu23.com/?screen=2 | Posts ~2pm the day before. Archived hourly to `data/boards/day/<date>_<hash>.html`; the last file for a date is the final board. `http://ilwu23.com/` (no screen) shows the night board. |
| **Night board** | http://ilwu23.com/?screen=1 | `data/boards/night/` |
| **Vessel schedule** (ETA/ETD by terminal) | https://docs.nwseaportalliance.com/Vessel/Schedule.xlsx | Only source of the future beyond tomorrow. Snapshotted daily to `data/vessels/<date>.xlsx`. ETAs slip, often by a day. |
| **PMA Dispatch Summaries** (Tacoma day shift) | pmanet.org footer, "Dispatch Summaries" | Daily jobs filled by category, unfilled, whether casuals cycled. Parsed to `data/pma_tacoma_day.csv` (Oct 2025 onward) by `pma_parse.py`. Older years exist. Please don't hammer it: pull once, not on a schedule. |
| PMA Coastwide Data / Annual Report | pmanet.org footer | Registered workforce, TEUs, wages by region. Context only. |
| PMA Casual Draw Results | pmanet.org footer | Who is coming up from casual to B. |
| Longshore holiday calendar | NWSA "Longshore Holiday Calendar" PDF | No-work days and OT days. Update yearly. |
| Your own history | Dispatch Companion app, timebook export | Your jobs and pay. **Keep it private** (gitignored `private/`). Summarize into `data/outcomes/` without pay. |

## Dead ends (already checked, save your time)

- **Wayback Machine** has only ~17 snapshots of the day board (2019 to 2025-06). Real content, but too sparse to fit anything. The CDX API rate-limits (429); the availability API works.
- There is no official history of past boards. This repo's archive started 2026-10-10.
