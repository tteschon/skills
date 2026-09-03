---
name: obsidian-cli
description: Read, search, and edit an Obsidian vault with the obsidian CLI - notes, daily notes, properties, tags, backlinks, templates, and bases. Use when finding or summarizing notes, capturing into today's daily note, editing a note, or when the user mentions Obsidian, their vault, a daily note, a wikilink, or says "add this to my notes". Do NOT use for a vault where each task is its own note - that is obsidian-tasks.
compatibility: Requires the obsidian CLI - Obsidian desktop 1.12.7+ with Settings - General - Command line interface enabled, and the app running
---

# Obsidian CLI

Use the `obsidian` CLI to work inside a vault through the running app. Requires
Obsidian to be open.

This skill covers the calling conventions and the failure modes. It does not
mirror the command list, because the CLI ships its own and that one is current.

## Command reference

Run `obsidian help` for all commands, and `obsidian help <command>` for one
command's arguments. This is always up to date. Full docs:
https://help.obsidian.md/cli

Flag sets vary by build. A flag taken from any external source - including
published documentation - may not exist here, so check `obsidian help` before
using one.

## Workflow

1. **Check the CLI exists** with `command -v obsidian`. Use that, not a real
   command: it costs nothing and will not launch the app as a side effect.
2. **Target the vault** with a leading `vault=<name>` when more than one
   exists. Confirm with `obsidian vault info=name`.
3. **Locate the note** with `search`, `files`, or `daily:path`. Take paths from
   the app's output, never from `ls`.
4. **Read or write**, using `path=` for anything that writes.
5. **Validate**: read the output text for a leading `Error: `, then read the
   note back. Common failures: the command exited 0 despite failing, `vault=`
   was placed after the command and ignored, or `path=` was omitted and the
   write landed in whatever note is open.

## Syntax

**Parameters** take a value with `=`. Quote values containing spaces.
**Flags** are bare switches with no value - `total`, `verbose`, `counts`,
`newtab`, not `total=true`.

Inside `content=`, write newlines as a literal `\n` and tabs as `\t`. Passing a
real multi-line string is what silently produces a one-line note.

## File targeting

- `file=<name>` resolves by name the way a wikilink does. Convenient, but it
  picks one match silently when several notes share a name.
- `path=<folder/note.md>` is exact, including the extension.

**Use `path=` for anything that writes.** Omitting both targets whatever note
is open in the app.

## Vault targeting

The default target is the vault matching the shell's working directory, and the
active vault otherwise. Agent commands almost never run from inside a vault, so
the default is whichever vault the user last had focused.

`vault=` **must come before the command name.** Placed after it, it is parsed
as an argument to that command and ignored - the command runs against the wrong
vault with no warning.

```bash
# WRONG - runs against the default vault, silently
obsidian files total vault=work-vault

# CORRECT - vault= leads
obsidian vault=work-vault files total
```

## Common patterns

```bash
obsidian search query="search term" format=json      # paths only
obsidian search:context query="search term"          # path:line: text
obsidian read path="folder/My Note.md"
obsidian outline path="folder/My Note.md"            # headings only
obsidian daily:read
obsidian daily:append content="- [ ] New task"
obsidian create name="New Note" path="folder" template="Daily Note"
obsidian append path="folder/My Note.md" content="New line"
obsidian properties path="folder/My Note.md"
obsidian property:set name=status value=done path="folder/My Note.md"
obsidian backlinks file="My Note"
obsidian tag name=project verbose
obsidian delete path="folder/My Note.md"
```

Add `format=json` to anything being parsed, `total` for a bare count, and
`verbose` or `counts` to enrich a listing.

## Reading the vault without the CLI

The vault is ordinary Markdown on disk, so Read and Grep work directly and are
faster for bulk scanning. Use the CLI when the answer depends on Obsidian's
index rather than on file text - backlinks, orphans, tag counts, wikilink
resolution, templates, or the daily note's configured folder and date format.

**Route every write through the CLI**, so a note the user has open cannot
clobber the change with an unsaved buffer.

## Validating a write

**IMPORTANT:** Every command exits 0, including the ones that failed. Errors
arrive as a line on stdout beginning with `Error: `, so `&&` chains, `set -e`,
and `if` on exit status all read a failure as a success.

```bash
# WRONG - the read failed, the append runs anyway
obsidian read file="NoSuchNote" && obsidian append path="x.md" content="y"

# CORRECT - run separately, match the output text
obsidian read file="NoSuchNote"        # -> Error: File "NoSuchNote" not found.
```

Then read the result back with `read`, `daily:read`, or `properties` and
confirm the change is in the note. Silence is not success; it is no
information.

The one exit code worth reading is 127, which comes from the shell rather than
the CLI and means the binary is absent.

## Confirm before

`delete`, `move` or `rename` on a note with backlinks, and `create ...
overwrite`, which replaces a whole file. To add to an existing note, `append`
or `prepend` - never `create overwrite`.

## Troubleshooting

**The CLI is missing.** `command -v obsidian` printing nothing means it is not
installed, or the CLI was never enabled. The two are indistinguishable from the
shell and neither is fixable from it - the command is a root-owned symlink into
the app bundle, created by a prompt the user answers under Settings - General -
Command line interface on installer 1.12.7 or later. Say what is missing and
stop. Do not install anything, do not write to the vault directory as a
workaround, and do not fall back to editing Markdown by hand unless the user
asks after being told.

**A command pauses.** Obsidian was closed and the command is launching it.
Wait, then rerun.

**`property:set` broke sorting everywhere.** `type=` is a vault-wide setting,
not a per-note one. It writes `.obsidian/types.json`, so one note's edit
retypes the property for every note and every base that sorts on it. Nothing
warns, and the note itself looks correct.

```bash
# WRONG - flips due from date to text for the entire vault
obsidian property:set name=due value="~25,731 mi" type=text path="note.md"

# CORRECT - same value written, registry untouched
obsidian property:set name=due value="~25,731 mi" path="note.md"
```

**`daily:path` returned a path that does not exist.** It reports the configured
folder and date format, not a file listing, so it answers for today whether or
not the note was written. Use `daily:read` and `daily:append`, which handle the
not-yet-created case; `append path=` does not.

**A different vault changed than expected.** Either `vault=` came after the
command, or the shell's working directory was inside another vault. Confirm
with `obsidian vault info=name` before writing.

**A deletion reached other devices.** `delete` without `permanent` goes to the
vault's `.trash`, which is still a synced change - on a vault with Obsidian
Sync it propagates immediately. Never pass `permanent` unless the user asked.

## Complete example

Capturing a thought into today's note and confirming it landed:

```bash
obsidian vault=home-vault vault info=name           # confirm the target
obsidian vault=home-vault daily:append content="- Called the roofer\n"
obsidian vault=home-vault daily:read                # read back, check the line
```

Three commands, run separately rather than chained, with the read-back as the
only evidence the write happened.

The first line reads oddly and is correct: `vault=` is the parameter selecting
which vault, and `vault` is the command that reports on it.

## References

- https://help.obsidian.md/cli
- `references/commands.md` - templates, bases, link hygiene, file history, and
  driving the app, with the argument shapes that are not guessable from the
  command names
