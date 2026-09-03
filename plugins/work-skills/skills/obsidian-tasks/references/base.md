# Repairing the task base

Read this when the base disagrees with the plugin, or when a filter, formula or
view needs changing. Creating one is not covered, because the plugin's **Open
base file** command does it - generating the filters from its own settings, so
a base made that way agrees with the pane by construction.

Day-to-day task work never touches this file. Nothing in `SKILL.md` reads the
base at all: `tasks()` and `buckets()` go through the plugin, which walks the
metadata cache. The base is what the *user* looks at.

Verified against Obsidian 1.13.x.

## The base and the plugin can drift

Bases exposes no plugin API, so the plugin does not query the `.base` file - it
re-implements the filter clauses against the metadata cache. The two agree only
as long as someone keeps them agreeing.

That makes the check one line:

```bash
tb 'contract()'                              # the baseFilters the plugin uses
obsidian read path="<basePath from contract>"
```

Every clause in `contract().baseFilters` must appear in the file's `filters:`
block. A base missing `!file.inFolder("Templates")` will list the task template
as a task; a base with an extra clause hides rows the pane still counts.

## What the generated base contains

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
    order: [file.name, done, category, frequency, created, due, last done,
            priority, asset, formula.days_until_due, formula.overdue]
    sort:
      - {property: done, direction: ASC}
      - {property: due, direction: ASC}
  - type: table
    name: Today
    filters: {and: ['done != true', 'due != null', 'due <= today()']}
    order: [file.name, category, due, priority]
  - type: table
    name: This week
    filters: {and: ['done != true', 'due != null', 'due <= today() + "7d"']}
    order: [file.name, category, due, formula.days_until_due, priority]
  - type: table
    name: Needs attention
    filters: {and: ['done != true', 'frequency != null', 'due == null']}
    order: [file.name, frequency, last done, priority]
  - type: table
    name: Sweep
    filters: {and: ['done == true', 'frequency == null']}
    order: [file.name, category, last done, created]
```

Three of these encode decisions rather than taste:

- **No `done` clause on the base's own filter.** An earlier version excluded
  finished tasks, which put a completed note beyond the reach of every query
  the moment it was finished - tidy to look at, and impossible to clean up.
  Keeping them in the base is what makes `obsidian-task-grooming`'s sweep
  possible.
- **`Needs attention` is a queue, not a schedule** - recurring tasks with no
  due date, because they have never been completed.
- **`Sweep`'s `frequency == null` clause is a guard**, not a filter. Without it
  a recurring task wrongly sitting at `done: true` would appear on a list of
  things to delete, and deleting it destroys the schedule rather than repairing
  it.

A base predating plugin 0.4.0 will be missing `Sweep` and the two formula
columns. Neither breaks anything - grooming filters by hand when the view is
absent - but adding them is the fix.

## Writing the file

```bash
obsidian create path="<path>" content="..."
```

Pass newlines as literal `\n`. `create` makes missing parent folders on the
way, and the base is queryable immediately - no reload.

## Gotchas

These fire only while editing a base. The ones that bite during ordinary task
work are in `SKILL.md`.

- **`obsidian create` needs the `overwrite` flag to replace a file.** Without
  it, pointed at an existing path, it writes `<name> 1.base` alongside the
  original and reports success - and a query against the original path then
  returns the old content, which reads as an edit that did not take. The
  `Created:` line names the path it actually wrote; `Overwrote:` is what a
  successful replace prints. Confirm with the user before overwriting, since it
  replaces the whole file.
- **A file written from the shell is not immediately visible to the CLI.**
  `obsidian read` serves the app's cached copy and can return pre-edit content
  for a moment after an external write, while `cat` shows the new bytes. When a
  read looks stale, check the filesystem before concluding the write failed.
- **Date subtraction yields a Duration, and `.days` is still not an integer.**
  Access `.days` before any number function - `.round()` on a raw Duration
  fails. Then round it: daylight saving makes a span across a DST boundary 120
  days *and one hour*, so `(due - today()).days` returns `120.04166666666667`.
- **A formula over an empty property errors on every row that lacks it.** Guard
  with `if()`.
- **A formula no view lists is returned by nothing.** It is computed nowhere
  and readable nowhere, with no error to say so - which is how
  `days_until_due` and `overdue` sat unreachable in the generated base until
  0.4.0. A dangling `formula.X` under `sort:` is equally quiet: the remaining
  sort keys apply as though it were not there.
- **`== null` matches an empty property, but an empty *string* is not null.**
  The template writes a bare `frequency:`, so `frequency == null` correctly
  selects one-time tasks. `frequency: ""` slips through the filter. The plugin
  writes bare keys; hand edits and `property:set` do not.
- **A new property is invisible to `base:query` until a view lists it.**
  Results are keyed by the view's `order:` columns, so a property written to
  every note still reads back as absent. Update the base before trying to
  verify a new field through a query - or read it through `get(path)`, which
  does not go via the base at all.
- **Test formulas and filters on a scratch base, never the live one.** Create
  it, query it, delete it. A malformed formula is invisible until a query
  returns `Error: ...` in the column where a value should have been.
