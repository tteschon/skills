---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault - one note per task, identified by a type property set to task and collected by a Bases file, carrying status, due, priority, category, cadence, and last done. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward after doing it, or ask what to work on next - what are my top tasks, what is overdue, what should I do this weekend, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task base, a task repo, a task note's status or cadence, or a backlog of home, yard, or vehicle chores. Do not use it for checkbox tasks written inline in note bodies - those are what the obsidian tasks command lists - and do not use it for general vault reading, searching, or note editing - obsidian-vault covers those.
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
exit codes cannot be trusted; do not re-derive it. Run its check, then
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
| No task base | Confirm with the user, then build the one in `references/base.md` |

**Use the path the app prints, never the one `ls` shows** - paths are
case-sensitive to the CLI and case-insensitive on macOS disk. See Gotchas.
Then `obsidian read path="<base path>"` to learn its filter, which names the
property marking a task and any folder the base restricts to.

## Step 1 - Survey and learn the schema

Read current state before any write, and let the existing rows define the
field set rather than a list baked into this skill:

```bash
obsidian base:query path="<base path>" format=json
```

One object per task, keyed by the base view's columns. **The keys are the
schema** - a new task should carry the same ones. Never assume a status from
memory or from the user's phrasing.

Formula columns come back with the properties. When the base defines
`days_until_due` and `overdue`, **those values are the answer** - the vault
computed them, so do not recompute from `due`. `base:views` lists what a base
offers, and `base:query ... view="Today"` queries one directly. A base
predating those views has neither; Step 5's rules still apply.

## Step 2 - Create a task

`base:create` satisfies the base's filters on its own - it stamps the filter
property into the new note and writes the file into the folder the filter
names, or beside the `.base` file when it names none. The note comes back
scaffolded: every column in the view's `order:` list as an empty key, with
`type: task` filled in. Fill in what the user gave, plus `created`, which
arrives empty because `base:create` takes no template:

```bash
obsidian base:create path="<base path>" name="<task name>"
obsidian property:set name=status value=backlog path="<new path>"
obsidian property:set name=priority value=medium path="<new path>"
obsidian property:set name=category value=yard path="<new path>"
obsidian property:set name=created value="[[<today>]]" path="<new path>"
```

`created` is the daily-note backlink - a quoted wikilink, never a bare date.
The user's template sets it; `base:create` does not.

**Never pass `type=` to `property:set`** - see Gotchas. It is doubly
confusing here, because `type` is also the property that marks a task:
`name=type` is correct, `type=text` is the destructive one.

Ask for `category` and `priority` when the user did not say; leave `due` and
`cadence` empty rather than inventing them. If `base:create` fails, fall back
to `create name="<name>" path="<folder>"` then
`property:set name=type value=task` - the note is only a task once it has
that property.

Read `references/schema.md` before creating or migrating: it holds the field
contract and the values already in use, so a new task reuses a `category`
instead of coining one.

## Step 3 - Change status, and complete an ad-hoc task

The canonical set is `backlog`, `active`, `done`:

```bash
obsidian property:set name=status value=active path="<path>"
```

**Check `cadence` before writing `done`** - it separates the two kinds of
task, and the branch is not recoverable by reading the note afterwards. A
task *with* a cadence goes to Step 4 and never gets `status: done`. A task
*without* one is confirmed with the user, then gets `status: done` and
`last done` = today.

A completed ad-hoc task leaves the base, which filters on `status != "done"`.
The note keeps its full history on disk; it just stops appearing in queries.
**That disappearance is the success condition, not a failed write** - Step 6
tells the two apart.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is the most likely mistake in this skill, and it now
drops the task out of the base - so the mistake hides itself.

Due dates snap to the **end of a period**, computed from today rather than
from `last done`. Worked from a completion on Monday 2026-08-17:

| Cadence | New `due` |
|---|---|
| `weekly` | 2026-08-30 (Sunday) |
| `monthly` | 2026-09-30 |
| `every 6 months` | 2027-02-28 |
| `annual` | 2027-08-31 |

Then write three properties, in this order, and append to the body:

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian property:set name=due value="<computed>" path="<path>"
obsidian property:set name=status value=backlog path="<path>"
obsidian append path="<path>" content='\n- <today> - <detail>\n'
```

`last done` and `due` are real dates, always. Non-date detail - mileage, a
part number, what was done - goes on the body log line under a
`## Service log` heading, **never** into those two fields. The body log also
keeps the history that `last done` overwrites.

Read `references/recurrence.md` for any cadence outside that table, the
algorithm behind it, and the month-end and leap-year edges. It exists to stop
you rolling the completion date forward by the interval instead of snapping
to a period end - a drift that compounds every cycle.

## Step 5 - Answer what to work on

The base defines **no sort order** - `order:` is column order. Any ranking is
this skill's, so state the rule rather than implying the vault supplied it.

Default ranking, highest first:

1. Overdue - `overdue` is true, or `due` is a date before today
2. `status: active`
3. `priority: high`, then `medium`, then `low`
4. Ties broken by `due`, empty `due` last

Prefer the base's own `overdue` and `days_until_due`, and query
`view="Today"` or `view="This week"` rather than filtering every row by hand.

Say how many tasks were considered. The base holds only open work, so a count
that drops between runs usually means an ad-hoc task was completed, not that
something went missing. Recurring tasks with no `due` are waiting on their
first completion - list them separately rather than as overdue.

## Step 6 - Verify, then report

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>` or `Set <property>: <value>`. A line
   starting with `Error: ` is a failure.
2. Re-run the Step 1 `base:query`, then read the note when a task is absent
   from it. Absence has two causes meaning opposite things:

   | Absent from `base:query` | Meaning |
   |---|---|
   | Note has `status: done` | Correct - an ad-hoc task was completed |
   | Anything else | **The note has no `type: task`** - the classic failure |

   The second is invisible from the note alone, which is why the read-back
   goes against the base and not the file.

Never report a change as made on the strength of a silent command. Then give
the note path, the fields changed, and their new values, quoting the
read-back. For a roll-forward, state the new `due` and how it was computed.
If a command printed `Error: `, say what did not happen.

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
- **Flag sets vary by CLI build, and `obsidian help` on the machine wins.**
  Published documentation describes a `silent` flag that this build does not
  have; here `open` is an opt-in instead. Check `obsidian help <command>`
  before using a flag taken from any external source.
- **`obsidian tasks` is a different system.** It lists checkbox tasks written
  inline in note bodies (`done`, `todo`, `status="<char>"`). This skill never
  uses it - a task here is a note with `type: task`, not a `- [ ]` line.
- **The base holds only open work.** Its filter includes `status != "done"`,
  so `base:query` is not an inventory of task notes - completed ad-hoc tasks
  are still on disk. Auditing history means reading the notes.
- **Text in `due` breaks computation silently, not loudly.** A formula over a
  non-date `due` errors, but a comparison like `due < today()` returns
  **`false`** - so the task is never flagged overdue and date-window views
  omit it with no error at all. Both fields are real dates on every task
  today; keep them that way.
- **`created` is a wikilink, not a date** - `"[[2026-08-16]]"`, pointing at
  the daily note. Writing a bare date breaks that backlink. The template
  handles it; do not set `created` by hand.
- **Never read or write task state from a Kanban board or a hand-maintained
  table.** They look authoritative and drift from the frontmatter;
  `references/schema.md` measures the drift and explains why the board is
  still a legitimate way to *create* tasks.
