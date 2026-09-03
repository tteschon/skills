---
name: obsidian-task-grooming
description: Reviews the health of an Obsidian note-per-task base and reports what has drifted - one-time tasks with no due date, recurring tasks that have silently stopped recurring, and finished one-time tasks waiting to be swept out. Use this skill when the user wants a periodic look at the task system as a whole rather than a change to one task - groom my tasks, review my task backlog, audit my tasks, what is stale, what has gone unscheduled, is my task list healthy, why does this task never show up in my Today view, clear out my finished tasks, sweep the done ones. Also use it when the user mentions task hygiene. This skill owns the sweep - it deletes finished one-time tasks to the vault trash, naming every note and taking a confirmation first. Adding a task, completing one, rolling a recurring chore forward, and asking what to work on next all belong to obsidian-tasks; general vault work belongs to obsidian-vault.
compatibility: Requires the obsidian CLI and a vault whose task notes carry a type property of task, collected by a Bases file that does not filter out completed tasks
---

# Obsidian Task Grooming

Review a note-per-task base as a whole and report what has drifted -
unscheduled work, recurring chores that have stopped recurring, and finished
tasks waiting to be swept out.

**This skill owns the sweep.** Deleting a finished one-time task happens here
and nowhere else, which is what keeps the guard in Step 3 - the one that stops
a recurring task from being deleted - in exactly one place. `obsidian-tasks`
still deletes the single task the user abandons mid-conversation (its Step 3),
but it does not sweep the base; that is this skill's job.

## Before you start

`obsidian-vault` covers the CLI itself - preflight, vault targeting, and why
exit codes cannot be trusted. `obsidian-tasks` covers resolving the task base,
under "Before you start". Run both; do not re-derive either.

```bash
command -v obsidian          # exit 1 - stop, not fixable from the shell
obsidian vault info=name     # confirm the right vault
obsidian bases               # find the task base
```

Grooming is a review, not a repair queue. Report everything; change only what
the user accepts, and leave the rest alone rather than tidying by default.

## Step 1 - Survey once

One query feeds every check. Never walk the notes one at a time:

```bash
obsidian base:query path="<base path>" format=json
```

**Test the values this returns, never the note text.** The task template writes
`frequency:` as an empty key on every note, so a check for a missing line matches
nothing and reports a clean base no matter how much has drifted. `base:query`
returns `null` for an empty key and a genuinely absent one alike, which is the
only place the two look the same.

Below, "empty" means the queried value is `null` or `""`.

## Step 2 - Check A, unscheduled one-time tasks

**Rule** - `done` is not true, `due` is empty, and `frequency` is empty.

These are invisible to the schedule, not merely unprioritised. The base's
`Today` and `This week` views both filter on `due != null`, so a task with no
due date appears in neither, and no amount of waiting will surface it.

Report them, then offer three outcomes. Never invent a due date:

| The user says | Do |
|---|---|
| A date, or a month | `obsidian property:set name=due value="<date>" path="<path>"` |
| It is a someday item | Leave it, and say plainly that it stays off every dated view |
| It is no longer wanted | Hand off to `obsidian-tasks` Step 3, which completes and deletes it |

A **recurring** task with an empty `due` is a different thing and not a defect
- it is waiting on its first completion, which is exactly what the base's
`Needs attention` view collects. List those separately and say why.

## Step 3 - Check B, sweep finished one-time tasks

Finished tasks stay in the base rather than vanishing - that is the only
reason they can be found and cleared at all.

| Row | Meaning | Do |
|---|---|---|
| `done: true`, `frequency` empty | A finished one-time task | Sweep it - delete after confirmation |
| `done: true`, `frequency` set | A recurring task that has silently stopped recurring | **Never delete.** Report for `obsidian-tasks` Step 4 roll-forward |

**`frequency` is what keeps a task out of the sweep.** A done row carrying a
rule is a recurring chore that was marked finished and never rolled
forward; deleting it destroys the schedule instead of repairing it. This guard
lives here and only here - never re-implement it elsewhere. It is also the
finding worth naming out loud, because nothing else in the vault will ever
flag it: the row sits in the base looking finished, its rule intact, and it
will simply never come due again.

