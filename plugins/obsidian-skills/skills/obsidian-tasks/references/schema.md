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
| `done` | **checkbox** | `true` once finished - on a one-time task that means the note is about to be deleted. Binary: there is no in-flight state |
| `due` | **date** | A real date on every task. Keep it that way - see below |
| `created` | unregistered | A wikilink, `"[[YYYY-MM-DD]]"`, not a date |
| `priority` | text | `low`, `medium`, `high` |
| `category` | unregistered | Free text, but reuse an existing value |
| `last done` | **date** | Latest completion only; the body log holds the history |
| `frequency` | text | An RFC 5545 `RRULE` value. **Set = recurring, empty = one-time.** Evaluated in Step 4, and what keeps a task out of the grooming sweep |
| `asset` | unregistered | Optional wikilink to the thing serviced, e.g. `"[[Cub Cadet Ultima 54 Mower]]"` |

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

## Recurring versus one-time

`frequency` is the only thing that separates the two kinds of task. There is
no `recurring` flag; a task recurs if and only if it carries a rule.

| | One-time | Recurring |
|---|---|---|
| `frequency` | empty | an `RRULE` value |
| On completion | `done: true`, `last done` = today | `last done` = today, `due` recomputed, `done` back to `false` |
| Afterwards | Note deleted to the vault trash | Stays, with a new due date |

`frequency` is **empty, not absent**, on a one-time task - the template writes
the key on every note. Nothing distinguishes the two kinds in the file text,
so read the value, not the presence of the line. `base:query` returns `null`
either way, which is the reliable place to test it.

> **An empty key and an empty string are not the same to Bases.** The template
> writes a bare `frequency:`, which is `null`. Writing `property:set
> name=frequency value=""` produces `frequency: ""`, which is **not** null - a
> `frequency != null` filter then matches every one-time task, and the base
> view returns wrong rows with no error. Verified: the same probe returned 29
> rows with `""` and 11 with a bare key. Never seed the empty key through
> `property:set`; let the template write it.

That one field carries more weight than its size suggests, because it is also
what protects a task from deletion. A recurring task is never left in `done`;
if one is, it has stopped recurring, and the rule is the only reason the sweep
passes it over instead of removing it.

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
| `done` | `false` on every open task; `true` only briefly, on a finished one-time task awaiting deletion |
| `priority` | All three are in use, but the distribution is lopsided - mostly `low`, then `medium`, with `high` rare. Treat a `high` as deliberate: it is the one value that reorders Step 6 |
| `category` | `yard`, `home`, `errands`, `vehicle`, `health` |
| `frequency` | `FREQ=WEEKLY;BYDAY=MO`, `FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1`, `FREQ=YEARLY` - empty on one-time tasks |
| `asset` | wikilinks to equipment notes; absent on most tasks |

Every task currently carries a `category`. A note that turns up without one
is a gap to ask about, not a value to invent.

## The three parallel systems

The vault contains three views of the same tasks. Only the first is written.

| System | Role |
|---|---|
| Notes carrying `type: task` | **Source of truth.** The only thing this skill writes |
| A Kanban board note | A *creation and viewing* surface, not a mirror |
| A recurring-tasks table note | Hand-maintained view, stale |

The board deserves a precise description, because "stale duplicate"
understates it. Two things are true and neither is obvious.

**Its cards are not task notes.** `🗃 Kanban Cards/` holds 26 notes and **none
of them carry `type: task`**, so not one is in the base. Every task row lives
in `tasks/task repo` (31) or `tasks` (2). The cards run a different schema
altogether - `type: story`, `domain`, `assignee`, `size`, `opened` - and they
are not uniformly tasks either: they range from real work ("change internet",
on hold since 2023) through a camping packing list to one whose entire body is
`test`. Whatever `kanban:settings` claims about `new-note-template`, the notes
in that folder did not come out of the task template.

**It does not write back.** Moving a card between columns changes the card's
position and nothing else, so the frontmatter never learns about it. At an
earlier survey of 34 tasks - taken while completion still lived in a `status`
text property - 7 of the 33 appearing in both disagreed: three the frontmatter
called `active` sat in the board's Backlog column, and three the board had
archived as done were still `backlog` in frontmatter. The property has since
become the `done` checkbox; the board still does not write to it.

So the board is a place the user thinks about tasks, and an unreliable way to
read their state. Write frontmatter only. An agent editing a Kanban plugin's
markdown can also corrupt card formatting or drop the settings block, which
would break a flow the user depends on.

When asked to sync or update the board, say that frontmatter is the source
of truth, that the legacy views are stale by a known amount, and offer to
report the drift instead. Reconciling them - and deciding which of the 26
orphan cards are real tasks - is a deliberate one-time job the user should
decide on, not a side effect of completing a task and not something
`obsidian-task-grooming` does on a schedule.
