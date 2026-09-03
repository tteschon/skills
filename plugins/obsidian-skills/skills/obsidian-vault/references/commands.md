# The wider command surface

Read this when the task reaches past reading and writing notes - templates,
bases, link hygiene, file history, or driving the app itself. The command
names below do not imply their arguments, and several return a shape that is
worth knowing before parsing it.

Run `obsidian help <command>` for the authoritative argument list on the
user's installed version. Everything here still exits 0 on failure, so the
verification rule from `SKILL.md` Step 6 applies to every command on this
page.

## Output formats

Most listing commands take `format=`, and the default is rarely the one to
parse. Pick deliberately:

| Need | Use |
|---|---|
| Anything being parsed programmatically | `format=json` |
| A count and nothing else | `total` |
| Something shown to the user | the default text or tsv |

`total` is a bare flag, not `total=true`, and it replaces the listing rather
than annotating it. `obsidian files total` returns a number; `obsidian files`
returns paths.

Note that `format=json` on `search` returns an array of **paths only** - no
matched text. When the matched text is the point, use `search:context`, which
returns `path:line: text` and takes `format=json` as well.

## Templates

Obsidian's template folder is a setting, so the CLI is the only way to find
these without reading the vault config.

| Goal | Command |
|---|---|
| List templates | `obsidian templates` |
| Read one raw | `obsidian template:read name="<name>"` |
| Read with variables filled in | add `resolve title="<title>"` |
| Create a note from a template | `obsidian create name="<name>" template="<name>"` |
| Insert into the open note | `obsidian template:insert name="<name>"` |

Template names have no extension - `Daily Note`, not `Daily Note.md`.

Prefer `create ... template=` over reading a template and passing its body
back as `content=`. The round trip drops variable resolution, so `{{date}}`
and `{{title}}` land in the note as literal text. If a template body must be
inspected first, use `template:read ... resolve` and pass that.

## Bases

`.base` files are Obsidian's saved queries. They answer "which notes match
these criteria" without reimplementing the filter in shell.

| Goal | Command |
|---|---|
| List base files | `obsidian bases` |
| Run a base and get results | `obsidian base:query path="<path>" format=json` |
| Just the matching paths | `obsidian base:query path="<path>" format=paths` |
| Add a note into a base | `obsidian base:create path="<path>" name="<name>"` |

`bases` returns paths including the `.base` extension; pass those to `path=`
verbatim. `format=json` returns one object per matching note, keyed by the
view's own columns - `path` plus whatever properties that view displays, with
`null` for notes that lack one. `format=paths` when only the file list is
wanted.

A base with several views needs `view="<name>"` on `base:query`, or it
queries the default view. **`base:views` cannot be pointed at a base** - it
takes no `file=` or `path=` argument and lists views for whichever base is
open in the app. To read view names for a specific base, read the `.base`
file directly; it is YAML on disk, and the names are under `views:` as
`name:`. That is also the only way to check a base the user does not
currently have open.

## Link hygiene

These read the link graph, which is index-derived and cannot be reproduced by
grepping the vault.

| Goal | Command |
|---|---|
| Notes nothing links to | `obsidian orphans` |
| Notes that link nowhere | `obsidian deadends` |
| Links pointing at nonexistent notes | `obsidian unresolved counts verbose` |
| Inbound links to one note | `obsidian backlinks file="<name>" counts` |

Do not present raw orphan or deadend counts as a problem to fix. In a normal
vault most notes are one or both - 828 orphans out of 1200 notes is an
ordinary vault, not a broken one. These lists are useful filtered to a folder
or cross-referenced with a tag, and misleading as a headline number.

`unresolved` is the one that surfaces genuine mistakes - typo'd wikilinks,
and template placeholders like `{{date}}` left behind in a note where the
variable never resolved. `verbose` adds the source files, which is what makes
the output actionable.

## File history and versions

Two independent histories, with parallel command sets. `history:*` is the
local file recovery snapshot; `sync:*` is Obsidian Sync's server-side
version history and only exists on a synced vault.

| Goal | Command |
|---|---|
| Local versions of a note | `obsidian history path="<path>"` |
| Read a local version | `obsidian history:read path="<path>" version=<n>` |
| Restore a local version | `obsidian history:restore path="<path>" version=<n>` |
| Sync versions | `obsidian sync:history path="<path>"` |
| Read a sync version | `obsidian sync:read path="<path>" version=<n>` |
| Files deleted through sync | `obsidian sync:deleted` |

`No history found for this file.` is the normal answer for a note that has
not changed since snapshots began - it is not an error, and it is not
evidence the note is new.

Always `history:read` a version before `history:restore`. Restore overwrites
the working file with no confirmation and no second undo step, and version
numbers are positional - they shift as new snapshots accumulate, so a number
read in an earlier turn may point somewhere else by the time it is used.

## Driving the app

These change what the user is looking at. Use them when the user asked to be
shown something; do not use them to "check" a result, because opening a note
moves the user's focus mid-task.

| Goal | Command |
|---|---|
| Open a note | `obsidian open path="<path>"` |
| Open in a new tab | add `newtab` |
| Open the search view | `obsidian search:open query="<text>"` |
| List open tabs | `obsidian tabs` |
| Recently opened notes | `obsidian recents` |

`recents` is a good proxy for "the note I was just working on" when the user
refers to something without naming it - but confirm the match before writing
to it rather than assuming the top entry.

## Arbitrary Obsidian commands

`obsidian commands filter=<prefix>` lists every command in the app's palette,
including ones community plugins add, and `obsidian command id=<id>` runs
one. This is the escape hatch for anything the CLI has no verb for.

Treat it as a last resort. Palette commands act on the active note and the
current UI state, report nothing back about what they did, and vary with the
user's installed plugins - so the result cannot be verified the way a
`path=`-targeted command can. Prefer any dedicated command that exists, and
tell the user explicitly when a palette command was used instead.
