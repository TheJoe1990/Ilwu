# How dispatch works (and what the model assumes)

Facts below came from a working B man and were checked against real days in `data/outcomes/`.
Each is marked **rule** (how the hall works) or **observed** (seen happen, may not always hold).
Nothing here assumes which job *you* want. Your preferences go in your own agent's config.

## The line

- **rule** A's are dispatched before B's, B's before casuals.
- **rule** Within a class: lowest logged hours goes first; the day's spin number breaks ties.
- **rule** Hours reset Saturday 00:00 (weekend) and Monday 00:00 (weekday). Weekend hours don't count against weekdays.
- **rule** Logged hours on a weekday day shift = hours worked − 2. Hustler: 8 worked, logs 6. Strad/top pick or supervisor: 8 + 2 OT, logs 8. Weekends and longshore holidays log full hours and pay OT.
- **rule** Once you go in, if there's work for you, you take it. So "which days to go in" is the only real choice.
- So a day off lowers your hours relative to everyone who worked, which moves you up the line on later days. Skipping a slow day can buy a better pick on a busy day.

## Who takes what

- **rule** A's can hold a ship job day to day. **rule** Monday is weekly yard hiring: A's take the house/yard strad and top-pick jobs for the week, so few skill jobs reach B's on a Monday.
- **observed** B's fill all skill jobs before unskilled ones (car ships, lashing). Only A's choose car shifts.
- **observed** Trucks (hustlers) at a terminal: B preferences split roughly evenly across WUT / Husky / Matson.
- **observed** Lashers on the board = a ship starting or finishing. Lashing and car ships soak up labor ahead of you, so lots of them improves your odds for other jobs.
- **rule** Reading the board: job counts are jobs open at the hall, already net of men coming "BACK" (holding from the previous day). E.g. "10 BACK 6NEW 15 HUST" = 15 new hustler jobs to dispatch.
- "SV" on the board = supervisor. **rule** Supervisor jobs are dispatched at flex pick, before regular pick. **observed** Sometimes the dispatcher sends no B's at flex pick and hands SV jobs out at regular pick instead (2026-10-13). Treat an SV at regular pick as an anomaly; it isn't modeled.

## Turnout

- **observed** Turnout drops on slow days. With 1 ship in port the parking lot was empty, the line went deep, and a 0-hr B with spin 174 of ~296 still got a strad. **Few ships does not mean worse odds.**
- **observed** Military work (e.g. P-7 military rail) lowers turnout: it can be extremely physical and many people avoid it, so more stay home when it is on the board.
- **observed** Light weekday boards run out early: 2026-10-14 (3 vessels at SSAT/WUT/EB1, no PCT or Husky, little house work) jobs ran out around 12 hrs, so a B at 14 hrs with spin 309 got nothing. One data point; that board was unusually light for a Wednesday.
- **observed** Busy Saturdays can run through the whole B list into casuals: everyone who shows works.
- **observed** PMA sheet (Aug–Sep 2026): active B's average ~30 paid hrs/week; ~10% of B's barely work.

## Terminals (Tacoma)

- PCT (Evergreen): a ship there runs lots of strads/top picks. The strongest single signal for skill jobs.
- Husky (P3/P4): some skill jobs. WUT: mostly hustlers. Matson/WST, EB1, T7, Blair: few skill jobs reaching B's.
- PCT rail / NIM train days also run strads without a ship.
- **rule** Grain ships (grain elevators, e.g. "C.G" on the board) don't count when counting ships for the day: they hire few longshore and no skill jobs. Wed 10-21 board: 5 ships + 1 grain.

## The model in this repo

- `sim.py`: Monte Carlo over the B line for a Sat–Fri pay period. Rolls ship delays and misses, gives every B their own attendance habit, ranks by hours then spin, and searches every combination of days in for a weekly goal. `params.json` holds the tuned numbers. `--calibrate` rescales job counts to match one person's timebook rates.
- `outlook.py`: quick per-day heuristic table (ships by terminal × spin position).
- **Known gaps:** turnout is a flat show rate (it should drop with ship count); the share of B's qualified for skill jobs is a guess (0.3); other B's hours are unknown beyond your own; board job codes for strad/top pick/hustler aren't decoded yet; weekend send-home risk isn't modeled.
- `params.json` and `sim.py` still contain the original author's preferences (pay goal, terminal preference, avoiding Matson, the PCT lean). Copy `preferences.example.json`, change it, and adapt before trusting the output for yourself.
