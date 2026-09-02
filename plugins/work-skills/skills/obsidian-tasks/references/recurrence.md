# Computing the next due date

Read this before computing a `due` date for a recurring task.

Recurrence is stored in one property, `frequency`, holding an **RFC 5545
`RRULE` value**:

```yaml
frequency: FREQ=WEEKLY;INTERVAL=2;BYDAY=MO
```

`INTERVAL`, `BYDAY`, `BYMONTHDAY`, `UNTIL`, and `COUNT` all live inside that
string. There are no companion fields.

## Let the plugin compute it

When `task-base` is installed it already implements this, and it is what the
user's own **Complete task** button uses. Delegating is the only way an agent
roll-forward and a UI roll-forward land on the same date - see
`plugin.md` for the exact call sequence. Everything below is the fallback for
a vault without the plugin, and the explanation of what the plugin is doing.

## The policy: skip the rest of the period you just did it in

**The anchor is the completion date, not the task's current `due`.** Then take
the schedule's next occurrence, having skipped whatever is left of the period
the completion fell in.

Verified against the plugin, every row:

| `frequency` | Completed | New `due` |
|---|---|---|
| `FREQ=WEEKLY;BYDAY=MO` | Mon 2026-08-24 | 2026-08-31 |
| `FREQ=WEEKLY;BYDAY=SU` | Mon 2026-08-17 | 2026-08-30 |
| `FREQ=WEEKLY;BYDAY=SU` | Wed 2026-09-02 | 2026-09-13 |
| `FREQ=WEEKLY;INTERVAL=2;BYDAY=MO` | Mon 2026-08-24 | 2026-09-07 |
| `FREQ=WEEKLY;BYDAY=MO,TH` | Mon 2026-08-24 | 2026-08-27 |
| `FREQ=MONTHLY;BYMONTHDAY=-1` | 2026-08-22 | 2026-09-30 |
| `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1` | 2026-06-19 | 2026-12-31 |
| `FREQ=YEARLY` | 2026-06-19 | 2027-06-19 |

Row three is the one that catches a naive implementation. Mow the lawn on a
Wednesday under a Sunday rule and the answer is **the Sunday after next**, not
this coming Sunday - you already did it this week, so this week's slot is
spent.

### Three cases, in order

1. **The rule selects no days** (`FREQ=YEARLY`, `FREQ=DAILY`). The day is
   implied by the anchor, so the roll is one whole `FREQ` x `INTERVAL` period
   later. A yearly task done 19 June comes back the following 19 June, not on
   1 January.
2. **More than one occurrence in the period** (`FREQ=WEEKLY;BYDAY=MO,TH`).
   The rest of this period is real work, so take the strict next occurrence:
   done Monday, due Thursday.
3. **One occurrence per period** - every rule in this vault today. Anchor the
   rule at the **start of the period containing the completion** so nothing is
   clipped, then take the first occurrence after that period **ends**.
   `INTERVAL` does the remaining skipping by itself.

Case 3 is the whole reason this is not `rule.after(today)`. Anchoring on the
completion date makes `INTERVAL` step from there: an oil change on 2026-06-19
under `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1` would roll to 2026-06-30 -
eleven days out instead of six months.

Periods are calendar periods: months from the 1st, years from 1 January,
**weeks from Monday**.

## Never compute this by hand

**Do not parse or evaluate an RRULE in shell, and do not do the date
arithmetic yourself.** RFC 5545's `BY*` parts each either *expand* or *limit*
the set depending on the `FREQ` above them, and getting that backwards
produces a rule that looks right and yields the wrong dates. See the trap
below.

The fallback evaluator, which reproduces all eight rows of the table above:

```bash
uv run --with python-dateutil python3 -c '
import sys, re, datetime as d
from dateutil.rrule import rrulestr

RULE, DONE = sys.argv[1].strip(), sys.argv[2]
freq = re.search(r"FREQ=(\w+)", RULE).group(1)
interval = int((re.search(r"INTERVAL=(\d+)", RULE) or [0, 1])[1])
selects_days = bool(re.search(r"BY(DAY|MONTHDAY|MONTH|YEARDAY|SETPOS|WEEKNO)=", RULE))
done = d.date.fromisoformat(DONE)

def month_add(y, m, day):          # m is 0-based; overflows into the next month
    return d.date(y + m // 12, m % 12 + 1, 1) + d.timedelta(days=day - 1)

if not selects_days:                                    # case 1
    if freq == "YEARLY":    nxt = month_add(done.year + interval, done.month - 1, done.day)
    elif freq == "MONTHLY": nxt = month_add(done.year, done.month - 1 + interval, done.day)
    elif freq == "WEEKLY":  nxt = done + d.timedelta(days=7 * interval)
    else:                   nxt = done + d.timedelta(days=interval)
    print(nxt.isoformat()); raise SystemExit

if freq == "YEARLY":
    start, end = d.date(done.year, 1, 1), d.date(done.year, 12, 31)
elif freq == "MONTHLY":
    start = done.replace(day=1); end = month_add(start.year, start.month, 0)
elif freq == "WEEKLY":
    start = done - d.timedelta(days=done.weekday()); end = start + d.timedelta(days=6)
else:
    start = end = done

dt = lambda x: d.datetime(x.year, x.month, x.day)
rule = rrulestr(RULE, dtstart=dt(start))
hit = (rule.after(dt(done), inc=False)                  # case 2
       if len(rule.between(dt(start), dt(end), inc=True)) > 1
       else rule.after(dt(end), inc=False))             # case 3
print(hit.date().isoformat() if hit else "")
' "<frequency>" "<today>"
```

`dateutil` is not a project dependency; `uv run --with` supplies it per
invocation, which is why `SKILL.md` preflight checks for `uv` on this path.

**This is a second implementation of the plugin's `src/recurrence.ts`, and
that is a seam.** If the plugin's policy changes, this file is wrong until it
is changed too. Prefer the plugin whenever it is installed.

## `due` is an output, not an anchor

Nothing reads the task's existing `due` to compute the next one. A `due` that
has drifted off its own rule's grid therefore corrects itself on the next
completion instead of compounding - which is the opposite of the older
anchor-on-`due` model, where an off-grid anchor produced a short cycle
forever.

A recurring task with an empty `due` is not broken; it has simply never been
completed. It sits in the base's `Needs attention` view and the plugin's
`needsAttention` bucket until it is. Never backfill `last done` to make the
arithmetic work.

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

The plugin writes the terse form - `FREQ=YEARLY`, never `FREQ=YEARLY;INTERVAL=1`
- and omits `INTERVAL` at 1. Match it, so hand-written and plugin-written
rules read the same.

Its **Edit repeat rule** command opens a builder that previews the next three
dates before saving. When the user is at the keyboard and the rule is at all
unusual, point them there rather than hand-writing the string.

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

### An unreadable rule is not a one-time task

A `frequency` that will not parse is a third state. Completing such a task as
one-time would write `done: true` and retire a schedule that was meant to keep
running - and under `SKILL.md` Step 3 it would also delete the note. The
plugin refuses to act on one and asks for the rule to be fixed; do the same.

`FREQ=FORTNIGHTLY` is the shape this takes in practice: it parses as a rule
with no usable `FREQ` rather than raising, so a naive check reads it as
recurring and it produces no date, forever.

## An empty `frequency` is one-time

A task recurs if and only if `frequency` has a value. Empty means one-time,
which also means sweepable - see `schema.md`.
