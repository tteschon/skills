# Computing the next due date

Read this before computing a `due` date for a recurring task.

Recurrence is stored in one property, `frequency`, holding an **RFC 5545
`RRULE` value**:

```yaml
frequency: FREQ=WEEKLY;INTERVAL=2;BYDAY=MO
```

`INTERVAL`, `BYDAY`, `BYMONTHDAY`, `UNTIL`, and `COUNT` all live inside that
string. There are no companion fields.

## Never compute this by hand

**Do not parse or evaluate an RRULE in shell, and do not reimplement the date
arithmetic.** RFC 5545's `BY*` parts each either *expand* or *limit* the set
depending on the `FREQ` they sit under, and getting that backwards produces a
rule that looks right and yields the wrong dates. See the trap below.

Call a real evaluator:

```bash
uv run --with python-dateutil python3 -c '
import sys, datetime as d
from dateutil.rrule import rrulestr
rule, due, today = sys.argv[1], sys.argv[2], sys.argv[3]
r = rrulestr(rule, dtstart=d.datetime.fromisoformat(due))
print(r.after(d.datetime.fromisoformat(today)).date().isoformat())
' "<frequency>" "<due>" "<today>"
```

This is why `SKILL.md` preflight requires Python in addition to the obsidian
CLI. `dateutil` is not a project dependency; `uv run --with` supplies it per
invocation.

## The two rules that define the model

**1. The anchor is `due`.** RRULE has no meaning without a `DTSTART`; this
system uses the task's current `due` date as that anchor.

**2. Roll-forward is the next occurrence strictly after today.**
`rule.after(today)` — today being the completion date.

Rule 2 is what makes the model tolerant of late completions *without* a second
field. The grid is fixed by the anchor, so a late completion lands on the next
scheduled slot rather than shifting the whole series. Verified against
`FREQ=WEEKLY;INTERVAL=2;BYDAY=MO` anchored 2026-08-24:

| Completed | New `due` | |
|---|---|---|
| 2026-08-24 | 2026-09-07 | on time |
| 2026-09-02 | 2026-09-07 | 9 days late; parity held, series not shifted |
| 2026-09-08 | 2026-09-21 | a whole cycle missed - it skips rather than sliding |

## The anchor must sit on its own grid

`due` has to be a member of the series its own `frequency` generates. If it is
not, the first roll-forward returns a short cycle - the next grid point, which
may be days away instead of months.

Assert it after every write:

```python
rrulestr(frequency, dtstart=due)[0].date() == due     # must be True
```

Real examples from the migration, before they were corrected: an oil change
with `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1` anchored at 2026-12-19 rolled
forward to 2026-12-31 - twelve days, not six months. A `FREQ=WEEKLY;BYDAY=SU`
task anchored on a Friday rolled forward two days.

When a task's `due` is off-grid, snap it to `rule[0]` before anything else.

## Writing a rule

| Intent | `frequency` |
|---|---|
| Every Monday | `FREQ=WEEKLY;BYDAY=MO` |
| Every other Monday | `FREQ=WEEKLY;INTERVAL=2;BYDAY=MO` |
| End of each week | `FREQ=WEEKLY;BYDAY=SU` |
| Last day of each month | `FREQ=MONTHLY;BYMONTHDAY=-1` |
| Last day, every 6 months | `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1` |
| Annually, on the anniversary | `FREQ=YEARLY` |
| First Saturday of the month | `FREQ=MONTHLY;BYDAY=1SA` |
| Every Monday through October | `FREQ=WEEKLY;BYDAY=MO;UNTIL=20261031T000000` |

`BYDAY` takes a position prefix: `1SA` is the first Saturday, `-1FR` the last
Friday. `BYMONTHDAY=-1` is the last day of the month.

### The `FREQ=YEARLY;BYMONTHDAY=-1` trap

The obvious spelling of "annually, on the last day of the month" is wrong.
Under `FREQ=YEARLY`, `BYMONTHDAY` **expands**, so that rule yields the last day
of *every* month - a monthly rule wearing a yearly label:

```
FREQ=YEARLY;BYMONTHDAY=-1   ->  2026-11-30, 2026-12-31, 2027-01-31, 2027-02-28 ...
FREQ=YEARLY                 ->  2026-11-30, 2027-11-30, 2028-11-30 ...
```

Plain `FREQ=YEARLY` recurs on the anchor's anniversary, which is what "annual"
means here. This is the concrete reason for the no-hand-parsing rule above:
the wrong spelling is the intuitive one, and nothing reports an error.

## An empty `frequency` is one-time

A task recurs if and only if `frequency` has a value. Empty means one-time,
which also means sweepable - see `schema.md`. A recurring task with an empty
`due` is not a problem; it simply has no due date until first completed. Never
backfill `last done` to make arithmetic work.
