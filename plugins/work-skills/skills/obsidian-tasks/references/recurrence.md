# Computing the next due date

Read this before computing a `due` date for a recurring task. The rules snap
to the **end of a period**; rolling the completion date forward by the
interval instead - `today + 7 days` for a weekly chore - is the failure this
file exists to prevent, and it drifts the schedule a little further every
cycle.

`SKILL.md` Step 4 carries the worked answers for the common cadences. This is
the derivation and the edges.

## Cadence vocabulary

| Cadence | Rule |
|---|---|
| `weekly` | End of next week (Sunday) |
| `monthly` | Last day of next month |
| `every N months` | Last day of the month N months out |
| `annual` | Last day of the same month next year |

`annual` is the spelling in use; treat `annually` and `yearly` as the same
thing if they appear. Anything else is unparseable - see below.

## The algorithms

Compute from **today**, the completion date, never from `last done`:

```
weekly:   this_sunday = today + (6 - today.weekday())   # Mon=0 .. Sun=6
          due = this_sunday + 7 days                    # end of NEXT week

monthly / every N months / annual:
          target = today's month + N months             # monthly N=1, annual N=12
          due = last calendar day of target month
```

## Verified edge cases

| Completed | Cadence | New `due` | Why |
|---|---|---|---|
| Sun 2026-08-23 | `weekly` | 2026-08-30 | A Sunday completion still lands on the *following* Sunday, not the same day |
| Sat 2026-08-22 | `weekly` | 2026-08-30 | Same week, same answer |
| Thu 2026-12-31 | `weekly` | 2027-01-10 | Year rollover |
| 2026-08-31 | `every 6 months` | 2027-02-28 | Target month is shorter than the source month |
| 2027-08-31 | `every 6 months` | 2028-02-29 | Leap year |
| 2026-12-15 | `monthly` | 2027-01-31 | Year rollover |

Because `due` comes from the completion date, a recurring task with an empty
`last done` is not a problem - it simply has no due date until the first time
it is completed. Never backfill a `last done` to make the arithmetic work.

## Cadences these rules do not cover

`seasonally`, or anything that will not parse: set `last done` and
`status: backlog`, leave `due` empty, and say so in the report. Do not invent
an interval.
