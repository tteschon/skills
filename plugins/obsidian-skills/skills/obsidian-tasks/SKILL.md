---
name: obsidian-tasks
description: Create and manage note-per-task records in an Obsidian vault - one note per task with a done checkbox, due, priority, category, and an RRULE frequency, collected by a Bases file. Use when adding a task, marking one done, rolling a recurring chore forward, asking what to work on next, or grooming the base for unscheduled and finished tasks. Do NOT use for checkbox tasks inline in note bodies, or for general vault reading and editing - that is obsidian-cli.
compatibility: Requires the obsidian CLI, uv for RRULE evaluation, and a vault whose task notes carry a type property of task, collected by a Bases file that does not filter out completed tasks
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks, complete them,
roll recurring chores forward, answer what to work on next, and groom the base.

**A note is a task because it has `type: task`, not because of where it lives.**
The base collects them wherever they sit.

`obsidian-cli` covers the CLI itself - preflight, vault targeting, `path=` vs
`file=`, and why exit codes cannot be trusted. Run its check first; do not
re-derive it here.

## Workflow

1. **Resolve the base** with `obsidian bases`. Use the path it prints, exactly.
2. **Survey** with one `base:query` before any write. The returned keys are the
   schema.
3. **Branch on `frequency`** before completing anything. Set means recurring,
   empty means one-time, and the two paths are not interchangeable.
4. **Write** through `property:set`, one property per call.
5. **Validate**: re-run the `base:query` and read the output text. Common
   failures: the command exited 0 despite printing `Error: `, `done` was
   written as the string `"false"` because `type=checkbox` was omitted, or the
   note never had `type: task` and so never entered the base.
6. **Report** the note path, the fields changed, and their new values, quoting
   the read-back.

## Resolving the base

```bash
obsidian bases                       # find the task base
obsidian read path="<base path>"     # learn its filter
```

| Found | Do |
|---|---|
| One task base | Use the path `bases` printed, exactly |
| Several | Pick by name, or ask; do not guess |
| None | Confirm with the user, then build the one in `references/base.md` |

The filter names the property marking a task and any folder the base restricts
to. Take paths from the app, never from `ls` - they are case-sensitive to
the CLI and case-insensitive on the macOS disk.

Rolling a recurring task forward evaluates an RFC 5545 `RRULE` and needs Python
as well as the CLI; `uv run --with python-dateutil` supplies it per invocation.
Every other operation is shell only.

## Surveying

```bash
obsidian base:query path="<base path>" format=json
```

One object per task, keyed by the base view's columns. **The keys are the
schema** - a new task should carry the same ones. Never assume a value from
memory or from the user's phrasing.

Formula columns come back with the properties. When the base defines
`days_until_due` and `overdue`, those values are the answer - the vault
computed them, so do not recompute from `due`.

**The base includes done tasks.** Its filter does not exclude them, so this is
the full inventory rather than a list of open work. Drop `done: true` rows
before ranking, and recognise them as the sweep queue.

## Creating a task

`base:create` satisfies the base's filters on its own - it stamps the filter
property into the new note and writes it into the folder the filter names. The
note comes back scaffolded with every column in the view's `order:` list as an
empty key, and `type: task` filled in.

```bash
obsidian base:create path="<base path>" name="<task name>"
obsidian property:set name=done value=false type=checkbox path="<new path>"
obsidian property:set name=priority value=medium path="<new path>"
obsidian property:set name=category value=yard path="<new path>"
obsidian property:set name=created value="[[<today>]]" path="<new path>"
```

Ask for `category` and `priority` when the user did not say. **Leave `due` and
`frequency` empty rather than inventing them** - a task with no due date is a
real state the base has a view for, and an invented date is indistinguishable
from one the user chose.

`created` is a daily-note backlink - a quoted wikilink, never a bare date.

If `base:create` fails, fall back to `create name="<name>" path="<folder>"`
then `property:set name=type value=task`. The note is only a task once it has
that property.

Read `references/schema.md` before creating or migrating: it holds the field
contract and the values already in use, so a new task reuses a `category`
instead of coining one.

## Completing a one-time task

**Check `frequency` first.** It separates the two kinds of task, and the branch
is not recoverable by reading the note afterwards. A task *with* a rule goes to
the next section and never gets `done: true`.

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian property:set name=done value=true type=checkbox path="<path>"
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

**Confirm before the `delete`, naming the note.** Write `done: true` first even
though the note is about to go: the trashed copy is recoverable, and it should
read as finished work rather than an abandoned draft.

Anything the user may want later - what was done, a measurement, a receipt -
belongs in a note that outlives the task. Offer to move it before deleting.

This removes the one task the user finishes in front of you. Clearing
accumulated finished tasks is the sweep, further down.

