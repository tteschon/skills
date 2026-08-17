---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault - one note per task, identified by a type property set to task and collected by a Bases file, carrying status, due, priority, category, cadence, and last done. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward after doing it, or ask what to work on next - what are my top tasks, what is overdue, what should I do this weekend, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task base, a task repo, a task note's status or cadence, or a backlog of home, yard, or vehicle chores. Do not use it for checkbox tasks written inline in note bodies, and do not use it for general vault reading, searching, or note editing - obsidian-vault covers those.
compatibility: Requires the obsidian CLI and a vault whose task notes carry a type property of task, collected by a Bases file
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks, move them
through their lifecycle, roll recurring chores forward after they are done,
and answer what to work on next.

**A note is a task because it has `type: task`, not because of where it
lives.** The base collects them wherever they sit. Every write here changes
the user's real notes, and the CLI exits 0 on failure, so nothing is done
until the read-back in Step 6.

## Before you start

`obsidian-vault` covers the CLI itself - preflight, vault targeting, and why
exit codes cannot be trusted. Do not re-derive it. Run its check, then
**resolve the layout rather than assuming it**:

```bash
command -v obsidian          # exit 1 - stop, not fixable from the shell
obsidian vault info=name     # confirm the right vault
obsidian bases               # find the task base
```

| Found | Do |
|---|---|
| A task base | Use the path `bases` printed, exactly |
| Several bases | Pick by name, or ask; do not guess |
| No task base | Offer to bootstrap - see below |

**Use the path the app prints, never the one `ls` shows** - paths are
case-sensitive to the CLI and case-insensitive on macOS disk. See Gotchas.

Then `obsidian read path="<base path>"` to learn its filter, which names the
property that marks a task and any folder the base restricts to.

### Bootstrap

When there is no task base, confirm with the user, then create one at
`tasks/task base.base` with this content:

```yaml
filters:
  and:
    - type == "task"
    - '!file.inFolder("Templates")'
views:
  - type: table
    name: Table
    order: [file.name, category, due, priority, status]
```

Write it with `obsidian create path=... content=...`, passing newlines as
literal `\n`. `create` makes missing parent folders on the way, so one call
builds the whole structure, and the base is queryable immediately - no
reload. The `Templates` exclusion is not optional: the task template carries
`type: task` so that template-made notes are real tasks, and without the
clause the template lists itself as one.

## Step 1 - Survey and learn the schema

Read current state before any write, and let the existing rows define the
field set rather than a list baked into this skill:

```bash
obsidian base:query path="<base path>" format=json
```

One object per task, keyed by the base view's columns. **The keys are the
schema** - a new task should carry the same ones. Never assume a status from
memory, from the user's phrasing, or from a Kanban board.

## Step 2 - Create a task

`base:create` satisfies the base's filters on its own - it stamps the filter
property into the new note's frontmatter, and writes the file into the folder
the filter names, or beside the `.base` file when the filter names none:

```bash
obsidian base:create path="<base path>" name="<task name>"
```

The new note comes back scaffolded from the base - every column in the view's
`order:` list present as an empty key, with the filter property (`type:
task`) already filled in. Fill in what the user gave, plus `created`, which
`base:create` leaves empty because it takes no template:

```bash
obsidian property:set name=status value=backlog path="<new path>"
obsidian property:set name=priority value=medium path="<new path>"
obsidian property:set name=category value=yard path="<new path>"
obsidian property:set name=created value="[[<today>]]" path="<new path>"
```

`created` is the daily-note backlink, so write it as a quoted wikilink -
`"[[2026-08-16]]"`, not a bare date. Notes made from the user's template get
this automatically; notes made by `base:create` do not.

**Never pass `type=` to `property:set`** - see Gotchas. This is doubly
confusing here, because `type` is also the name of the property that marks a
task; `name=type` is correct, `type=text` is the destructive one.

Ask for `category` and `priority` when the user did not say. Leave `due` and
`cadence` empty rather than inventing them. If `base:create` fails, fall back
to `create name="<name>" path="<folder>"` followed by
`property:set name=type value=task` - the note is only a task once it has
that property.

Read `references/schema.md` before creating or migrating - it holds the field
contract, the values already in use, and why `due` is not always a date.

