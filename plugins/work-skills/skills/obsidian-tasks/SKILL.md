---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault's task repo - one note per task carrying status, due, priority, category, cadence, and last done frontmatter, listed by a Bases file. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward after doing it, or ask what to work on next - what are my top tasks, what is overdue, what should I do this weekend, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task repo, Home Base, a task note's status or cadence, or a backlog of home, yard, or vehicle chores. Do not use it for checkbox tasks written inline in note bodies, and do not use it for general vault reading, searching, or note editing - obsidian-vault covers those.
compatibility: Requires the obsidian CLI and a vault holding one note per task with status, due, priority, category, cadence, and last done frontmatter
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks from the
user's template, move them through their lifecycle, roll recurring chores
forward after they are done, and answer what to work on next.

Every write here changes the user's real notes, and the CLI exits 0 on
failure. Nothing is done until the read-back in Step 6.

## Before you start

`obsidian-vault` covers the CLI itself - the preflight, vault targeting,
and why exit codes cannot be trusted. Do not re-derive any of that. Run its
check first:

```bash
command -v obsidian
```

Exit 1 means the CLI is absent and unfixable from the shell - stop and say
so. Then confirm the layout, because every path below depends on it:

| Check | Command | Expect |
|---|---|---|
| Right vault | `obsidian vault info=name` | the vault holding the tasks |
| Task repo exists | `obsidian files folder="Tasks/task repo"` | the task notes |
| Base exists | `obsidian bases` | `Tasks/Home Base.base` |

Folder and base names are per-vault. If they differ from the above, use what
the vault reports - do not assume these literals.

## Step 1 - Survey before acting

Read current state before any write. Never assume a status from memory, from
the user's phrasing, or from a Kanban board.

```bash
obsidian base:query path="Tasks/Home Base.base" format=json
```

One object per task, keyed by the base view's columns - `path`, `file name`,
`category`, `cadence`, `created`, `due`, `last done`, `priority`, `status`.
That single call is usually the whole survey; do not read notes one by one.

## Step 2 - Create a task

Create from the user's template so defaults and the `created` wikilink come
from one place:

```bash
obsidian create name="<task name>" path="Tasks/task repo" \
  template="task template @{{date}}"
```

`path=` is the **folder**; `name=` becomes the filename. The template name
contains a literal `{{date}}` and must be quoted exactly as listed by
`obsidian templates`. Success prints `Created: <path>`.

Then set only the fields the user actually specified:

```bash
obsidian property:set name=priority value=medium path="<path>"
obsidian property:set name=category value=yard path="<path>"
```

**Never pass `type=` on `property:set`.** See Gotchas - it rewrites the
vault-wide property type. Ask for `category` and `priority` when the user
did not say; leave `due` and `cadence` empty rather than inventing them.

Read `references/schema.md` before creating or migrating - it holds the
field contract, the values already in use, and why `due` is not always a
date.

## Step 3 - Change status

The canonical set is `backlog`, `active`, `done`.

```bash
obsidian property:set name=status value=active path="<path>"
```

Confirm with the user before setting anything to `done`. If the task has a
`cadence`, do not use this step at all - go to Step 4.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is the most likely mistake in this skill.

| Cadence | On completion |
|---|---|
| `weekly`, `monthly`, `every N months`, `annually` | `last done` = today; `due` = today + cadence; `status` = `backlog` |
| `seasonally` | `last done` = today; leave `due` empty; `status` = `backlog` |
| `every N mi` | **Ask for the current odometer.** `last done` = `YYYY-MM-DD (X mi)`; `due` = `~<X+N> mi`; `status` stays `active` |

The odometer is not in the vault and cannot be derived from the last
reading - ask, and stop if the user does not know. Writing a guessed
mileage silently corrupts the next service interval.

Worked example, Crosstrek at 25,900 mi with `cadence: every 3,000 mi`:

```bash
obsidian property:set name="last done" value="2026-08-16 (25,900 mi)" path="<path>"
obsidian property:set name=due value="~28,900 mi" path="<path>"
```

## Step 5 - Answer what to work on

The base defines **no sort order** - its `order:` field is column order for
the table view, and its only filter is the folder. Any ranking is this
skill's, so state the rule being used rather than implying the vault
supplied it.

Default ranking, highest first:

1. Overdue - `due` parses as a date and is before today
2. `status: active`
3. `priority: high`, then `medium`, then `low`
4. Ties broken by `due`, empty `due` last

**Report non-date `due` values as their own group.** Vehicle tasks carry
mileage strings, so they are neither overdue nor not-overdue without an
odometer reading. Dropping them from the answer hides real work; sorting
them as dates is wrong.

Say how many tasks were considered and note anything conspicuous - a
`cadence` with an empty `last done` cannot be scheduled at all, and that is
worth surfacing rather than silently ranking last.

## Step 6 - Verify

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>` or `Set <property>: <value>`. A line
   starting with `Error: ` is a failure.
2. Re-run the Step 1 `base:query` and confirm the task now reads the way it
   should. For a new note, `obsidian read path="<path>"` and confirm
   `created` resolved to `[[YYYY-MM-DD]]` rather than a literal `{{date}}`.

Do not report a change as made on the strength of a silent command.

## Step 7 - Report

Give the note path, the fields changed, and their new values, quoting the
read-back. For a recurrence roll-forward, state the new `due` and how it was
computed. If a command printed `Error: `, say what did not happen.

## Gotchas

- **Never pass `type=` to `property:set`.** It rewrites the property's type
  vault-wide in `.obsidian/types.json`, not just on the note being edited.
  `property:set name=due value="~25,731 mi" type=text` flips `due` from
  `date` to `text` for every note and for the base, silently breaking date
  sorting everywhere. Omitting `type=` writes the same value and leaves the
  registry untouched, which is why mileage strings can live in a
  `date`-typed field at all.
- **`due` and `last done` are `date`-typed but hold text on vehicle tasks** -
  `~25,731 mi`, `2026-06-19 (22,731 mi)`. Parse defensively. Date arithmetic
  on the raw value will raise or, worse, sort a mileage string as a date.
- **`created` is a wikilink, not a date** - `"[[2026-08-16]]"`, pointing at
  the daily note. Writing a bare date breaks that backlink, and the property
  is deliberately unregistered so it stays text. The template handles this;
  do not set `created` by hand.
- **The user's template may default `status` to a value outside the
  canonical set.** Read the note back after `create` and correct `status`
  rather than trusting the template.
- **`Tasks/Home Board.md` and `Tasks/reoccurring tasks.md` are stale legacy
  views.** They look authoritative - a Kanban board with columns, a table
  with cadences - and they disagree with the frontmatter on roughly a fifth
  of tasks, including tasks sitting in Backlog on the board while their note
  says `active`. Never read a status from them, and never write them. If
  asked to sync them, explain that frontmatter is the source of truth and
  that hand-maintained duplicates are what caused the drift.
- **A `cadence` with an empty `last done` has no computable next due date.**
  Most recurring tasks in the vault are in this state. Do not invent a
  `last done` to make the math work - ask when it was last done, or say it
  cannot be scheduled yet.
