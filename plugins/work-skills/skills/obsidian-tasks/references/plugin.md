# The Task Base API

Read this for a call's arguments, its return shape, or why it refused.
`SKILL.md` covers when to reach for each one.

The authoritative version of this page is the plugin's own README, under
**Driving it from a script** - it sits next to the code that can invalidate it.
This page is the caller's view.

## The call form

```bash
tb() { obsidian eval code="(async()=>JSON.stringify(await app.plugins.plugins['task-base'].api.$1))()"; }
```

Nested quoting is the thing to get right: double quotes outside, single quotes
around the plugin id, and the argument object written as JavaScript rather than
JSON - `{name:"Mow the lawn"}` is fine, unquoted keys and all.

## Every call returns a Result

```json
{"ok": true,  "value": ...}
{"ok": false, "error": "..."}
```

A refusal is a normal return. The CLI exits 0 for both, and so does a call that
threw - the API converts an exception into the same shape, so there is exactly
one thing to check.

Three failures are worded apart because they call for different fixes:

| `error` | Means |
|---|---|
| `No note at "<path>".` | The path is wrong - a typo, or a note already deleted |
| `"<path>" is not a task — it does not carry type: task.` | The note exists but lacks the identity property. This is the classic failure of a system where a property, not a folder, decides membership |
| `The repeat rule cannot be read...` | `frequency` is set to something unparseable. Neither recurring nor one-time |

## Facts

### `contract()`

The schema, as the vault currently holds it. Read it in Step 1 and use its
values instead of any list written down in this skill.

| Key | |
|---|---|
| `apiVersion`, `pluginVersion` | `apiVersion` is `1`. A higher number means a call's shape may have changed |
| `fields` | Frontmatter keys in the order the template writes them |
| `identity` | `{property: "type", value: "task"}` - what makes a note a task |
| `priorities`, `categories` | The live values, `categories` merging the setting with what the vault actually uses |
| `taskFolder`, `basePath`, `excludedFolders` | Layout |
| `baseFilters` | The clauses a task base must filter on to agree with the plugin |
| `logHeading` | Where `detail` lines go |
| `ranking` | How `tasks()` and `buckets()` are ordered, in words |
| `recurrencePolicy` | How a completion computes the next due date, in words |
| `neverWritten` | Fields the plugin refuses to touch, each with its reason |

## Reads

| Call | Returns |
|---|---|
| `tasks()` | Every task note, ranked |
| `get(path)` | One task, or a refusal |
| `buckets(today?)` | The pane's sections - see below |
| `assets()` | `{path, name}` for every note carrying `type: asset` |

A task crosses the boundary as plain JSON - `path` is a string, `done` is a
real boolean, an unset field is `null`. `TFile` does not survive
`JSON.stringify`, which is why `path` and not the file object.

```json
{"path":"tasks/Mow Lawn.md","name":"Mow Lawn","done":false,"due":"2026-09-13",
 "created":"2026-06-29","priority":"low","category":"yard",
 "lastDone":"2026-09-01","frequency":"FREQ=WEEKLY;BYDAY=SU",
 "asset":"[[Cub Cadet Ultima 54 Mower]]"}
```

### `buckets()`

| Bucket | Contents |
|---|---|
| `overdue` | Open, `due` before today |
| `today` | Open, `due` today |
| `thisWeek` | Open, `due` within 7 days |
| `needsAttention` | Open, recurring, no `due` - awaiting a first completion |
| `later` | **Every other open task** - the remainder, not a date window |
| `stalled` | Recurring tasks sitting at `done: true` - they stopped recurring |
| `invalidRule` | `frequency` set but unparseable |
| `all` | Every task note, finished ones included |

`later` being a remainder is load-bearing: a one-time task with no `due` at all
matches none of the other filters, and a hand-rolled "due beyond this week"
query would lose it silently.

## Pure calls

None of these read a note or write anything, so they are safe while thinking
out loud with the user.

| Call | Returns |
|---|---|
| `nextDue(rule, completedOn?)` | The date a completion on that day would produce, or `null` |
| `upcoming(rule, from?, count?)` | The next `count` occurrences - what the builder previews |
| `describeRule(rule)` | Plain English, e.g. "every 6 months on the last day" |
| `ruleState(rule)` | `none` \| `valid` \| `invalid` |
| `buildRule(spec)` | A rule string from `{freq, interval, byday, lastDayOfMonth}` |

`previewCompletion(path, completedOn?)` is the one that touches a note - it
reads it, writes nothing, and returns `{kind, due, reason}`: the branch a
completion would take and the date it would write.

## Writes

| Call | |
|---|---|
| `create(spec)` | `name` required; `folder`, `priority`, `category`, `due`, `frequency`, `asset`, `body` optional, defaulting to the plugin's settings |
| `complete(path, {detail?, due?, completedOn?})` | Branches on the rule. Returns `{kind, task, reason}` |
| `update(path, changes)` | `due`, `priority`, `category`, `frequency`, `asset`, `lastDone`, `done` |
| `appendLog(path, detail, when?)` | A dated line under the log heading |

Three things hold across all of them:

- **They re-read the note before returning**, waiting for the metadata cache
  first. So the returned task is what the vault stored, not what was sent - a
  date field that rejected a value reports the old one rather than pretending.
- **`null` clears a field; `""` does not.** An empty string is not null to
  Bases, and a `frequency != null` filter would start matching one-time tasks.
  The API writes a bare key.
- **Nothing here deletes.** `complete` on a one-time task writes `done: true`
  and leaves the note in the base. Deletion is `obsidian delete`, under a
  confirmation, and only in `SKILL.md` Step 3.

`create` never overwrites: an existing name gets a numbered suffix, the way
Obsidian itself does. Check the `path` it returns rather than assuming the name
you asked for.

## Commands are for people, not for this skill

```bash
obsidian commands | grep task-base
```

**Never fire one from the CLI.** `obsidian command` prints `Executed: <id>`
whether the command did the work or opened a form and walked away, and every
task-taking command falls back to a picker modal when the active file is not a
task. There is no result channel and no way to pass an argument.

Two are worth *suggesting* by name, because a person does them better than an
argument does:

- **Edit repeat rule** - a builder that previews the next three dates.
- **Create task** / **Set asset** - forms, with a type-ahead over real notes.

To check nothing was left waiting for the user:

```bash
obsidian eval code='document.querySelectorAll(".modal-container").length'
```

## When something looks wrong

- **`{}` came back.** The `await` is missing from the call form. The write
  probably happened; re-read with `get(path)` before retrying.
- **Nothing came back at all.** `eval` prints nothing for `undefined`, which is
  what an unloaded plugin looks like. Check `obsidian plugins:enabled`.
- **`apiVersion` is not `1`.** A call's arguments or return shape may have
  changed. Say so rather than guessing.
- **The pane disagrees with `buckets()`.** They read the same repository, so
  they cannot disagree about tasks - but the *base* can, since it filters
  independently. Compare `contract().baseFilters` with the `.base` file;
  `references/base.md` covers repairing it.