## Step 3 - Change status

The canonical set is `backlog`, `active`, `done`.

```bash
obsidian property:set name=status value=active path="<path>"
```

Confirm before setting anything to `done`. If the task has a `cadence`, do
not use this step - go to Step 4.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is the most likely mistake in this skill.

| Cadence | On completion |
|---|---|
| `weekly`, `monthly`, `every N months`, `annually` | `last done` = today; `due` = today + cadence; `status` = `backlog` |
| `seasonally` | `last done` = today; leave `due` empty; `status` = `backlog` |
| `every N mi` | **Ask for the current odometer.** `last done` = `YYYY-MM-DD (X mi)`; `due` = `~<X+N> mi`; `status` stays `active` |

The odometer is not in the vault and cannot be derived from the last
reading - ask, and stop if the user does not know. A guessed mileage
silently corrupts the next service interval.

## Step 5 - Answer what to work on

The base defines **no sort order** - `order:` is column order for the table
view. Any ranking is this skill's, so state the rule rather than implying the
vault supplied it.

Default ranking, highest first:

1. Overdue - `due` parses as a date and is before today
2. `status: active`
3. `priority: high`, then `medium`, then `low`
4. Ties broken by `due`, empty `due` last

**Report non-date `due` values as their own group.** Vehicle tasks carry
mileage strings, so they are neither overdue nor current without an odometer
reading. Dropping them hides real work; sorting them as dates is wrong.

Say how many tasks were considered, and surface anything unschedulable - a
`cadence` with an empty `last done` cannot be scheduled at all.

## Step 6 - Verify

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>` or `Set <property>: <value>`. A line
   starting with `Error: ` is a failure.
2. Re-run the Step 1 `base:query`. **A new task that does not appear in it
   has no `type: task`** - that is the single most likely failure, and it is
   invisible from reading the note alone.

Do not report a change as made on the strength of a silent command.

## Step 7 - Report

Give the note path, the fields changed, and their new values, quoting the
read-back. For a recurrence roll-forward, state the new `due` and how it was
computed. If a command printed `Error: `, say what did not happen.

## Gotchas

- **Never pass `type=` to `property:set`.** It rewrites the property's type
  vault-wide in `.obsidian/types.json`, not on the note being edited.
  `property:set name=due value="~25,731 mi" type=text` flips `due` from
  `date` to `text` for every note and for the base, silently breaking date
  sorting everywhere. Omitting `type=` writes the same value and leaves the
  registry untouched.
- **Paths are case-sensitive to the CLI but not to the macOS disk.** A vault
  folder renamed to `tasks/` in Obsidian still shows as `Tasks/` in `ls`, and
  `base:query path="Tasks/task base.base"` fails with `Base file not found`
  while the lowercase spelling returns every row. Always take paths from
  `obsidian bases` and `obsidian files`, never from the filesystem.
- **`base:create` scaffolds the base's columns but fills only the filter.**
  The new note gets every column in the view's `order:` list as an empty key
  and the filter property populated, and it honours a `file.inFolder(...)`
  clause when choosing the destination. It takes no `template=`, so the
  user's task template is not on this path and `created` arrives empty -
  set the wikilink explicitly or the daily-note backlink is lost.
- **Anything carrying `type: task` joins the base, including the template.**
  The task template needs the property so template-created notes are real
  tasks, which means the base needs a `!file.inFolder("Templates")` clause or
  the template appears as a task. The same trap applies to any other note
  that happens to use the property.
- **`due` and `last done` are `date`-typed but hold text on vehicle tasks** -
  `~25,731 mi`, `2026-06-19 (22,731 mi)`. Parse defensively; date arithmetic
  on the raw value raises or sorts a mileage string as a date.
- **`created` is a wikilink, not a date** - `"[[2026-08-16]]"`, pointing at
  the daily note. Writing a bare date breaks that backlink. The template
  handles it; do not set `created` by hand.
- **A `cadence` with an empty `last done` has no computable next due date.**
  Most recurring tasks are in this state. Do not invent a `last done` to make
  the math work - ask, or say it cannot be scheduled yet.
- **A Kanban board that creates task notes still never writes status back.**
  Boards and hand-maintained tables look authoritative and drift from the
  frontmatter. Never read a status from one, and never write one.
