---
name: obsidian-task-grooming
description: Reviews the health of an Obsidian note-per-task base and reports what has drifted - one-time tasks with no due date, recurring tasks left in active after a roll-forward already reset their schedule, and finished tasks waiting to be deleted. Use this skill when the user wants a periodic look at the task system as a whole rather than a change to one task - groom my tasks, review my task backlog, audit my tasks, what is stale, what has gone unscheduled, is my task list healthy, why does this task never show up in my Today view. Also use it when the user mentions task hygiene or a stale status. This skill reads and makes non-destructive property corrections only - it never deletes a note. Adding a task, completing one, rolling a recurring chore forward, deleting a finished one, and asking what to work on next all belong to obsidian-tasks; general vault work belongs to obsidian-vault.
compatibility: Requires the obsidian CLI and a vault whose task notes carry a type property of task, collected by a Bases file that does not filter out completed tasks
---

# Obsidian Task Grooming

Review a note-per-task base as a whole and report what has drifted -
unscheduled work, stale statuses, and finished tasks waiting to be deleted.

**This skill never deletes a note.** Removing a finished task belongs to
`obsidian-tasks`, which owns every write that completes or removes work. The
split is deliberate: the guard that stops a recurring task from being deleted
lives there, and it only stays correct while it has exactly one home. Grooming
reports what should go and hands off.

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
`cadence:` as an empty key on every note, so a check for a missing line matches
nothing and reports a clean base no matter how much has drifted. `base:query`
returns `null` for an empty key and a genuinely absent one alike, which is the
only place the two look the same.

Below, "empty" means the queried value is `null` or `""`.

## Step 2 - Check A, unscheduled one-time tasks

**Rule** - `status` is not `done`, `due` is empty, and `cadence` is empty.

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

## Step 3 - Check B, stale active status

**Rule** - `status` is `active`, `cadence` is set, `due` is in the future, and
`last done` is not empty.

A correct roll-forward ends at `status: backlog`; that is the last property
write in `obsidian-tasks` Step 4. So this combination cannot be produced by the
documented lifecycle. It means the roll-forward ran and recomputed `due`, and
only the status reset failed to stick.

Confirm the arithmetic before calling it stale. A task whose `due` sits exactly
one cadence interval past its `last done` was rolled forward, and the status is
the only thing wrong with it:

```
Crosstrek Oil Change    cadence: every 6 months
  last done 2026-06-19    due 2026-12-19    <- exactly 6 months on, rolled forward
```

Offer the reset, taking one confirmation for the batch:

```bash
obsidian property:set name=status value=backlog path="<path>"
```

**Ask rather than assume.** `active` is also what a genuinely in-flight task
looks like, and nothing in the data separates "left behind by a roll-forward"
from "being worked on right now". Present the finding and let the user decide.

Touch `status` and nothing else. `due` and `last done` are already correct on
these rows - rewriting them re-rolls a schedule that was right.

## Step 4 - Report what needs deleting; delete nothing

| Row | Meaning | Do |
|---|---|---|
| `done`, `cadence` empty | A finished one-time task | Report the count. `obsidian-tasks` Step 5 deletes them |
| `done`, `cadence` set | A recurring task that has silently stopped recurring | Report as an anomaly for `obsidian-tasks` Step 4 roll-forward |

The second is the one worth naming out loud. Nothing else in the vault will
ever flag it: it sits in the base looking finished, its cadence intact, and it
will simply never come due again.

## Step 5 - Verify, then report

The CLI exits 0 on failure, so check the output text and then the data:

1. Each write prints `Set <property>: <value>`. A line starting with `Error: `
   is a failure, whatever the exit code said.
2. Re-run the Step 1 query. Confirm every accepted change took, and that the
   row count is unchanged - grooming never adds or removes a task, so a count
   that moved means something happened that this skill did not intend.

Report it as a review, not as a changelog: how many tasks were surveyed, what
each check found, what the user accepted, and what was left alone on purpose.
A check that found nothing still earns a line - "no recurring task is stuck in
`done`" is a result, and silence reads as an unrun check.

## Gotchas

- **`cadence` is empty on a one-time task, not missing.** The template writes
  the key on every note, so `cadence:` appears everywhere and a test for an
  absent line matches nothing - a grooming run built that way finds zero
  problems and reports success. Test the value from `base:query`.
- **Never pass `type=` to `property:set`.** It rewrites the property's type
  vault-wide in `.obsidian/types.json` rather than on the note being edited.
  `type=text` on a date field silently breaks date sorting and every formula
  for every task. Omitting `type=` writes the same value safely.
- **Paths are case-sensitive to the CLI but not to the macOS disk.** Take each
  path from the `path` key of `base:query` verbatim; a retyped `Tasks/` for
  `tasks/` fails with `Base file not found` or `Error: File "..." not found.`
- **This skill has no reason to call `obsidian delete`.** If a task needs
  removing, hand off to `obsidian-tasks`. Two skills that can both delete are
  two places for the `cadence` guard to drift.
- **Never read task state from the Kanban board.** It does not write back to
  frontmatter, so its columns disagree with `status` by a known and growing
  margin. `obsidian-tasks/references/schema.md` measures the drift.
