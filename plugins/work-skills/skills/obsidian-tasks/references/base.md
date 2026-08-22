# Authoring the task base

Read this when there is no task base and one must be created, or when the
base's filters, formulas, or views need changing. Day-to-day task work never
touches this file - `SKILL.md` covers that.

Everything here is verified working against Obsidian 1.13.x.

## The bootstrap base

Create it at `tasks/task base.base`, after confirming with the user:

```yaml
filters:
  and:
    - type == "task"
    - '!file.inFolder("Templates")'
    - 'status != "done"'
formulas:
  days_until_due: 'if(due, (due - today()).days.round(0), "")'
  overdue: 'if(due, due < today(), false)'
views:
  - type: table
    name: Table
    order: [file.name, category, cadence, due, last done, priority, status]
  - type: table
    name: Today
    filters:
      and:
        - 'due != null'
        - 'due <= today()'
    order: [file.name, category, due, priority, status]
  - type: table
    name: This week
    filters:
      and:
        - 'due != null'
        - 'due <= today() + "7d"'
    order: [file.name, category, due, formula.days_until_due, priority]
  - type: table
    name: Needs attention
    filters:
      and:
        - 'cadence != null'
        - 'due == null'
    order: [file.name, cadence, last done, priority]
```

Three filter clauses, each load-bearing:

- `type == "task"` is what makes a note a task.
- `!file.inFolder("Templates")` is not optional. The task template carries
  `type: task` so template-made notes are real tasks, and without this clause
  the template lists itself as one. The same trap applies to any other note
  that happens to use the property.
- `status != "done"` is what makes a completed ad-hoc task leave the base.

The formulas do the date arithmetic once, in the vault, so every run reads
the same numbers instead of recomputing them. The views answer the daily and
weekly questions directly. `Needs attention` is the data-quality queue:
recurring tasks with no due date because they have never been completed.

## Writing the file

```bash
obsidian create path="tasks/task base.base" content="..."
```

Pass newlines as literal `\n`. `create` makes missing parent folders on the
way, so one call builds the whole structure, and the base is queryable
immediately - no reload.

## Gotchas

These fire only while authoring a base. The ones that bite during ordinary
task work are in `SKILL.md`.

- **`obsidian create` needs the `overwrite` flag to replace a file.** Without
  it, pointed at an existing path, it writes `<name> 1.base` alongside the
  original and reports success - and a query against the original path then
  returns the old content, which reads as an edit that did not take. The
  `Created:` line names the path it actually wrote; `Overwrote:` is what a
  successful replace prints. `obsidian-vault` covers `overwrite` and the rule
  to confirm before using it, since it replaces the whole file.
- **A file written to the vault from the shell is not visible to the CLI
  immediately.** `obsidian read` serves the app's cached copy and can return
  pre-edit content for a moment after an external write, while `cat` on the
  same path shows the new bytes. When a read looks stale, confirm against the
  filesystem before concluding the write failed.
- **Date subtraction yields a Duration, and `.days` is still not an integer.**
  Access `.days` before any number function - `.round()` on a raw Duration
  fails. Then round it: daylight saving makes a span across a DST boundary
  120 days *and one hour*, so `(due - today()).days` returns
  `120.04166666666667`. `(due - today()).days.round(0)` returns `120`.
- **A formula over an empty property errors on every row that lacks it.**
  Guard with `if()`: `'if(due, (due - today()).days.round(0), "")'`.
- **A `formula.X` in a view's `order:` with no matching `formulas:` entry
  fails silently** - the column simply does not appear, with no error to
  explain it.
- **Test formulas and filters on a scratch base, never the live one.**
  Create it, query it, delete it. A malformed formula is invisible until a
  query returns `Error: ...` in the column where a value should be.
