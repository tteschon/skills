---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault - one note per task, identified by a type property set to task, collected by a Bases file, carrying a done checkbox, due, priority, category, an optional asset link, and an RRULE frequency, and edited alongside the Task Base plugin. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward, or ask what to work on next - what are my top tasks, what is overdue, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task base, the Task Base plugin or its task pane, a task note's done state, asset, or repeat rule, or a backlog of home or yard chores. Do not use it for checkbox tasks inline in note bodies; do not use it to review the whole base or sweep out finished tasks - groom my tasks, what is stale - which is obsidian-task-grooming; and not for general vault reading, searching, or note editing, which is obsidian-vault.
compatibility: Requires the obsidian CLI and a vault whose task notes carry a type property of task; uses the task-base Obsidian plugin when installed, and falls back to a Python RRULE evaluator when it is not
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks, move them
through their lifecycle, roll recurring chores forward after they are done,
and answer what to work on next.

**A note is a task because it has `type: task`, not because of where it
lives.** The base collects them wherever they sit. Every write here changes
the user's real notes - one of them deletes a note - and the CLI exits 0 on
failure, so nothing is done until the read-back in Step 7.

**This skill is not the only writer.** The `task-base` plugin edits the same
notes from inside Obsidian, and where the two disagree the user gets two
answers for one task. Delegate to it wherever it can be reached from the CLI -
`references/plugin.md` says where that is.

## Before you start

`obsidian-vault` covers the CLI itself - preflight, vault targeting, and why
exit codes cannot be trusted; do not re-derive it. Run its check, then
**resolve the layout rather than assuming it**:

```bash
command -v obsidian                       # exit 1 - stop, not fixable from the shell
obsidian vault info=name                  # confirm the right vault
obsidian plugins:enabled | grep -x task-base   # is the plugin there?
```

**When `task-base` is enabled, ask it for the layout instead of deducing
one:**

```bash
obsidian eval code='JSON.stringify(app.plugins.plugins["task-base"].settings)'
```

That returns `basePath`, `taskFolder`, `excludedFolders`, `categories`,
`defaultPriority` and `logHeading` - every value the rest of this skill would
otherwise assume. Strip `eval`'s `=> ` prefix before parsing. Read
`references/plugin.md` now: it is the contract between this skill and the
plugin, and Steps 4 and 6 both hand work to it.

Without the plugin, find the base and check for Python, which the fallback
RRULE evaluator needs:

```bash
command -v uv                # only the Step 4 fallback needs it
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
schema** - a new task should carry the same ones. Never assume a value from
memory or from the user's phrasing.

**A formula is returned only if some view lists it.** The base defines
`days_until_due` and `overdue`, but the plugin-generated `Table` view names
neither, so a default query returns no formula columns at all. `This week`
returns `days_until_due`; nothing returns `overdue`. Where a formula does come
back it is the answer, computed by the vault - do not recompute it from `due`.
`base:views path="<base path>"` lists what a base offers - it takes `path=`
and `file=` even though `obsidian help base:views` shows no options at all -
and `base:query ... view="Today"` queries one by name.

With the plugin installed there is a better survey than the base:
`repository.buckets()` partitions the open set into the same sections as the
sidebar the user is looking at. `references/plugin.md` has the call.

**The base includes done tasks.** Its filter no longer excludes them, so
`base:query` is the full inventory rather than a list of open work. Two
consequences: drop `done: true` rows before ranking anything (Step 6), and
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
obsidian property:set name=done value=false type=checkbox path="<new path>"
obsidian property:set name=priority value=medium path="<new path>"
obsidian property:set name=category value=yard path="<new path>"
obsidian property:set name=created value="<today>" path="<new path>"
obsidian property:set name=asset value="[[Cub Cadet Ultima 54 Mower]]" path="<new path>"
```

`created` is a **bare `YYYY-MM-DD`**, registered vault-wide as a date. It used
to be a wikilink to the daily note; writing one now is a regression that turns
the property back into text. `asset` is optional - a quoted wikilink to the
note for the thing being serviced, which carries `type: asset`. Set it only
when there is one, and leave the key off otherwise.