## Completing a recurring task

A recurring task is never left `done`; that is what makes it recur. `frequency`
holds an RFC 5545 `RRULE`, and the new `due` is the next occurrence **strictly
after today**, anchored on the task's current `due`.

```bash
uv run --with python-dateutil python3 -c '
import sys, datetime as d
from dateutil.rrule import rrulestr
r = rrulestr(sys.argv[1], dtstart=d.datetime.fromisoformat(sys.argv[2]))
print(r.after(d.datetime.fromisoformat(sys.argv[3])).date().isoformat())
' "<frequency>" "<current due>" "<today>"
```

**IMPORTANT:** Never compute this by hand. RRULE's `BY*` parts expand or limit
depending on the `FREQ` above them, so the intuitive spelling of "annually on
the last day of the month" silently yields a *monthly* series:

```
# WRONG - BYMONTHDAY expands under YEARLY, giving 12 occurrences a year
FREQ=YEARLY;BYMONTHDAY=-1

# CORRECT - pin the month, and BYMONTHDAY limits instead
FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=-1
```

Anchoring on `due` rather than today is what makes a late completion land on
the next scheduled slot instead of shifting every future cycle. Confirm the new
`due` is itself on the rule's grid - an off-grid anchor rolls forward by days
instead of months.

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian property:set name=due value="<computed>" path="<path>"
obsidian property:set name=done value=false type=checkbox path="<path>"
obsidian append path="<path>" content='\n- <today> - <detail>\n'
```

`last done` and `due` are real dates, always. Non-date detail - mileage, a part
number, what was done - goes on the body log line under a `## Service log`
heading, *never* into those two fields. The body log also keeps the history
that `last done` overwrites.

Read `references/recurrence.md` before writing or editing any rule.

## What to work on

Drop `done: true` rows before ranking. They sit in the base and they are
not work; scheduling one is the way to get this wrong.

The base's Table view sorts by `done` then `due`. That front-loads open work
and the soonest dates, but it is not a priority ranking. Any ranking is this
skill's, so state the rule rather than implying the vault supplied it.

Default ranking, highest first:

1. Overdue - `overdue` is true, or `due` is before today
2. `priority: high`, then `medium`, then `low`
3. Ties broken by `due`, empty `due` last

Prefer the base's own `overdue` and `days_until_due`, and query `view="Today"`
or `view="This week"` rather than filtering every row by hand.

Say how many tasks were considered, counting open ones only. Recurring tasks
with no `due` are waiting on their first completion - list them separately
rather than as overdue.

## Grooming the base

A periodic review of the whole base rather than a change to one task. **Report
everything; change only what the user accepts**, and leave the rest alone
rather than tidying by default. One `base:query` feeds both checks.

### Unscheduled one-time tasks

`done` is not true, `due` is empty, and `frequency` is empty.

These are invisible to the schedule, not merely unprioritised - the `Today` and
`This week` views both filter on `due != null`, so no amount of waiting will
surface them. Report them and offer three outcomes. Never invent a due date:

| The user says | Do |
|---|---|
| A date, or a month | `property:set name=due value="<date>"` |
| A someday item | Leave it, and say plainly it stays off every dated view |
| No longer wanted | Complete and delete it, as above |

A *recurring* task with an empty `due` is not a defect - it is waiting on its
first completion, which is what the `Needs attention` view collects. List those
separately and say why.

### Sweeping finished tasks

| Row | Meaning | Do |
|---|---|---|
| `done: true`, `frequency` empty | A finished one-time task | Sweep after confirmation |
| `done: true`, `frequency` set | A recurring task that has silently stopped recurring | **Never delete.** Roll it forward instead |

**IMPORTANT:** `frequency` is what keeps a task out of the sweep. A done row
carrying a rule is a recurring chore that was marked finished and never rolled
forward; deleting it destroys the schedule instead of repairing it. It is also
the finding worth naming out loud, because nothing else in the vault will flag
it - the row sits there looking finished, its rule intact, and it will simply
never come due again.

**List every candidate by name and take one confirmation for the batch**, then
delete one path at a time, using the `path` from `base:query` verbatim:

```bash
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

When `base:views` lists a `Sweep` view, `base:query ... view="Sweep"` returns
exactly the deletable rows. A base without one is not a problem; filter the
survey on the two conditions instead.

Most one-time tasks are frontmatter and nothing else. When a candidate has a
body, say so while listing it - a service log or a receipt should outlive the
task and be moved somewhere that survives.

## Validating a write

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>`, `Set <property>: <value>`, or `Moved to
   trash: <path>`. A line starting with `Error: ` is a failure - including
   `Error: File "..." not found.`, which is what a delete against a mistyped
   path prints in place of doing anything.
