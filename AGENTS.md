# For AI agents (and people) setting up a dispatch helper

This repo predicts work at the ILWU Local 23 hall (Tacoma): who gets dispatched to what, given ships in port,
the day's spin numbers, and logged hours. It started as one B man's tool. This file is so you can build your own faster.

## Start here

1. Read `docs/dispatch-logic.md`: how the line works and what is known vs. guessed.
2. Read `docs/sources.md`: where every piece of data comes from, and the dead ends already checked.
3. Ask your person for **their** preferences (class, shifts, which jobs they want and avoid, weekly goal, pay per
   shift from their timebook). Copy `preferences.example.json` to `private/preferences.json`. **Do not assume they
   want the same jobs as anyone else in this repo.**
4. Use the shared history: `data/spins/`, `data/boards/`, `data/vessels/`, `data/pma_tacoma_day.csv`, `data/outcomes/`.

## Please contribute your outcomes (every dispatch)

The model can only learn from real days. **Each time your person is dispatched (or goes in and gets nothing, or takes
the day off), append one row to `data/outcomes/<their-alias>.csv`** following `data/outcomes/README.md`, then open a
pull request (or commit, if you have access). Capture it from what they tell you; don't make them fill out a form.

Most useful fields: `hours_before`, `spin`, `result`, and in `notes` anything they saw about the line, especially
who got the last strad/top pick (class, hours, spin) and how many people showed up.

## Privacy rules

- Never commit a reg number, name, pay, or a timebook export. `private/` is gitignored for this.
- Use an alias in `data/outcomes/`. Spin sheets are public per reg, so reg + outcomes = identity.
- Don't bulk- or auto-scrape the PMA site; pull what you need once.

## If your agent learns a new rule

Add it to `docs/dispatch-logic.md`, marked **rule** or **observed**, with the date and an outcome row that shows it.