**Never pass `type=` to `property:set`** - see Gotchas. It is doubly
confusing here, because `type` is also the property that marks a task:
`name=type` is correct, `type=text` is the destructive one.

Ask for `category` and `priority` when the user did not say; leave `due` and
`frequency` empty rather than inventing them. If `base:create` fails, fall back
to `create name="<name>" path="<folder>"` then
`property:set name=type value=task` - the note is only a task once it has
that property.

With the plugin installed, take `categories` and `defaultPriority` from its
settings rather than from this skill's tables, and put the note in its
`taskFolder`. Its **Create task** command is a form the user fills in, so it
is not something to fire from the CLI - offer it when they are at the keyboard
and would rather type into a dialog. Same for **Set asset**, whose type-ahead
over `type: asset` notes beats guessing a wikilink.

Read `references/schema.md` before creating or migrating: it holds the field
contract and the values already in use, so a new task reuses a `category`
instead of coining one.

## Step 3 - Complete a one-time task

Completion is the `done` checkbox. There is no in-flight state; a task is done
or it is not.

**Check `frequency` before writing `done: true`** - it separates the two kinds
of task, and the branch is not recoverable by reading the note afterwards. A
task *with* a rule goes to Step 4 and never gets `done: true`. A task
*without* one is finished for good here, and finishing it removes the note:

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian property:set name=done value=true type=checkbox path="<path>"
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

**`done` is the one property that needs `type=checkbox`** - without the flag
the CLI writes the string `"false"` instead of a boolean, and every filter
that tests it stops working. See Gotchas; the blanket ban on `type=` still
holds for every other property.

**Confirm with the user before the `delete`, naming the note.** It is the one
command in this skill that removes work. Write `done: true` first even
though the note is about to go: the trashed copy is recoverable, and it
should read as finished work rather than as an abandoned draft.

Deleting is right only because the task is one-time. Anything the user may
want later - what was actually done, a measurement, a receipt - belongs in a
note that outlives the task, so offer to move it before deleting rather than
after. The ones already sitting in the base are swept by
`obsidian-task-grooming`, not here.

**The plugin does not do this.** Its **Complete task** command writes
`done: true` and stops - it never deletes. So a task finished in the app stays
in the base and a task finished here does not. That difference is deliberate:
deletion needs a confirmation, and a modal button is not one. Say which
happened when reporting, and if the user expects the plugin's behaviour,
completing without the delete is a fine thing to do on request.

## Step 4 - Complete a recurring task

A recurring task is never left `done`; that is what makes it recur. Marking
one `done` and stopping is still the most likely mistake in this skill, but it
no longer hides: done tasks stay in the base, so a done row carrying a
`frequency` is visible as the anomaly it is. `obsidian-task-grooming` lists
those rows for roll-forward and never deletes them - **`frequency` is what
keeps a task out of the sweep**, which is one more reason never to clear it.

`frequency` holds an RFC 5545 `RRULE`. The policy is **skip the rest of the
period you just did it in**, then take the schedule's next occurrence - so the
anchor is the completion date, *not* the task's current `due`. Mow the lawn on
a Wednesday under `FREQ=WEEKLY;BYDAY=SU` and the answer is the Sunday after
next, because this week's slot is already spent.

**With the plugin installed, let it compute.** Its `recompute-due` command
anchors on `last done`, so writing that first gets exactly what the user's own
**Complete task** button would have produced:

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian open path="<path>"                    # must print: Opened: <path>
obsidian command id=task-base:recompute-due    # prints: Executed: ...
obsidian read path="<path>"                    # the new due, read back
obsidian property:set name=done value=false type=checkbox path="<path>"
obsidian append path="<path>" content='\n- <today> - <detail>\n'
```

Two things this sequence depends on. **`obsidian open` must land on the task**
- every plugin command falls back to a picker modal when the active file is
not a task, and `obsidian command` prints `Executed:` either way, so a dialog
left open in front of the user reads here as success. And **read the new `due`
with `obsidian read`, never `property:read`** - the property cache lags a
plugin write by a moment and will hand back the old value.

Without the plugin, compute it with the evaluator in
`references/recurrence.md`, then write `due` yourself with `property:set`
between the `last done` and `done` writes above. **Never compute it by hand:**
RRULE's `BY*` parts expand or limit depending on the `FREQ` above them, and the
intuitive spelling of "annually on the last day of the month" -
`FREQ=YEARLY;BYMONTHDAY=-1` - silently yields a *monthly* series.

`last done` and `due` are real dates, always. Non-date detail - mileage, a
part number, what was done - goes on the body log line under a `## Service log`
heading, **never** into those two fields. The heading is the plugin's
`logHeading` setting where the plugin exists; read it rather than hardcoding
the default. The body log also keeps the history that `last done` overwrites.