2. Re-run the survey query. Absence has one innocent cause and one failure:

| Absent from `base:query` | Meaning |
|---|---|
| You deleted it, or swept it | Correct - `obsidian read` confirms, printing `Error: File "..." not found.` |
| Anything else | The note has no `type: task` - the classic failure |

The second is invisible from the note alone, which is why the read-back goes
against the base and not the file.

After a sweep, confirm the row count dropped by exactly the number swept - no
more, and never for a task nobody agreed to remove.

Report grooming as a review, not a changelog. A check that found nothing still
earns a line; silence reads as an unrun check.

## Troubleshooting

**Every filter testing `done` stopped working.** `done` is the one property
that must carry `type=checkbox`. Without it the CLI writes the *string*
`"false"`:

```bash
# WRONG - writes the string "false"
obsidian property:set name=done value=false path="<path>"

# CORRECT - writes a boolean
obsidian property:set name=done value=false type=checkbox path="<path>"
```

This is the sole exception to the ban on `type=`. `done` is task-exclusive, so
registering it vault-wide is the intent rather than a side effect. Never
generalise it to any other property.

**Every task read back as done.** `base:query` returns `done` as a string, and
`"false"` is truthy - an open task reads as `'false'`, a completed one as
`'true'`, both non-empty:

```python
# WRONG - true for every task; counted 29 of 29 as done when exactly one was
if row['done']:

# CORRECT
if row['done'] in (True, 'true'):
```

**Every task went down the one-time path.** `frequency` is empty on a one-time
task, not missing - the template writes the bare key on every note, so a test
for an absent line matches nothing. Test the value from `base:query`, which
returns `null` for an empty key and a genuinely absent one alike.

**A `frequency != null` filter started matching one-time tasks.** An empty
string is not `null` to Bases:

```bash
# WRONG - writes frequency: "", which is not null
obsidian property:set name=frequency value="" path="<path>"

# CORRECT - leave the template's bare key alone
```

**`property:set` broke sorting for the whole vault.** `type=` is vault-wide;
see `obsidian-cli`. It is doubly confusing here because `type` is also the
property marking a task - `name=type` is correct, `type=text` is the
destructive one.

**A new property is invisible to `base:query`.** Results are keyed by the
view's columns, so a property written to every note reads back as absent until
the `.base` file names it. Verify with `obsidian read`, or update the base
first.

**Text in `due` broke computation silently.** A formula over a non-date `due`
errors, but a comparison like `due < today()` returns *`false`* - so the task
is never flagged overdue and date-window views omit it with no error at all.

**`obsidian tasks` returned something unrelated.** It is a different system: it
lists checkbox tasks written inline in note bodies, and its flags happen to be
named `done` and `todo` despite the collision. This skill never uses it.

**Never read task state from a Kanban board or a hand-maintained table.** They
do not write back to frontmatter and drift by a known and growing margin.
`references/schema.md` measures it.

**`obsidian delete` trashes by default; never pass `permanent`.** The note
stays recoverable from the vault trash, which is what makes a batch sweep safe
to confirm.

## Complete example

Rolling a recurring chore forward after the user says "I mowed the lawn":

```bash
obsidian bases                                       # -> tasks/task base.base
obsidian base:query path="tasks/task base.base" format=json
# -> {"path":"tasks/Mow Lawn.md","done":"false","due":"2026-09-06",
#     "frequency":"FREQ=WEEKLY;BYDAY=SU","last done":"2026-08-30", ...}

uv run --with python-dateutil python3 -c '
import sys, datetime as d
from dateutil.rrule import rrulestr
r = rrulestr(sys.argv[1], dtstart=d.datetime.fromisoformat(sys.argv[2]))
print(r.after(d.datetime.fromisoformat(sys.argv[3])).date().isoformat())
' "FREQ=WEEKLY;BYDAY=SU" "2026-09-06" "2026-09-03"     # -> 2026-09-13

obsidian property:set name="last done" value="2026-09-03" path="tasks/Mow Lawn.md"
obsidian property:set name=due value="2026-09-13" path="tasks/Mow Lawn.md"
obsidian property:set name=done value=false type=checkbox path="tasks/Mow Lawn.md"
obsidian append path="tasks/Mow Lawn.md" content='\n- 2026-09-03 - front and back\n'

obsidian base:query path="tasks/task base.base" format=json   # read back
```

`frequency` was checked before anything was written, the next date came from
the evaluator rather than arithmetic, and the last line is the only evidence
the writes happened.

## References

- `references/schema.md` - the field contract and the values already in use
- `references/recurrence.md` - RRULE grammar, the evaluator, and the
  expand-versus-limit traps
- `references/base.md` - repairing or rebuilding the `.base` file
