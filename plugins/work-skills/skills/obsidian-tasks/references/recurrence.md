# Writing repeat rules

Read this before writing or editing a `frequency` value. Computing a date from
one is not covered here, because this skill does not compute them - the plugin
does, and `nextDue` will answer without writing anything.

Recurrence lives in one property holding an **RFC 5545 `RRULE` value**:

```yaml
frequency: FREQ=WEEKLY;INTERVAL=2;BYDAY=MO
```

`INTERVAL`, `BYDAY`, `BYMONTHDAY`, `UNTIL` and `COUNT` all live inside that
string. There are no companion fields, and an empty value means one-time.

## Check a rule before storing it

```bash
tb 'ruleState("FREQ=WEEKLY;BYDAY=SU")'                  # none | valid | invalid
tb 'describeRule("FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1")'
tb 'upcoming("FREQ=MONTHLY;BYMONTHDAY=-1","2026-09-03",3)'
```

All three are pure. `describeRule` and `upcoming` together are the honest way
to confirm intent with the user: the rule in English, and the next three dates
it actually produces. **Do both before writing an unfamiliar rule** - every
trap below is one where the rule looks right and yields the wrong dates.

## The grammar

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

The plugin writes the terse form - `FREQ=YEARLY`, never
`FREQ=YEARLY;INTERVAL=1` - and omits `INTERVAL` at 1. `buildRule` produces
exactly that from `{freq, interval, byday, lastDayOfMonth}`, so a rule written
here and one written by the builder read the same.

## Three traps

### `FREQ=YEARLY;BYMONTHDAY=-1` is a monthly rule

The obvious spelling of "annually, on the last day of the month" is wrong.
Under `FREQ=YEARLY`, `BYMONTHDAY` **expands** rather than limits, so it yields
the last day of *every* month:

```
FREQ=YEARLY;BYMONTHDAY=-1   ->  2026-11-30, 2026-12-31, 2027-01-31, 2027-02-28 ...
FREQ=YEARLY                 ->  2026-11-30, 2027-11-30, 2028-11-30 ...
```

Plain `FREQ=YEARLY` recurs on the anniversary, which is what "annual" means
here. Nothing reports an error either way, which is what `upcoming` is for.

### An unreadable rule is a third state, not a one-time task

`ruleState` returns `invalid` for a value that will not parse, and `complete`
refuses rather than choosing. Completing such a task as one-time would write
`done: true` and retire a schedule meant to keep running.

`FREQ=FORTNIGHTLY` is the shape this takes in practice: it parses as a rule
with an unrecognised `FREQ` rather than raising, so a naive check reads it as
recurring and it produces no date, forever. Those tasks surface in
`buckets().invalidRule`.

### An empty rule is empty, not absent

The template writes a bare `frequency:` key on every task note, so a test for a
missing line matches nothing. The API returns `null` for both, which is the
reliable place to test it - and `null` is what clears it. Writing `""` instead
leaves a value that is not null to Bases, and a `frequency != null` filter
starts matching one-time tasks with no error to explain the wrong rows.

## The policy, for explaining it

The skill never applies this by hand - `nextDue` does - but the user may ask
why a date moved where it did. `contract().recurrencePolicy` states it in the
vault's own words; in short:

**Skip the rest of the period you just did it in, then take the schedule's next
occurrence.** The anchor is the completion date, never the task's current
`due`. Mow the lawn on a Wednesday under `FREQ=WEEKLY;BYDAY=SU` and the answer
is the Sunday after next, because this week's slot is already spent.

| `frequency` | Completed | New `due` |
|---|---|---|
| `FREQ=WEEKLY;BYDAY=MO` | Mon 2026-08-24 | 2026-08-31 |
| `FREQ=WEEKLY;BYDAY=SU` | Wed 2026-09-02 | 2026-09-13 |
| `FREQ=WEEKLY;BYDAY=MO,TH` | Mon 2026-08-24 | 2026-08-27 |
| `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1` | 2026-06-19 | 2026-12-31 |
| `FREQ=YEARLY` | 2026-06-19 | 2027-06-19 |

Two consequences worth stating to a user:

- **A `due` that has drifted off its own rule corrects itself** on the next
  completion, because nothing reads the old `due` to compute the new one.
- **A recurring task with no `due` is not broken** - it has never been
  completed. It sits in `buckets().needsAttention` until it is. Never backfill
  `last done` to make arithmetic work.

The table above is a copy of the plugin's own test cases. If it ever disagrees
with `nextDue`, the plugin is right and this file is stale.
