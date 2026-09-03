# What the contract does not tell you

`contract()` returns the field list, the categories, the priorities and the
folders. Read it for those - this file is only for what a call cannot return:
why some of those fields are fragile, and which of the vault's other views of
the same tasks are lying.

## `type` decides membership, not the folder

A note is a task because it carries `type: task`. Folder is irrelevant - the
base collects matching notes from anywhere, and a note sitting in the task
folder without the property is invisible to every query.

`type` is a **vault-wide namespace**, not a task-only field. Values seen
alongside it include `asset`, `recipe`, `story` and `essay`, each backing its
own base. Two consequences:

- Do not repurpose `type` on a task note.
- Adding `type: task` to a note anywhere - including a template - puts it in
  the base. That is why the base carries a `!file.inFolder("Templates")` clause
  and why the plugin has an **Excluded folders** setting; without them, the
  task template lists itself as a task and the **Complete task** picker offers
  it.

`asset` follows the same rule one namespace over: an asset is a note carrying
`type: asset`. A name with no matching note is accepted rather than rejected -
capturing a chore for something not yet inventoried is normal - so a dangling
asset link is a gap to mention, not a bug to fix.

## Dates are dates, and breaking that is silent

`due`, `last done` and `created` are registered as `date` in the vault's
property registry. That was not always true, and the failure mode is what makes
it worth protecting: a comparison like `due < today()` against a text value
returns **`false`** rather than raising. The task is never flagged overdue, no
view reports it, and nothing errors.

Vehicle tasks once stored `~25,731 mi` and `2026-06-19 (22,731 mi)` in those
fields. The rules that keep it from happening again:

- **Non-date detail goes in the body log**, on a dated line under the log
  heading - mileage, part numbers, what was actually done. Pass it as
  `complete`'s `detail`. `last done` is overwritten every cycle; the log is the
  history.
- **Usage-based intervals are approximated as time.** The oil changes are
  `every 6 months` rather than `every 3,000 mi`, because a date is schedulable
  and a mileage string is not. The odometer reading still gets recorded, on the
  log line.
- **Never write these fields with the CLI's `property:set`.** Passing `type=`
  to make a non-date value fit rewrites the property's type for the whole vault.

The API re-reads a note after writing it, so a value the registry rejected
comes back as the old one rather than as the value you sent. That is the check;
compare what you asked for against what came back.

## `created` is a bare date, and used to be a wikilink

`created` once held `"[[2026-08-31]]"`, a backlink to the daily note - which
made the property **text**, so it could not be sorted, compared, or used in a
formula. It is now a bare `YYYY-MM-DD`.

Writing a wikilink into it now is a regression, not a backlink. One note in the
vault still holds the old form, written by an earlier version of this skill;
normalising it is a safe repair to offer when it comes up.

The registry is vault-wide, not per-note-type, which is what made the change
expensive: `created` sat on 259 notes in three incompatible formats and all of
them had to be normalised together. Daily notes lost their time component in
the process. Do not reopen that decision casually - and note that the plugin
lists `created` under `contract().neverWritten` for the same reason.

## The three parallel systems

The vault holds three views of the same tasks. Only the first is written.

| System | Role |
|---|---|
| Notes carrying `type: task` | **Source of truth.** The only thing this skill writes |
| A Kanban board note | A *creation and viewing* surface, not a mirror |
| A recurring-tasks table note | Hand-maintained view, stale |

The board deserves a precise description, because "stale duplicate"
understates it. Two things are true and neither is obvious.

**Its cards are not task notes.** `🗃 Kanban Cards/` holds 26 notes and **none
carry `type: task`**, so not one is in the base. They run a different schema
altogether - `type: story`, `domain`, `assignee`, `size`, `opened` - and they
are not uniformly tasks either: they range from real work ("change internet",
on hold since 2023) through a camping packing list to one whose entire body is
`test`.

**It does not write back.** Moving a card between columns changes the card's
position and nothing else, so the frontmatter never learns about it. At an
earlier survey of 34 tasks, 7 of the 33 appearing in both disagreed. The
property has since become the `done` checkbox; the board still does not write
to it.

So the board is a place the user thinks about tasks, and an unreliable way to
read their state. Write frontmatter only. An agent editing a Kanban plugin's
markdown can also corrupt card formatting or drop the settings block, breaking
a flow the user depends on.

When asked to sync or update the board, say that frontmatter is the source of
truth, that the legacy views are stale by a known amount, and offer to report
the drift instead. Reconciling them - and deciding which of the 26 orphan cards
are real tasks - is a deliberate one-time job the user should decide on, not a
side effect of completing a task.
