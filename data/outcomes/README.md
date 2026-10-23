# Dispatch outcomes (shared)

One CSV per contributor: `data/outcomes/<contributor>.csv`. Separate files mean no merge conflicts.
Pick an alias like `b-day-02`. **Never put your reg number, name, or pay in these files**: spins are public
per reg, so a reg number plus these rows identifies you.

## Columns

| column | meaning |
|---|---|
| `date` | dispatch date, `YYYY-MM-DD` (the day worked, not the day the board posted) |
| `contributor` | your alias, same as the filename |
| `class` | `A`, `B`, or `C` (casual) |
| `shift` | `day` or `night` |
| `hours_before` | your logged hours this period *before* this dispatch (blank if unknown) |
| `spin` | your spin number for that day (from the union spin sheet) |
| `result` | one of `skill3` (strad/top pick), `hustler`, `supervisor`, `crane`, `lash`, `car`, `other`, `no_work` (showed up, sent home), `day_off` |
| `job` | job title as written on your timebook, e.g. `Hustler`, `S/V-SHIP`, `Strad` |
| `terminal` | where you worked, e.g. `PCT`, `Husky P4`, `WUT`, `Matson`, `SSAT` |
| `vessel` | ship name if a ship job |
| `turnout` | `low` / `normal` / `high`: how many people showed at the hall, if you noticed |
| `notes` | anything about the line: who got the last strad (class, hours, spin), what went to A's, empty parking lot, etc. |

The `notes` about *other people's* jobs are the most valuable part: one person's job only shows where they were in
line, but "last strad went to a 0-hr B with spin 174" shows where the line cut off.

`day_off` rows are worth logging too (with whatever you heard about how deep the line went that day).

## cutoffs.csv

Where the line ran out on a day (from anyone's report): `date, shift, kind` (`skill3` = last strad/top pick, `skill` = last skill job incl. trucks), `hours, spin` of the last person to get one, `bound` (`exact`, or `at_least` when someone that deep still got one), `notes`. `score.py` scores the app's saved guesses against it.
