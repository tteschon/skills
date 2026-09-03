# Command semantics

`obsidian help <command>` lists arguments. This page covers what it does not:
the shapes these commands return, and the ones that behave differently than
their names suggest.

Everything here exits 0 on failure. The verification rule in `SKILL.md`
applies to every command on this page.

## Output formats

`format=json` for anything parsed, `total` for a bare count, the default for
anything shown to the user.

`total` is a bare flag and it *replaces* the listing rather than annotating it -
`obsidian files total` returns a number, `obsidian files` returns paths.

`format=json` on `search` returns **paths only**, with no matched text. When
the text is the point, use `search:context`, which returns `path:line: text`
and takes `format=json` too.

## Templates

Template names carry no extension - `Daily Note`, not `Daily Note.md`.

**Prefer `create ... template=` over reading a template and passing its body
back as `content=`.** The round trip drops variable resolution, so `{{date}}`
and `{{title}}` land in the note as literal text. When a body must be inspected
first, use `template:read ... resolve` and pass that.

## Bases

`.base` files are Obsidian's saved queries - YAML on disk.

`bases` returns paths including the `.base` extension; pass those to `path=`
verbatim. `base:query format=json` returns one object per matching note, keyed
by **the view's own columns** - `path` plus whatever properties that view
displays, with `null` for notes lacking one. A property written to every note
still reads back as absent until the base names it.

A base with several views needs `view="<name>"`, or it queries the default.

**`base:views` cannot be pointed at a base.** It takes no `file=` or `path=`
and lists views for whichever base is open in the app. To read view names for a
specific base, read the `.base` file directly - the names are under `views:` as
`name:`. That is also the only way to inspect a base the user does not
currently have open.

## Link hygiene

Index-derived; not reproducible by grepping the vault.

**Do not present raw orphan or deadend counts as a problem to fix.** In a
normal vault most notes are one or both - 828 orphans out of 1200 notes is an
ordinary vault, not a broken one. These lists are useful filtered to a folder
or crossed with a tag, and misleading as a headline number.

`unresolved` is the one that surfaces genuine mistakes - typo'd wikilinks, and
template placeholders like `{{date}}` left in a note where the variable never
resolved. `verbose` adds the source files, which is what makes it actionable.

## File history and versions

Two independent histories with parallel command sets: `history:*` is the local
file recovery snapshot, `sync:*` is Obsidian Sync's server-side history and
exists only on a synced vault.

`No history found for this file.` is the normal answer for a note unchanged
since snapshots began. It is not an error and not evidence the note is new.

**Always `history:read` a version before `history:restore`.** Restore
overwrites the working file with no confirmation and no second undo. Version
numbers are positional and shift as new snapshots accumulate, so a number read
in an earlier turn may point somewhere else by the time it is used.

## Driving the app

`open`, `search:open`, `tabs`, `recents` change what the user is looking at.
Use them when the user asked to be shown something; do not use them to check a
result, because opening a note moves their focus mid-task.

`recents` is a good proxy for "the note I was just working on" when the user
refers to something without naming it - but confirm the match before writing to
it rather than assuming the top entry.

## Arbitrary palette commands

`obsidian commands filter=<prefix>` lists every command in the app's palette,
including ones plugins add, and `obsidian command id=<id>` runs one.

Treat it as a last resort. Palette commands act on the active note and the
current UI state, report nothing about what they did, and vary with the user's
installed plugins - so the result cannot be verified the way a `path=`-targeted
command can. Prefer any dedicated command that exists, and tell the user
explicitly when a palette command was used instead.
