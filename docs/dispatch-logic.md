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
- **rule** Reading the board: job counts are jobs open at the hall, already net of men coming "BACK" (A men holding the job from the previous day; B's don't hold). E.g. "10 BACK 6NEW 15 HUST" = 15 new hustler jobs to dispatch.
- "SV" on the board = supervisor. **rule** Supervisor jobs are dispatched at flex pick, before regular pick. **observed** Sometimes the dispatcher sends no B's at flex pick and hands SV jobs out at regular pick instead (2026-10-13). Treat an SV at regular pick as an anomaly; it isn't modeled.

- **rule** PCT (Evergreen) hires 4 strads per working crane. Matches the board: EVER ELITE 10-20 had 4 new gangs and 16 strads.
- **rule** Ships at WUT and Pier 4 (Husky) raise the chance of top-pick jobs.
- `UT` = utility truck: a yard hustler hired for house/yard work, not a ship. Same truck as a ship hustler, so it counts as a truck (skill) job, not a strad/top pick.
- Likely (agreed, not confirmed): `HS` = house, `SK/HS` = skilled house, `T/TAINER` = transtainer (yard crane). None counted as strad/top pick.
- Timebooks may log a UT shift as plain HUSTLER, so "HUSTLER" mixes ship and yard trucks. `STRAD` = strad, `T/PICK` = top pick, `HT`/`HUST` = hustler.

## Turnout

- **observed** Turnout drops on slow days. With 1 ship in port the parking lot was empty, the line went deep, and a 0-hr B with spin 174 of ~296 still got a strad. **Few ships does not mean worse odds.**
- **observed** Military work (e.g. P-7 military rail) lowers turnout: it can be extremely physical and many people avoid it, so more stay home when it is on the board.
- **observed** Light weekday boards run out early: 2026-10-14 (3 vessels at SSAT/WUT/EB1, no PCT or Husky, little house work) jobs ran out around 12 hrs, so a B at 14 hrs with spin 309 got nothing. One data point; that board was unusually light for a Wednesday.
- **observed** In a busy week nearly every B picks up hours: by Fri 10-23 only 2-3 Bs were at 0 and maybe one at 6, so skill reached 28 hrs. Cutoff hours depend on how much everyone else worked that week, not just on the day's board. The sim's flat show rate badly underestimates this (it guessed ~14 hrs).
- **observed** Busy Saturdays can run through the whole B list into casuals: everyone who shows works.
- **observed** PMA sheet (Aug–Sep 2026): active B's average ~30 paid hrs/week; ~10% of B's barely work.

## Terminals (Tacoma)

- PCT (Evergreen): a ship there runs lots of strads/top picks. The strongest single signal for skill jobs.
- Husky (P3/P4): some skill jobs. WUT: mostly hustlers. Matson/WST, EB1, T7, Blair: few skill jobs reaching B's.
- PCT rail / NIM train days also run strads without a ship.
- **rule** TOTE works Wednesday and Friday nights and basically never day shift, so it's left out of day-shift ship counts (it still adds night work).
- **rule** A ship that doesn't appear on the day board isn't hiring longshore work that day. When the schedule lists a ship that the board doesn't, the forecast overcounted (see `board_backtest.py`).
- **observed** A container ship leaving before ~3pm usually isn't worked on day shift that day: a day gang would get half a shift minus untie time but be paid for a whole one, so it gets finished on the night before. Tying up on arrival takes time too, so a ship due after ~noon gets no day hire.
- **rule** Grain ships (grain elevators, e.g. "C.G" on the board) don't count when counting ships for the day: they hire few longshore and no skill jobs. Wed 10-21 board: 5 ships + 1 grain.

## The model in this repo

- `sim.py`: Monte Carlo over the B line for a Sat–Fri pay period. Rolls ship delays and misses, gives every B their own attendance habit, ranks by hours then spin, and searches every combination of days in for a weekly goal. `params.json` holds the tuned numbers. `--calibrate` rescales job counts to match one person's timebook rates.
- `outlook.py`: quick per-day heuristic table (ships by terminal × spin position).
- **Known gaps:** turnout is a flat show rate (it should drop with ship count); the share of B's qualified for skill jobs is a guess (0.3); other B's hours are unknown beyond your own; board job codes for strad/top pick/hustler aren't decoded yet; weekend send-home risk isn't modeled.
- `params.json` and `sim.py` still contain the original author's preferences (pay goal, terminal preference, avoiding Matson, the PCT lean). Copy `preferences.example.json`, change it, and adapt before trusting the output for yourself.

- **Guess basis (2026-10-23):** guess.py labels each day "Before board" (vessel schedule only) or "After board" (the posted day board's ship list replaces the schedule for that day and for earlier days in the period). Job counts still come from the model; board job codes aren't used yet.
