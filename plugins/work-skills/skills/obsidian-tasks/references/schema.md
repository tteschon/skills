# The task note contract

Read this before creating a task, migrating existing ones, or interpreting a
field whose value looks wrong. The field types and the values already in use
are not guessable from the field names, and two of them behave differently
from how they are declared.

## The fields

One note per task, with this frontmatter. The shape comes from the user's
template, which is the only thing that should ever write `created`.

| Field | Declared type | Reality |
|---|---|---|
| `type` | text | **The identity field.** `task` is what puts a note in the base |
| `status` | text | `backlog`, `active`, `done` - `done` removes it from the base |
| `due` | **date** | A real date on every task. Keep it that way - see below |
| `created` | unregistered | A wikilink, `"[[YYYY-MM-DD]]"`, not a date |
| `priority` | text | `low`, `medium`, `high` |
| `category` | unregistered | Free text, but reuse an existing value |
| `last done` | **date** | Latest completion only; the body log holds the history |
| `cadence` | text | **Present = recurring, absent = ad-hoc.** Parsed by Step 4 |

"Declared type" is what `.obsidian/types.json` registers. Unregistered
fields infer as text and are safe to write. The two registered as `date` are
the ones worth protecting - see "Dates are dates" below.

### `type` decides membership, not the folder

A note is a task because it carries `type: task`. Folder is irrelevant - the
base collects matching notes from anywhere in the vault, and a note sitting
in the task folder without the property is invisible to it. When a task
created through this skill does not show up in `base:query`, a missing
`type` is the first thing to check.

`type` is a vault-wide namespace shared with other Bases, not a
task-only field. Values seen alongside it include `recipe`, `story`, and
`essay`, each backing its own base. Two consequences:

- Do not repurpose `type` for anything else on a task note.
- Adding `type: task` to a note anywhere - including a template - puts it in
  the task base. The base needs a `!file.inFolder("Templates")` clause, or
  the task template lists itself as a task.

Confirm the live registry rather than trusting this table, since a stray
write can change it:

```bash
obsidian property:read name=<field> path="<a task note>"
```

## Recurring versus ad-hoc

`cadence` is the only thing that separates the two kinds of task. There is no
`recurring` flag; a task recurs if and only if it carries a cadence.

| | Ad-hoc | Recurring |
|---|---|---|
| `cadence` | absent | present |
| On completion | `status: done`, `last done` = today | `last done` = today, `due` recomputed, `status` back to `backlog` |
| Afterwards | Leaves the base | Stays, with a new due date |

The base filter includes `status != "done"`, so completing an ad-hoc task
removes it from every query and report while leaving the note on disk. A
recurring task is never left in `done` - if one is, it has stopped recurring
and nothing will say so.

## Dates are dates

`due` and `last done` are registered `date` and hold real dates on every task.
This was not always true: vehicle tasks once stored `~25,731 mi` and
`2026-06-19 (22,731 mi)` in them, which broke sorting, comparison, and every
formula that touched them - and broke them *quietly*, since `due < now()` on a
text value returns `false` rather than raising.

The rules that keep it true:

- **Non-date detail goes in the body**, on a dated line under a
  `## Service log` or `## Completion log` heading - mileage, part numbers,
  what was actually done. `last done` is overwritten on each completion; the
  body log is the history.
- **Never write these fields with `property:set ... type=`.** Passing
  `type=text` to make a non-date value fit rewrites `due` to text for the
  whole vault and breaks date sorting on every other task. Omit `type=`.
- **Usage-based intervals are approximated as time.** The oil changes are
  `every 6 months` rather than `every 3,000 mi`, because a date is
  schedulable and a mileage string is not. The odometer reading still gets
  recorded - on the body log line.

## Values already in use

Reuse these rather than coining new ones. A new `category` is fine when the
task genuinely does not fit, but check first - `obsidian base:query` returns
every value in one call.

| Field | Observed values |
|---|---|
| `status` | `backlog` dominates; `active` for in-flight; `done` only on completed ad-hoc tasks, which the base then excludes |
| `priority` | `low`, `medium`, `high` - `high` is rare and worth respecting |
| `category` | `yard`, `home`, `errands`, `vehicle`, `health` |
| `cadence` | `weekly`, `every 6 months`, `annual` - absent on ad-hoc tasks |

Some notes carry no `category` at all. That is a gap to ask about, not a
value to invent.

## The three parallel systems

The vault contains three views of the same tasks. Only the first is written.

| System | Role |
|---|---|
| Notes carrying `type: task` | **Source of truth.** The only thing this skill writes |
| A Kanban board note | A *creation and viewing* surface, not a mirror |
| A recurring-tasks table note | Hand-maintained view, stale |

The board deserves a precise description, because "stale duplicate"
understates it. Its `kanban:settings` block sets `new-note-template` and
`new-note-folder` to the same template and folder used here, so dragging a
new card onto the board really does create a proper task note - and once the
template carries `type: task`, those notes land in the base automatically.
What it does not do is write back - moving a card between columns changes the
card's position and nothing else, so `status` in the frontmatter never learns
about it.

That is the mechanism behind the drift. At a survey of 34 tasks, 7 of the 33
appearing in both disagreed - three the frontmatter called `active` sat in
the board's Backlog column, and three the board had archived as done were
still `backlog` in frontmatter. One note had no card, one card had no note,
and several archived cards are plain text that never became notes at all.

So the board is a legitimate way for the user to *add* tasks, and an
unreliable way to read their state. Write frontmatter only. An agent editing
a Kanban plugin's markdown can also corrupt card formatting or drop the
settings block, which would break the creation flow the user depends on.

When asked to sync or update the board, say that frontmatter is the source
of truth, that the legacy views are stale by a known amount, and offer to
report the drift instead. Reconciling them is a deliberate one-time job the
user should decide on - not a side effect of completing a task.