When `base:views` lists a `Sweep` view, `base:query ... view="Sweep"` returns
exactly the deletable rows and no others. A base without one is not a problem;
filter the Step 1 rows on the two conditions instead.

**List every candidate by name and take one confirmation for the batch.**
Grooming is a review, so the sweep is offered when candidates turn up, never
run unasked. Then delete them one path at a time:

```bash
obsidian delete path="<path>"        # prints: Moved to trash: <path>
```

Use the `path` value from `base:query` verbatim rather than retyping it - a
mistyped path prints `Error: File "..." not found.` instead of deleting.

Most one-time tasks are frontmatter and nothing else, so the note carries no
history worth keeping. When a candidate does have a body, say so while listing
it and let the user decide - a service log, a measurement, or a receipt is the
kind of thing that should outlive the task, and it should be moved somewhere
that survives before the note goes.

## Step 4 - Verify, then report

The CLI exits 0 on failure, so check the output text and then the data:

1. Each command prints `Set <property>: <value>` or `Moved to trash: <path>`.
   A line starting with `Error: ` is a failure, whatever the exit code said -
   including `Error: File "..." not found.`, which is what a delete against a
   mistyped path prints in place of doing anything.
2. Re-run the Step 1 query. Confirm every accepted change took, and that the
   row count dropped by exactly the number of notes swept - no more, and never
   for a task nobody agreed to remove. A count that moved by any other amount
   means something happened that this skill did not intend.

Report it as a review, not as a changelog: how many tasks were surveyed, what
each check found, what the user accepted, and what was left alone on purpose.
Name every note swept and say it is recoverable from the vault trash. A check
that found nothing still earns a line - "no recurring task is stuck in `done`"
is a result, and silence reads as an unrun check.

## Gotchas

- **`frequency` is empty on a one-time task, not missing.** The template
  writes the key on every note, so `frequency:` appears everywhere and a test for an
  absent line matches nothing - a grooming run built that way finds zero
  problems and reports success. Test the value from `base:query`.
- **Never pass `type=` to `property:set`.** It rewrites the property's type
  vault-wide in `.obsidian/types.json` rather than on the note being edited.
  `type=text` on a date field silently breaks date sorting and every formula
  for every task. Omitting `type=` writes the same value safely.
- **Paths are case-sensitive to the CLI but not to the macOS disk.** Take each
  path from the `path` key of `base:query` verbatim; a retyped `Tasks/` for
  `tasks/` fails with `Base file not found` or `Error: File "..." not found.`
- **`obsidian delete` trashes by default; never pass `permanent`.** Plain
  `delete` prints `Moved to trash: <path>` and the note stays recoverable from
  the vault trash, which is what makes the sweep safe to confirm in a batch.
- **An empty `frequency` and `frequency: ""` are different to Bases.** A bare
  key is `null`; an empty string is not, so a `frequency != null` filter
  matches one-time tasks and a view built on it returns wrong rows silently.
  If a sweep candidate list looks too short, check for `""` in the notes.
- **Sweep only on the queried `frequency`, never on the note text.** A recurring
  task read the wrong way looks one-time, and the sweep deletes the schedule.
  This is the one place in the skill where a bad read destroys work.
- **`base:query` returns `done` as a *string*, and `"false"` is truthy.**
  A completed task reads back as `'true'`, an open one as `'false'` - both
  non-empty strings. Testing `if row['done']:` marks **every** task done, so a
  sweep built that way proposes deleting the entire base. Test
  `row['done'] in (True, 'true')`. Verified against the live vault: the naive
  test counted 29 of 29 tasks as done when only one was.
- **Never read task state from the Kanban board.** It does not write back to
  frontmatter, so its columns disagree with `done` by a known and growing
  margin. `obsidian-tasks/references/schema.md` measures the drift.
