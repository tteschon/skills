---
name: obsidian-tasks
description: Creates and manages task notes in an Obsidian vault through the Task Base plugin's API - one note per task, identified by a type property set to task and collected by a Bases file, carrying a done checkbox, due, priority, category, an optional asset link, and an RRULE repeat rule. Use this skill when the user wants to add a task, mark one done, change its priority or due date, roll a recurring chore forward, or ask what to work on next - what are my top tasks, what is overdue, add mowing the lawn to my tasks, I just changed the oil. Also use it when the user mentions their task base, the Task Base plugin or its task pane, a task note's done state, asset, or repeat rule, or a backlog of home or yard chores. Do not use it for checkbox tasks inline in note bodies; do not use it to review the whole base or sweep out finished tasks - groom my tasks, what is stale - which is obsidian-task-grooming; and not for general vault reading, searching, or note editing, which is obsidian-vault.
compatibility: Requires the obsidian CLI, a running Obsidian, and the task-base plugin (0.4.0+) enabled in the target vault
---

# Obsidian Tasks

Run a note-per-task system in an Obsidian vault - create tasks, complete them,
roll recurring chores forward, and answer what to work on next.

**The plugin owns the domain; this skill owns the judgment.** Field names,
categories, the ranking, and how a completion computes the next due date are
all answered by `contract()` at runtime, so nothing here can go stale against
the vault. What is left is the part a program cannot supply: what to confirm
before a destructive write, what to ask when the user was vague, and how to
report what actually happened.

## Before you start

`obsidian-vault` covers the CLI itself - preflight, vault targeting, and why
exit codes cannot be trusted. Run its check, then confirm the plugin:

```bash
command -v obsidian                             # exit 1 - stop, not fixable from the shell
obsidian vault info=name                        # confirm the right vault
obsidian plugins:enabled | grep -x task-base    # no match - stop, see below
```

**No `task-base` means stop and say so.** Everything below routes through it.
Editing the frontmatter by hand instead would write a second, unverified
implementation of the plugin's rules into the user's notes - which is the
failure this skill was rewritten to prevent. Tell the user the plugin is not
enabled in this vault and let them decide.

Then define the one call form used everywhere:

```bash
tb() { obsidian eval code="(async()=>JSON.stringify(await app.plugins.plugins['task-base'].api.$1))()"; }
tb 'contract()'
```

**The `await` is not optional, even for calls that look synchronous.**
`JSON.stringify` on a pending promise yields `{}`, so a write done without it
reports success having returned nothing. See Gotchas.

Every call returns `{"ok":true,"value":...}` or `{"ok":false,"error":"..."}`.
**Read `ok` before anything else** - a refusal is a normal return, not an
exception, and the CLI exits 0 regardless.

## Step 1 - Ask the vault what a task is

```bash
tb 'contract()'
```

This is the schema: `fields` in template order, the `identity` property, the
live `categories` and `priorities`, `taskFolder`, `logHeading`, `baseFilters`,
plus the `ranking` and `recurrencePolicy` in words. **Use these values rather
than any list written down here or in a reference** - that is the whole point
of the redesign. Check `apiVersion` is `1`; a higher number means this skill
may not know a call's current shape, which is worth saying out loud.

`neverWritten` names the fields the plugin refuses to touch and why. Treat it
as binding on this skill too.

## Step 2 - Add a task

```bash
tb 'create({name:"Mow the lawn",category:"yard",priority:"medium",due:"2026-09-06",frequency:"FREQ=WEEKLY;BYDAY=SU",asset:"Cub Cadet Ultima 54 Mower"})'
```

Only `name` is required; everything else falls back to the plugin's settings.
`asset` takes a bare name or a wikilink and is stored as a wikilink.

**Ask when the user was vague; never invent.** Take `category` from
`contract().categories` rather than coining one. Leave `due` and `frequency`
out rather than guessing - a task with no due date is a real state the base has
a view for, and an invented date is indistinguishable from one the user chose.

The return value is the note as stored, read back after the write. Quote it;
do not report what you sent.

When the user is at the keyboard and would rather fill in a form, the plugin's
**Create task** command is a better experience than a guessed argument - and
its asset field type-aheads over real notes. Suggest it by name; do not fire it
from the CLI (see Gotchas).

## Step 3 - Complete a task

**Preview before writing when the outcome is not obvious:**

```bash
tb 'previewCompletion("tasks/Mow Lawn.md")'   # -> kind, due, reason. Writes nothing
tb 'complete("tasks/Mow Lawn.md",{detail:"22,731 mi"})'
```

`kind` is the branch, and the three outcomes are different in kind, not degree:

| `kind` | What happened | What to say |
|---|---|---|
| `recurring` | `last done` set, `due` rolled forward, `done` back to false | The new due date, and that it recurs |
| `one-time` | `last done` set, `done` true. **The note stays** | It is finished and still in the base |
| refusal (`ok:false`) | The repeat rule cannot be read. Nothing was written | Ask for the rule to be fixed - see Step 5 |

The refusal is the one worth understanding. An unreadable rule is a third
state, not a one-time task: completing it as one would set `done: true` and
retire a schedule the user meant to keep. The plugin will not guess, and
neither should this skill.

`detail` - mileage, a part number, what was actually done - goes on a dated
line under the log heading, **never** into `due` or `last done`, which hold
only the latest completion. Pass it to `complete`; do not append it separately.

### Deleting a finished task

`complete` never deletes, on purpose. When the user wants the note gone as
well - "I'm done with this, get rid of it" - complete it first, then:

