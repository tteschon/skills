---
name: obsidian-vault
description: Reads, searches, and edits an Obsidian vault through the obsidian command line interface - notes, daily notes, tasks, frontmatter properties, tags, backlinks, and templates. Use this skill when the user wants to find something in their notes, read or summarize a note, capture a thought into today's daily note, create or append to a note, tick off a task, retag or move files, or trace what links to what. Also use it when the user mentions Obsidian, their vault, a daily note, a wikilink, or the obsidian CLI - and when they say things like "add this to my notes", "what did I write about X", or "put that in today's note" without naming the tool. Do not use it for Markdown files outside a vault, or to edit this repository's own docs - the ordinary file tools are better for those.
compatibility: Requires the obsidian CLI - Obsidian desktop 1.12.7+ with Settings - General - Command line interface enabled, and the app running
---

# Obsidian Vault

Work inside an Obsidian vault through the `obsidian` CLI - find notes, read
them, capture into the daily note, edit files, and update tasks, tags, and
frontmatter properties.

The job is not done when a command returns. **This CLI exits 0 on failure**,
so nothing is confirmed until the read-back in Step 6.

## Before you start

Check the CLI exists before planning anything around it. Use `command -v`,
not a real command - it costs nothing and, unlike every other command here,
it will not launch the app as a side effect:

```bash
command -v obsidian
```

| Result | Meaning | What to do |
|---|---|---|
| A path, exit 0 | Installed and registered | Continue to `obsidian vaults verbose` |
| Nothing, exit 1 | Not installed, or the CLI was never enabled | Stop and tell the user |

Those two failures are indistinguishable from the shell and neither is
fixable from it. The `obsidian` command is a root-owned symlink into the app
bundle, created by a prompt the user answers under Settings - General -
Command line interface on installer 1.12.7 or later - GUI steps needing their
admin password. **Say what is missing and stop.** Do not install anything, do
not write to the vault directory as a workaround, and do not fall back to
editing the Markdown by hand unless the user asks for that after being told.

With the CLI present, `obsidian vaults verbose` confirms it can reach the
app. A table of vault names and paths means everything works; a pause means
Obsidian was closed and this command is launching it - wait, then rerun.

Then ask only what the vault cannot answer:

1. **Which vault**, when `obsidian vaults` lists more than one and the
   request does not single one out.
2. **Which folder a new note goes in**, when creating one and nothing in the
   request or the vault's existing layout implies a home.

Skip both when the request already answers them. "Add a line to my daily
note" needs no questions at all.

## Step 1 - Target the right vault

The default target is the vault matching the shell's working directory, and
the active vault otherwise. Agent commands almost never run from inside a
vault, so the default is whichever vault the user last had focused - which is
not a fact worth betting a write on.

| Situation | What to run |
|---|---|
| One vault exists | Nothing; the default is correct |
| A specific vault, by name | `obsidian vault=<name> <command> ...` |
| Confirm what is being targeted | `obsidian vault info=name` |

`vault=` **must come before the command.** Placed after it, it is parsed as
an argument to that command, ignored, and the command runs against the wrong
vault without any warning. See Gotchas.

## Step 2 - Locate the note

Names resolve two ways, and picking the wrong one is the most common failed
command. `file=<name>` resolves by name the way a wikilink does - convenient,
but it silently picks one match when several notes share a name.
`path=<folder/note.md>` is exact, including the extension; use it for
anything that writes.

| Goal | Command |
|---|---|
| Full-text search, paths only | `obsidian search query="<text>" format=json` |
| Search with the matching lines | `obsidian search:context query="<text>"` |
| Narrow a search to a folder | add `path="<folder>"` |
| List a folder's notes | `obsidian files folder="<folder>"` |
| Notes carrying a tag | `obsidian tag name=<tag> verbose` |
| Today's daily note path | `obsidian daily:path` |
| What links to a note | `obsidian backlinks file="<name>"` |
| Confirm a note exists | `obsidian file path="<path>"` |

`search` returns files; `search:context` returns `path:line: text` and is
what to reach for when the answer is a passage rather than a note.

## Step 3 - Read what is there

| Goal | Command |
|---|---|
| Note contents | `obsidian read path="<path>"` |
| Headings only | `obsidian outline path="<path>"` |
| Today's note | `obsidian daily:read` |
| Frontmatter | `obsidian properties path="<path>"` |
| One property value | `obsidian property:read name=<key> path="<path>"` |

The vault is ordinary Markdown on disk, so Read and Grep work on it directly
and are faster for bulk scanning - use them for that. Use the CLI whenever
the answer depends on Obsidian's index rather than on file text - backlinks,
orphans, tag counts, wikilink resolution, templates, or the daily note's
configured folder and date format. **Route every write through the CLI**, so
a note the user has open cannot clobber the change with an unsaved buffer.

## Step 4 - Write