Read `references/recurrence.md` before writing or editing any rule. It holds
the `RRULE` value grammar, the three-case policy with its verified table, the
fallback evaluator, and the expand-versus-limit traps that make hand-computed
dates wrong without erroring.

An **unreadable** `frequency` is a third state, not a one-time task. The
plugin refuses to complete one; so should this skill, since finishing it as
one-time would write `done: true` and then delete a schedule the user meant to
keep. Ask for the rule to be fixed - the plugin's **Edit repeat rule** builder
previews the next three dates, which is the fastest way to fix one.

## Step 5 - Sweeping the base belongs to grooming

Finished one-time tasks stay in the base rather than vanishing, and clearing
them out is `obsidian-task-grooming`'s Step 3: it surveys the whole base, lists
every candidate by name, and deletes on a single confirmation. Hand off to it
rather than sweeping here.

The rule that decides what may go - **`frequency` empty means sweepable,
`frequency` set means never delete, roll it forward instead** - lives there and
nowhere else. Do not re-derive it in this skill; two copies of that guard are
two things that can drift apart, and the failure mode is a deleted recurring
schedule.

Step 3 above is a different thing and stays here: it removes the one task the
user finishes or abandons in front of you, named in the conversation. That is
a single note, not a pass over the base.

## Step 6 - Answer what to work on

**Drop `done: true` rows before ranking.** They sit in the base and they are
not work; scheduling one is the way to get this step wrong. Test the value
properly - `base:query` returns `done` as a string, so `if row['done']:` is
true for an *open* task. See Gotchas.

**With the plugin, read its buckets and keep its order** - that is what makes
the answer match the sidebar the user is looking at. Its sections partition the
open set, so nothing can be due-dated into invisibility, and `later` is defined
as the remainder rather than as a date window.

Its ranking within a section is **`due` ascending, empty `due` last, then
priority high/medium/low, then name.** Due before priority. Follow the same
order when working without the plugin, so the two never disagree:

1. Overdue first - `due` is a date before today
2. Then by `due` ascending, empty `due` last
3. Ties broken by `priority`, high before medium before low, then by name

Any ranking is still this skill's to state out loud; the vault supplies no
sort order. The base's Table view sorts by `done` then `due`, which
front-loads open work but is not a priority ranking.

Without the plugin, query `view="Today"` or `view="This week"` rather than
filtering every row by hand. Both carry a `done != true` clause, so done tasks
do not come back in them. Do not reach for the `overdue` formula: it is
defined in the base but listed by no view, so no query returns it - compare
`due` to today instead.

Say how many tasks were considered, counting open ones only. A count that
drops between runs means a task was completed and swept, not that something
went missing. Recurring tasks with no `due` are waiting on their first
completion - list them separately rather than as overdue.

