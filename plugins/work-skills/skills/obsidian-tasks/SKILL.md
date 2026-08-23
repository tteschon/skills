---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault - one note per task, identified by a type property set to task and collected by a Bases file, carrying status, due, priority, category, and cadence. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward after doing it, or ask what to work on next - what are my top tasks, what is overdue, what should I do this weekend, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task base, a task repo, a task note's status or cadence, or a backlog of home, yard, or vehicle chores. Do not use it for checkbox tasks inline in note bodies - what the obsidian tasks command lists - do not use it to review the whole base or to sweep out finished tasks - groom my tasks, what is stale, clear out my done tasks - which is obsidian-task-grooming; and do not use it for general vault reading, searching, or note editing - obsidian-vault covers those.
compatibility: Requires the obsidian CLI and a vault whose task notes carry a type property of task, collected by a Bases file
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks, move them
through their lifecycle, roll recurring chores forward after they are done,
and answer what to work on next.

**A note is a task because it has `type: task`, not because of where it
lives.** The base collects them wherever they sit. Every write here changes
the user's real notes - one of them deletes a note - and the CLI exits 0 on
failure, so nothing is done until the read-back in Step 7.

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
predating those views has neither; Step 6's rules still apply.

**The base includes done tasks.** Its filter no longer excludes them, so
`base:query` is the full inventory rather than a list of open work. Two
consequences: drop `status: done` rows before ranking anything (Step 6), and
recognise them as `obsidian-task-grooming`'s sweep queue rather than work.

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

## Step 3 - Change status, and complete a one-time task

The canonical set is `backlog`, `active`, `done`:

```bash
obsidian property:set name=status value=active path="<path>"
```

**Check `cadence` before writing `done`** - it separates the two kinds of
task, and the branch is not recoverable by reading the note afterwards. A
task *with* a cadence goes to Step 4 and never gets `status: done`. A task
*without* one is finished for good here, and finishing it removes the note:

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian property:set name=status value=done path="<path>"
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

**Confirm with the user before the `delete`, naming the note.** It is the one
command in this skill that removes work. Write `status: done` first even
though the note is about to go: the trashed copy is recoverable, and it
should read as finished work rather than as an abandoned draft.

Deleting is right only because the task is one-time. Anything the user may
want later - what was actually done, a measurement, a receipt - belongs in a
note that outlives the task, so offer to move it before deleting rather than
after. The ones already sitting in the base are swept by
`obsidian-task-grooming`, not here.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is still the most likely mistake in this skill, but it
no longer hides: done tasks stay in the base, so a done row carrying a cadence
is visible as the anomaly it is. `obsidian-task-grooming` lists those rows for
roll-forward and never deletes them - **`cadence` is what keeps a task out of
the sweep**, which is one more reason never to clear it.

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

## Step 5 - Sweeping the base belongs to grooming

Finished one-time tasks stay in the base rather than vanishing, and clearing
them out is `obsidian-task-grooming`'s Step 4: it surveys the whole base, lists
every candidate by name, and deletes on a single confirmation. Hand off to it
rather than sweeping here.

The rule that decides what may go - **`cadence` empty means sweepable,
`cadence` set means never delete, roll it forward instead** - lives there and
nowhere else. Do not re-derive it in this skill; two copies of that guard are
two things that can drift apart, and the failure mode is a deleted recurring
schedule.

Step 3 above is a different thing and stays here: it removes the one task the
user finishes or abandons in front of you, named in the conversation. That is
a single note, not a pass over the base.

## Step 6 - Answer what to work on

**Drop `status: done` rows before ranking.** They sit in the base now and they
are not work; scheduling one is the new way to get this step wrong.

The base's Table view sorts by `due` ascending, then `status` descending. That
front-loads the soonest work and pushes empty `due` to the end, but it is not
a priority ranking. Any ranking is this skill's, so state the rule rather than
implying the vault supplied it.

Default ranking, highest first:

1. Overdue - `overdue` is true, or `due` is a date before today
2. `status: active`
3. `priority: high`, then `medium`, then `low`
4. Ties broken by `due`, empty `due` last

Prefer the base's own `overdue` and `days_until_due`, and query
`view="Today"` or `view="This week"` rather than filtering every row by hand.
Both filter on `due` alone, not on `status` - a done task that still carries a
due date comes back in them, so drop done rows after querying either.

Say how many tasks were considered, counting open ones only. A count that
drops between runs means a task was completed and swept, not that something
went missing. Recurring tasks with no `due` are waiting on their first
completion - list them separately rather than as overdue.

## Step 7 - Verify, then report

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>`, `Set <property>: <value>`, or
   `Moved to trash: <path>`. A line starting with `Error: ` is a failure -
   including `Error: File "..." not found.`, which is what a delete against a
   mistyped path prints in place of doing anything.
2. Re-run the Step 1 `base:query`. Done tasks stay in the base now, so absence
   has one innocent cause and one failure:

   | Absent from `base:query` | Meaning |
   |---|---|
   | You deleted it in Step 3, or grooming swept it | Correct - `obsidian read` on the path confirms it, printing `Error: File "..." not found.` |
   | Anything else | **The note has no `type: task`** - the classic failure |

   The second is invisible from the note alone, which is why the read-back
   goes against the base and not the file. A completed one-time task that is
   still *present* means the delete did not happen - check its output line.

Never report a change as made on the strength of a silent command. Then give
the note path, the fields changed, and their new values, quoting the
read-back. For a roll-forward, state the new `due` and how it was computed.
For a deletion, name every note removed and say it is recoverable
from the vault trash. If a command printed `Error: `, say what did not happen.

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
- **The base holds done tasks too.** The filter no longer excludes
  `status: done`, so `base:query` is the full inventory rather than a list of
  open work. Drop done rows before ranking, and never schedule one as if it
  were outstanding. Clearing them out is grooming's sweep, not this skill's.
- **`cadence` is empty on a one-time task, not missing.** The template writes
  the key with no value, so `cadence:` appears on every task note and a test
  for an absent line matches nothing - a branch built that way sends every
  task down the one-time path. `base:query` returns `null` for an empty key and for a
  genuinely absent one alike, which is why the queried value is the one to
  test.
- **`obsidian delete` trashes by default; never pass `permanent`.** Plain
  `delete` prints `Moved to trash: <path>` and the note stays recoverable from
  the vault trash until the user empties it. `permanent` skips that, and
  nothing in this skill needs it. Deletion is also the one action here to
  confirm with the user before running.
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