```bash
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

**Confirm first, naming the note.** This is the only command in this skill that
removes work. Complete it before deleting even though the note is about to go:
the trashed copy is recoverable and should read as finished work rather than an
abandoned draft. If the body holds anything worth keeping - a service log, a
measurement, a receipt - offer to move it somewhere that outlives the task
*before* deleting, not after.

This is a deliberate divergence: the plugin's **Complete task** button leaves
the note. Say which of the two happened when reporting. Clearing out the
finished tasks already sitting in the base is a different job and belongs to
`obsidian-task-grooming`.

## Step 4 - Change a task

```bash
tb 'update("tasks/Mow Lawn.md",{due:"2026-09-13",priority:"high"})'
tb 'update("tasks/Mow Lawn.md",{asset:null})'     # null clears; never pass ""
```

`update` takes `due`, `priority`, `category`, `frequency`, `asset`, `lastDone`
and `done`. It will not touch `type` or `created`; `contract().neverWritten`
says why.

Setting `done` directly is almost always wrong - it skips the branch in Step 3
and can leave a recurring task retired. Use `complete`.

## Step 5 - Repeat rules

```bash
tb 'ruleState("FREQ=WEEKLY;BYDAY=SU")'                    # none | valid | invalid
tb 'describeRule("FREQ=MONTHLY;INTERVAL=6;BYMONTHDAY=-1")'
tb 'upcoming("FREQ=MONTHLY;BYMONTHDAY=-1","2026-09-02",3)'
tb 'nextDue("FREQ=WEEKLY;BYDAY=SU","2026-09-02")'
```

All four are pure - they read no notes and write nothing, so they are safe to
use while explaining a rule to the user.

**Never compute a date yourself.** RFC 5545's `BY*` parts expand or limit
depending on the `FREQ` above them, and the intuitive spelling of "annually on
the last day of the month" - `FREQ=YEARLY;BYMONTHDAY=-1` - silently yields a
*monthly* series. `references/recurrence.md` has the grammar and the traps that
make a hand-written rule wrong without erroring.

For a rule that is at all unusual, the plugin's **Edit repeat rule** builder
previews the next three dates before saving. Point the user there rather than
composing a string for them.

## Step 6 - Answer what to work on

```bash
tb 'buckets()'
```

The sections are the plugin's own, so the answer matches the pane the user is
looking at: `overdue`, `today`, `thisWeek`, `needsAttention`, `later`, plus
`stalled`, `invalidRule` and `all`.

- **`later` is the remainder, not a date window.** Everything open that the
  other sections did not catch lands there, so no open task can be missing.
- **`needsAttention` is a queue, not overdue work** - recurring tasks awaiting
  a first completion. List them separately and say why.
- **`stalled` and `invalidRule` are reports, not work.** A recurring task
  sitting at `done: true` has silently stopped recurring; nothing else in the
  vault flags it. Hand both to `obsidian-task-grooming`.
- **`all` includes finished tasks.** Never schedule one as if it were open.

Order within a section is the plugin's, and `contract().ranking` states it.
Say what the rule was rather than implying the vault supplied a priority order
it does not have. Say how many tasks were considered, counting open ones only.

## Step 7 - Verify, then report

1. **Check `ok` on every call.** `false` means nothing was written and `error`
   says why. The CLI exits 0 either way, and an empty `{}` means the `await`
   was missing - not that the call returned nothing.
2. **Quote the returned task, not what you sent.** Every write re-reads the
   note through the metadata cache before returning, so the value is what the
   vault stored - including a date field that rejected what was written to it.
3. **A `path` in a result is exact.** Reuse it verbatim for the next call
   rather than retyping it.

Then give the note path, the fields that changed, and their new values. For a
roll-forward, give the new `due` and say it came from the plugin's policy. For
a deletion, name the note and say it is recoverable from the vault trash. If a
call returned `ok:false`, say plainly what did not happen.

## Gotchas

- **The `await` in the `tb` helper is load-bearing.** Without it,
  `JSON.stringify` runs on a pending promise and prints `{}` - a write that
  happened, reported as a call that returned nothing. Verified live: `create`
  printed `{}` while the note appeared in the vault.
- **Never fire a plugin command from the CLI.** `obsidian command` prints
  `Executed: <id>` whether the command did the work or opened a form and walked
  away, and every task-taking command falls back to a picker modal when the
  active file is not a task. Suggest commands by name; drive the API instead.
  `obsidian eval code='document.querySelectorAll(".modal-container").length'`
  returning anything but `0` means a dialog is open in front of the user.
- **`obsidian eval` prefixes its result with `=> `**, and prints nothing at all
  when the expression is `undefined` - indistinguishable from a plugin that is
  not loaded. Check `plugins:enabled` rather than inferring it from silence.
- **Do not read task state through `base:query`.** It returns `done` as the
  *string* `"false"`, which is truthy - a check built on it once counted 29 of
  29 tasks as done when exactly one was. It also drops any formula no view
  lists. `tasks()` and `buckets()` return real booleans and nulls.
- **Do not write task fields with `property:set`.** It cannot write a boolean
  without `type=checkbox`, and `type=` rewrites a property's type vault-wide
  rather than on the note - flipping `due` from date to text for every note and
  silently breaking date sorting everywhere. `update` and `complete` write
  through the plugin, which does neither.
- **Clear a field with `null`, never `""`.** An empty string is not null to
  Bases, so a `frequency != null` filter starts matching one-time tasks and
  views return wrong rows with no error.
- **`obsidian delete` trashes by default; never pass `permanent`.** Nothing
  here needs it, and the trashed copy is what makes the confirmation safe.
- **`obsidian tasks` is a different system.** It lists checkbox tasks inline in
  note bodies, and its flags are coincidentally named `done` and `status`. A
  task here is a note with `type: task`, never a `- [ ]` line.
- **Never read or write task state from a Kanban board.** It looks
  authoritative and does not write back to frontmatter;
  `references/schema.md` measures the drift.
