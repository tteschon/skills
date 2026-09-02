# The Task Base plugin

Read this when the vault has the `task-base` community plugin installed. It
is the other writer of these notes, and where it and this skill disagree the
user sees two different answers for the same task.

The plugin owns two things this skill cannot do as well: the **next-due
computation** and the **ranking the user actually looks at**. Both are
reachable from the CLI, so use them rather than recomputing.

## Is it there?

```bash
obsidian plugins:enabled | grep -x task-base
```

Absent - nothing here applies. `SKILL.md` works against the notes directly and
`recurrence.md` has the fallback evaluator.

## Read its settings instead of guessing the layout

```bash
obsidian eval code='JSON.stringify(app.plugins.plugins["task-base"].settings)'
```

```json
{"taskFolder":"tasks","excludedFolders":["Templates"],
 "categories":["home","yard","errands","vehicle","health"],
 "defaultPriority":"low","logHeading":"Service log",
 "basePath":"tasks/task base.base","openViewOnStart":false}
```

Every one of these is a value this skill would otherwise assume:

| Setting | Replaces |
|---|---|
| `basePath` | picking a base out of `obsidian bases` |
| `taskFolder` | guessing where a new note goes |
| `categories` | the observed-values table in `schema.md` |
| `defaultPriority` | asking, when the user did not say |
| `logHeading` | hardcoding `## Service log` |
| `excludedFolders` | the base's `!file.inFolder(...)` clauses |

`eval` prefixes its result with `=> `; strip it before parsing.

## Commands: one is usable headless, the rest are not

```bash
obsidian commands | grep task-base
```

| Command | Headless? |
|---|---|
| `task-base:recompute-due` | **Yes** - writes `due` and returns, when the active file is a task |
| `task-base:create-task` | No - opens a form |
| `task-base:complete-task` | No - opens a confirm modal |
| `task-base:edit-task` | No - opens a form |
| `task-base:edit-frequency` | No - opens the rule builder |
| `task-base:set-asset` | No - opens a picker |
| `task-base:open-base`, `task-base:open-task-view` | Yes, but they only open UI |

**Never fire a modal command from the CLI.** `obsidian command` prints
`Executed: <id>` either way, so a form left open in front of the user reads
here as success. Suggest the command by name and let the user run it - the
rule builder in particular shows a live preview of the next three dates,
which is worth more than anything this skill can print.

The same trap has a second mouth: every task-taking command falls back to a
**picker modal** when the active file is not a task. So
`task-base:recompute-due` is only headless if the `obsidian open` before it
actually landed on a task note. Check that `open` printed `Opened: <path>`
and that the note carries `type: task` before invoking it. If a modal does get
left open:

```bash
obsidian eval code='document.querySelectorAll(".modal-container").length'
```

Non-zero means the user has a dialog waiting; say so rather than continuing.

## Rolling a recurring task forward

`recompute-due` anchors on the note's `last done`, falling back to today. So
write `last done` first and the plugin computes exactly what its own
**Complete task** modal would have:

```bash
obsidian property:set name="last done" value="<today>" path="<path>"
obsidian open path="<path>"                      # must print: Opened: <path>
obsidian command id=task-base:recompute-due      # prints: Executed: ...
obsidian read path="<path>"                      # the new due, read back
obsidian property:set name=done value=false type=checkbox path="<path>"
```

**Read the new `due` with `obsidian read`, not `property:read`.** The property
cache lags a plugin write by a moment: verified live, `property:read` returned
the pre-write `2026-06-30` while `read` on the same path already showed
`2026-12-31`.

The plugin refuses rather than guessing when the rule is unreadable, and does
nothing on a task with no rule. Both cases print `Executed:` and leave `due`
untouched, which is why the read-back is not optional.

## Ranking, and the sections the user sees

The plugin's sidebar partitions the open set. Reading its buckets is how an
answer to "what should I do next" matches the pane the user is looking at:

```bash
obsidian eval code='const b=app.plugins.plugins["task-base"].repository.buckets();
const m=t=>({name:t.name,path:t.file.path,due:t.due,priority:t.priority,
frequency:t.frequency,done:t.done});
JSON.stringify(Object.fromEntries(Object.entries(b).map(([k,v])=>[k,v.map?v.map(m):v])))'
```

| Bucket | Contents |
|---|---|
| `overdue` | open, `due` before today |
| `today` | open, `due` today |
| `thisWeek` | open, `due` within 7 days |
| `needsAttention` | open, recurring, no `due` - awaiting a first completion |
| `later` | **every other open task** - the remainder, not a date window |
| `stalled` | recurring tasks sitting at `done: true` - they stopped recurring |
| `invalidRule` | `frequency` set but unparseable |
| `all` | every task note, done ones included |

`later` being a remainder is load-bearing: a one-time task with no `due` at
all lands there rather than falling through every filter. A hand-rolled
"due beyond this week" query would lose it.

Within a bucket the order is the plugin's `rank`: **`due` ascending, empty
`due` last, then priority high/medium/low, then name.** Due before priority -
`SKILL.md` Step 6 follows the same order for exactly this reason.

`stalled` and `invalidRule` are reports, not work. Hand them to
`obsidian-task-grooming`.

## What the plugin will not do

- **Delete a note.** Its one-time completion writes `done: true` and stops.
  `SKILL.md` Step 3 goes further and trashes the note; that difference is
  deliberate and is stated there.
- **Write `.obsidian/types.json`.** Same rule as this skill's.
- **Touch a Kanban board.**

## When the plugin created the base

`task-base:open-base` creates `<taskFolder>/task base.base` if none exists,
generating the exclusion clauses from `excludedFolders`. That file is what the
live vault now holds - and it has **no `Sweep` view**, which the version in
`base.md` does. Grooming's sweep queue then has to come from a query over the
full base rather than from a saved view. Adding the view back is a `base.md`
edit; the plugin will not re-add it.

Its `Table` view also lists no formula columns, so `days_until_due` and
`overdue` are defined in the file but come back from **no** default query.
`This week` is the one view that returns `days_until_due`.
