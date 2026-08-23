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
formulas:
  days_until_due: 'if(due, (due - today()).days.round(0), "")'
  overdue: 'if(due, due < today(), false)'
views:
  - type: table
    name: Table
    order: [file.name, category, frequency, due, last done, priority, done]
    sort:
      - {property: done, direction: ASC}
      - {property: due, direction: ASC}
  - type: table
    name: Today
    filters:
      and:
        - 'done != true'
        - 'due != null'
        - 'due <= today()'
    order: [file.name, category, due, priority]
  - type: table
    name: This week
    filters:
      and:
        - 'done != true'
        - 'due != null'
        - 'due <= today() + "7d"'
    order: [file.name, category, due, formula.days_until_due, priority]
  - type: table
    name: Needs attention
    filters:
      and:
        - 'done != true'
        - 'frequency != null'
        - 'due == null'
    order: [file.name, frequency, last done, priority]
  - type: table
    name: Sweep
    filters:
      and:
        - 'done == true'
        - 'frequency == null'
    order: [file.name, category, last done, created]
```

Two filter clauses, both load-bearing:

- `type == "task"` is what makes a note a task.
- `!file.inFolder("Templates")` is not optional. The task template carries
  `type: task` so template-made notes are real tasks, and without this clause
  the template lists itself as one. The same trap applies to any other note
  that happens to use the property.

**There is deliberately no `done` clause on the base's own filter.** An
earlier version filtered `status != "done"`, which dropped a completed
one-time task out of the base
the moment it was finished - tidy to look at, but it also put the note beyond
the reach of `base:query`, so nothing could ever find it again to clean it up.
Keeping done tasks in the base is what makes the `obsidian-task-grooming`
sweep possible.

The formulas do the date arithmetic once, in the vault, so every run reads
the same numbers instead of recomputing them. The views answer the daily and
weekly questions directly. Two are queues rather than schedules:
`Needs attention` holds recurring tasks with no due date because they have
never been completed, and `Sweep` holds finished one-time tasks waiting to be
deleted. The `frequency == null` clause on `Sweep` is what keeps a recurring
task that is wrongly sitting in `done` off the deletion list.

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
  explain it. A dangling `formula.X` under `sort:` is equally quiet: the live
  base sorts on a `formula.Untitled` that no `formulas:` block defines, and
  the remaining sort keys still apply as though it were not there. Neither
  case reports anything, so a sort that looks configured may not be.
- **`== null` matches an empty property, but an empty *string* is not null.**
  The template writes `frequency:` with no value, so `frequency == null`
  correctly selects one-time tasks - a filter looking for the key's absence
  would match nothing. But `frequency: ""`, which is what
  `property:set value=""` writes, is **not** null and slips through the
  filter. Verified on a scratch base against the live vault: a
  `frequency != null` probe returned all 29 tasks while the one-time notes
  held `""`, and the correct 11 once they held a bare key. Seed empty keys
  from the template, never from `property:set`.
- **A new property is invisible to `base:query` until a view lists it.**
  Results are keyed by the view's `order:` columns, so a property written to
  every note still reads back as absent until the base file names it. Update
  the base before trying to verify a new field.
- **Test formulas and filters on a scratch base, never the live one.**
  Create it, query it, delete it. A malformed formula is invisible until a
  query returns `Error: ...` in the column where a value should be.