## Step 7 - Verify, then report

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Created: <path>`, `Set <property>: <value>`, or
   `Moved to trash: <path>`. A line starting with `Error: ` is a failure -
   including `Error: File "..." not found.`, which is what a delete against a
   mistyped path prints in place of doing anything. **`Executed: <id>` from
   `obsidian command` is not a success line** - it says the command was
   dispatched, not that it wrote anything, so a plugin command is verified by
   the note and by nothing else.
2. Re-run the Step 1 `base:query`. Done tasks stay in the base now, so absence
   has one innocent cause and one failure:

   | Absent from `base:query` | Meaning |
   |---|---|
   | You deleted it in Step 3, or grooming swept it | Correct - `obsidian read` on the path confirms it, printing `Error: File "..." not found.` |
   | Anything else | **The note has no `type: task`** - the classic failure |

   The second is invisible from the note alone, which is why the read-back
   goes against the base and not the file. A completed one-time task that is
   still *present* means the delete did not happen - check its output line.

When the plugin did a write, read the note back with `obsidian read` rather
than `property:read`, and check nothing was left waiting for the user -
`obsidian eval code='document.querySelectorAll(".modal-container").length'`
returning anything but `0` means a dialog is open in front of them, which is
worth saying rather than reporting the step as finished.

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
  inline in note bodies, and its own flags happen to be named `done`, `todo`,
  and `status="<char>"` - unrelated to this schema's `done` property despite
  the collision. This skill never uses it: a task here is a note with
  `type: task`, not a `- [ ]` line.
- **The base holds done tasks too.** The filter no longer excludes
  `done: true`, so `base:query` is the full inventory rather than a list of
  open work. Drop done rows before ranking, and never schedule one as if it
  were outstanding. Clearing them out is grooming's sweep, not this skill's.
- **`done` is the one property that must carry `type=checkbox`.** Without the
  flag, `property:set name=done value=false` writes the *string* `"false"`,
  and every filter testing it silently stops working. This is the sole
  exception to the ban below; `done` is task-exclusive, so registering it
  vault-wide is the intent rather than a side effect. Never generalise the
  exception to any other property.
- **`base:query` returns `done` as a string, and `"false"` is truthy.** An
  open task reads back as `'false'`, a completed one as `'true'` - both
  non-empty strings. `if row['done']:` is therefore true for *every* task, and
  code built that way treats the whole base as finished. Test
  `row['done'] in (True, 'true')`. Verified live: the naive test counted 29 of
  29 tasks as done when exactly one was.
- **`frequency` is empty on a one-time task, not missing.** The template
  writes the key with no value, so `frequency:` appears on every task note and
  a test for an absent line matches nothing - a branch built that way sends
  every task down the one-time path. `base:query` returns `null` for an empty
  key and for a genuinely absent one alike, which is why the queried value is
  the one to test.
- **Never seed an empty `frequency` with `property:set value=""`.** That
  writes `frequency: ""`, and an empty string is **not** `null` to Bases, so
  every `frequency != null` filter starts matching one-time tasks and the view
  returns wrong rows with no error. The template's bare `frequency:` key is
  null; let the template write it.
- **A new property is invisible to `base:query` until the base names it.**
  Results are keyed by the view's columns, so a property written to every note
  reads back as absent until it is added to the `.base` file. Verify a new
  field against `obsidian read`, or update the base first.
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
- **`created` is a bare date, not a wikilink** - `2026-08-16`, registered
  vault-wide as `date`. It used to be `"[[2026-08-16]]"`, a backlink to the
  daily note, which made the property *text* and left it unsortable. Writing a
  wikilink now undoes that. One note in the vault still carries the old form,
  written by an earlier version of this skill; normalising it is a safe repair
  to offer.
- **Modal plugin commands cannot be driven from the CLI, and say nothing when
  they are.** `obsidian command` prints `Executed: <id>` whether the command
  did the work or opened a form and walked away. `task-base:recompute-due` is
  the only one that finishes on its own, and only when the active file is
  already a task. `references/plugin.md` has the guard rails.
- **`property:read` can return a stale value straight after a plugin write.**
  Verified live: it handed back the pre-write `2026-06-30` while
  `obsidian read` on the same path already showed `2026-12-31`. Read back
  through `obsidian read` whenever a plugin command did the writing.
- **`obsidian eval` prefixes its result with `=> `**, and prints nothing at
  all when the expression is `undefined` - which is indistinguishable from a
  plugin that is not loaded. Check `plugins:enabled` rather than inferring it
  from empty output.
- **A formula the base defines is returned only if a view lists it.** The
  plugin-generated `Table` view names no formula columns, so `days_until_due`
  and `overdue` reach no default query despite being in the file. `This week`
  returns `days_until_due`; nothing returns `overdue`.
- **Never read or write task state from a Kanban board or a hand-maintained
  table.** They look authoritative and drift from the frontmatter;
  `references/schema.md` measures the drift and explains why the board is
  still a legitimate way to *create* tasks.
