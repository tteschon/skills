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

## Step 3 - Change status, and complete an ad-hoc task

The canonical set is `backlog`, `active`, `done`.

```bash
obsidian property:set name=status value=active path="<path>"
```

**Check `cadence` before writing `done`.** It is what separates the two kinds
of task, and the branch is not recoverable by reading the note afterwards:

| `cadence` | Completing the task means |
|---|---|
| Present | **Go to Step 4.** Never write `status: done` |
| Absent | Confirm with the user, then `status` = `done` and `last done` = today |

A completed ad-hoc task leaves the base - the base filters on
`status != "done"`. The note stays in the vault with its full history; it just
stops appearing in queries and reports. **That disappearance is the success
condition, not a failed write.** Step 6 says how to tell the two apart.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is the most likely mistake in this skill - and now it
also drops the task out of the base, so the mistake hides itself.

Due dates snap to the end of a period rather than rolling forward from the
completion date. Compute from **today**, not from `last done`:

```
weekly:   this_sunday = today + (6 - today.weekday())   # Mon=0 .. Sun=6
          due = this_sunday + 7 days                    # end of NEXT week

monthly / every N months / annual:
          target = today's month + N months             # monthly N=1, annual N=12
          due = last calendar day of target month
```

Worked from a completion on Monday 2026-08-17:

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

`last done` and `due` are real dates, always. Detail that is not a date -
mileage, a part number, what was actually done - goes on the body log line
under a `## Service log` or `## Completion log` heading, **never** back into
those two fields. That is what broke date sorting across the whole base
before, and the body keeps the full history that `last done` overwrites.

**A cadence these rules do not cover** - `seasonally`, or anything that will
not parse - gets `last done` and `status: backlog` with `due` left empty. Say
so in the report. Do not invent an interval.

Because `due` is computed from the completion date, a recurring task with an
empty `last done` is not a problem: it simply has no due date until the first
time it is completed.

## Step 5 - Answer what to work on

The base defines **no sort order** - `order:` is column order for the table
view. Any ranking is this skill's, so state the rule rather than implying the
vault supplied it.

Default ranking, highest first:

1. Overdue - `due` parses as a date and is before today
2. `status: active`
3. `priority: high`, then `medium`, then `low`
4. Ties broken by `due`, empty `due` last

`due` is a real date on every task. If a non-date value ever appears there,
something wrote text into a `date` field - report it as a data fault rather
than trying to rank it.

Say how many tasks were considered. The base holds only open work now, so a
count that drops between runs usually means an ad-hoc task was completed, not
that something went missing. Recurring tasks with no `due` are waiting on
their first completion, not broken - list them separately rather than as
overdue.

## Step 6 - Verify

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>` or `Set <property>: <value>`. A line
   starting with `Error: ` is a failure.
2. Re-run the Step 1 `base:query`, then read the note itself when a task is
   absent from it. Absence now has two causes and they mean opposite things:

   | Absent from `base:query` | Meaning |
   |---|---|
   | Note has `status: done` | Correct - an ad-hoc task was completed |
   | Anything else | **The note has no `type: task`** - the classic failure |

   The second is invisible from reading the note alone, which is why the
   read-back is against the base and not the file.

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
- **The base holds only open work.** Its filter includes `status != "done"`,
  so `base:query` is not an inventory of task notes - completed ad-hoc tasks
  still exist on disk and are simply not in it. Anything auditing history has
  to read the notes.
- **Text in `due` breaks computation silently, not loudly.** A formula over a
  non-date `due` returns `Error: Invalid operator between String and Date`,
  but a comparison like `due < now()` returns **`false`** - so the task is
  never flagged overdue, and a `due <= now() + "7 days"` view omits it with no
  error at all. Both fields are real dates on every task today. Keep them
  that way; non-date detail belongs on a body log line.
- **`created` is a wikilink, not a date** - `"[[2026-08-16]]"`, pointing at
  the daily note. Writing a bare date breaks that backlink. The template
  handles it; do not set `created` by hand.
- **Next `due` comes from the completion date, never from `last done`.** An
  empty `last done` is not an obstacle - the task just has no due date until
  it is first completed. Do not backfill a `last done` to make arithmetic
  work; ask, or leave `due` empty and say so.
- **`obsidian create` does not overwrite.** Pointed at an existing path it
  silently writes `<name> 1.base` alongside the original, and a query against
  the original path then returns the old content - which reads as an edit
  that did not take. Check the `Created:` line for a path you did not intend.
- **A file written to the vault from the shell is not visible to the CLI
  immediately.** `obsidian read` serves the app's cached copy and can return
  pre-edit content for a moment after an external write, while `cat` on the
  same path shows the new bytes. When a read looks stale, confirm against the
  filesystem before concluding the write failed.
- **A Kanban board that creates task notes still never writes status back.**
  Boards and hand-maintained tables look authoritative and drift from the
  frontmatter. Never read a status from one, and never write one.
