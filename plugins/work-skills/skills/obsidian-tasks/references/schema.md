# The task note contract

Read this before creating a task, migrating existing ones, or interpreting a
field whose value looks wrong. The field types and the values already in use
are not guessable from the field names, and two of them behave differently
from how they are declared.

## The fields

One note per task, in the task repo folder, with this frontmatter. The shape
comes from the user's template, which is the only thing that should ever
write `created`.

| Field | Declared type | Reality |
|---|---|---|
| `status` | text | Canonical set is `backlog`, `active`, `done` |
| `due` | **date** | Holds mileage strings on vehicle tasks - see below |
| `created` | unregistered | A wikilink, `"[[YYYY-MM-DD]]"`, not a date |
| `priority` | text | `low`, `medium`, `high` |
| `category` | unregistered | Free text, but reuse an existing value |
| `last done` | **date** | Also holds mileage strings |
| `cadence` | text | Free text, parsed by Step 4 of `SKILL.md` |

"Declared type" is what `.obsidian/types.json` registers. Unregistered
fields infer as text and are safe to write. The two registered as `date` are
where the trouble is.

Confirm the live registry rather than trusting this table, since a stray
write can change it:

```bash
obsidian property:read name=<field> path="<a task note>"
```

## The date-versus-mileage duality

`due` and `last done` are registered `date`, but vehicle tasks store text:

```yaml
# Tasks/task repo/Crosstrek Oil Change.md
due: "~25,731 mi"
last done: "2026-06-19 (22,731 mi)"
cadence: every 3,000 mi
```

This is deliberate and stays. It means:

- **Never call date arithmetic on a raw `due` or `last done`.** Parse, and
  branch on failure. A mileage string either raises or sorts as garbage.
- **Never "fix" these values into dates.** The mileage is the real interval;
  a date would be a guess.
- **Never write them with `property:set ... type=`.** Passing `type=text` to
  make a mileage string fit rewrites `due` to text for the whole vault and
  breaks date sorting on every other task. Omit `type=` - the value writes
  correctly and the registry is left alone.

Vehicle tasks are therefore neither overdue nor current until someone reads
an odometer. Report them separately rather than ranking them.

## Values already in use

Reuse these rather than coining new ones. A new `category` is fine when the
task genuinely does not fit, but check first - `obsidian base:query` returns
every value in one call.

| Field | Observed values |
|---|---|
| `status` | `backlog` dominates; `active` for in-flight; `done` when finished and not recurring |
| `priority` | `low`, `medium`, `high` - `high` is rare and worth respecting |
| `category` | `yard`, `home`, `errands`, `vehicle`, `health` |
| `cadence` | `weekly`, `every 6 months`, `every 3,000 mi` |

Some notes carry no `category` at all. That is a gap to ask about, not a
value to invent.

## The three parallel systems

The vault contains three views of the same tasks. Only the first is written.

| System | Role |
|---|---|
| Task notes in the task repo | **Source of truth.** The only thing this skill writes |
| A Kanban board note | A *creation and viewing* surface, not a mirror |
| A recurring-tasks table note | Hand-maintained view, stale |

The board deserves a precise description, because "stale duplicate"
understates it. Its `kanban:settings` block sets `new-note-template` and
`new-note-folder` to the same template and folder used here, so dragging a
new card onto the board really does create a proper task note. What it does
not do is write back - moving a card between columns changes the card's
position and nothing else, so `status` in the frontmatter never learns about
it.

That is the mechanism behind the drift. At a survey of 34 tasks, 7 of the 33
appearing in both disagreed - three the frontmatter called `active` sat in
the board's Backlog column, and three the board had archived as done were
still `backlog` in frontmatter. One note had no card, one card had no note,
and several archived cards are plain text that never became notes at all.

So the board is a legitimate way for the user to *add* tasks, and an
unreliable way to read their state. Write frontmatter only. An agent editing
a Kanban plugin's markdown can also corrupt card formatting or drop the
settings block, which would break the creation flow the user depends on.

When asked to sync or update the board, say that frontmatter is the source
of truth, that the legacy views are stale by a known amount, and offer to
report the drift instead. Reconciling them is a deliberate one-time job the
user should decide on - not a side effect of completing a task.