| Goal | Command |
|---|---|
| New note | `obsidian create name="<name>" path="<folder>" content="<text>"` |
| New note from a template | add `template="<template name>"` |
| Append | `obsidian append path="<path>" content="<text>"` |
| Prepend | `obsidian prepend path="<path>" content="<text>"` |
| Capture into today | `obsidian daily:append content="<text>"` |
| Rename in place | `obsidian rename path="<path>" name="<new name>"` |
| Move | `obsidian move path="<path>" to="<folder>"` |
| Delete to trash | `obsidian delete path="<path>"` |

Quote any value containing spaces, and write newlines as a literal `\n` and
tabs as `\t` inside `content=`. Passing a real multi-line string instead is
what silently produces a one-line note.

Confirm with the user before `delete`, before `move` or `rename` on a note
with backlinks, and before `create ... overwrite`, which replaces a whole
file. To add to a note that already exists, `append` or `prepend` - never
`create overwrite`.

## Step 5 - Tasks, properties, and tags

| Goal | Command |
|---|---|
| Open tasks in the vault | `obsidian tasks todo format=json` |
| Tasks in one note | `obsidian tasks path="<path>" format=json` |
| Complete a task | `obsidian task ref=<path>:<line> done` |
| Set frontmatter | `obsidian property:set name=<key> value=<v> type=<type> path="<path>"` |
| Remove frontmatter | `obsidian property:remove name=<key> path="<path>"` |
| Tags on a note | `obsidian tags path="<path>"` |
| Tag counts across the vault | `obsidian tags counts sort=count` |

`tasks ... format=json` returns `status`, `text`, `file`, and `line` per
task - read the `line` from that output and feed it straight back as
`ref=<file>:<line>`. Do not count lines by hand from a `read`; frontmatter
and the file's own offsets will not agree with the index.

`property:set` needs `type=` to store anything that is not text -
`list`, `number`, `checkbox`, `date`, or `datetime`. Without it a date lands
as a string and stops sorting.

For templates, bases, link hygiene, and file history, read
`references/commands.md` - it maps each of those onto the exact command and
arguments, which are not guessable from the command names alone.

## Step 6 - Verify

Every command in this CLI exits 0. Errors arrive as a line on **stdout**
beginning with `Error: `, so `&&` chains, `set -e`, and `if` on exit status
all read a failure as a success.

Verify both ways, every time:

1. **Read the output text.** A leading `Error: ` is a failure. So is
   `No backlinks found.` when backlinks were the point.
2. **Read the result back.** After a write, run the matching read - `read`,
   `daily:read`, `properties`, or `tasks` - and confirm the change is
   actually in the note.

Do not report a write as done on the strength of a silent command. Silence
here is not success; it is no information.

## Step 7 - Report

Give the user the vault name, the note paths touched, and what changed in
each, quoting the read-back for anything created or edited. If a command
printed an `Error: ` line, say so plainly and say what did not happen.

## Gotchas

- **Every command exits 0, including the ones that failed.** `obsidian read
  file="NoSuchNote"` prints `Error: File "NoSuchNote" not found.` and exits
  0. Anything downstream that branches on exit status - `&&`, `||`,
  `set -e`, `if obsidian ...` - takes that as a success and keeps going, so
  a chained write runs on a premise that was never true. Run the commands
  separately and match the output text against `Error: `. The one exit code
  worth reading is 127, which comes from the shell rather than the CLI and
  means the binary is absent - see "Before you start".
- **`vault=` after the command name is silently ignored.**
  `obsidian vault=work-vault files total` and
  `obsidian files total vault=work-vault` both succeed and return different
  numbers, because the second one ran against the default vault. Nothing
  warns. When more than one vault exists, put `vault=` first or confirm the
  target with `obsidian vault info=name` before writing.
- **The working directory can change which vault is targeted.** Running from
  inside a vault folder targets that vault regardless of which one is
  focused in the app. A command that behaved one way from the project
  directory behaves differently from the user's notes directory.
- **`daily:path` returns today's path whether or not the note exists.** It
  reports the configured folder and date format, not a file listing, so
  `read path="$(obsidian daily:path)"` fails on any day the user has not
  written yet. Use `daily:read` to read and `daily:append` to write - both
  handle the not-yet-created case; `append path=` does not.
- **`file=` picks one match and does not say it was ambiguous.** Two notes
  named `index` in different folders resolve to one of them, quietly. Use
  `path=` for writes, and use `obsidian search` first when only a name is
  known.
- **Omitting both `file=` and `path=` targets whatever is open in the app.**
  Most commands fall back to the active file, so a bare `obsidian append
  content="..."` writes into whichever note the user happens to be looking
  at. Always pass `path=` on a write unless the user explicitly said "the
  note I have open".
- **`delete` without `permanent` goes to the vault's `.trash`, which is
  still a synced change.** On a vault with Obsidian Sync the deletion
  propagates to the user's other devices immediately. Confirm before
  deleting, and never pass `permanent` unless the user asked for it.
