# Writing style for skills in this repository

Two jobs, and they fail in different ways. The **description** decides whether
the skill is loaded at all. The **body** decides whether loading it changed the
outcome. A perfect body behind a vague description is dead weight; a great
description in front of a body of generic advice is worse - it costs context
and gives nothing back.

## Writing the description

The description is the only text an agent sees before deciding to load the
skill. It is not a summary. It is a routing decision, written for a reader who
has the user's message and a list of thirty other descriptions.

The pattern:

1. **What it does**, third person, active, one sentence. Name the concrete
   outputs and the artifact - the file extension, the binary, the format.
   "Read, search, and edit an Obsidian vault with the obsidian CLI - notes,
   daily notes, properties, tags, backlinks" routes; "helps with notes" does
   not.
2. **When to use it**, as a `Use when ...` sentence covering the phrasings a
   user actually types, including the ones that never name the tool. Someone
   who says "turn this script into a package" is asking for the Python skill
   without using any of its keywords.
3. **When not to use it**, one clause, only if there is a near neighbour it
   keeps getting confused with.

Rules of thumb:

- **Third person, no "you".** It is read by an agent about a skill, not
  addressed to the user.
- **Length: roughly 250-500 chars.** The cap is 1024 and the old guidance here
  was 400-900, which was too generous. Under ~200 there is usually not enough
  trigger surface to route reliably.
- **What inflates a description is disambiguation.** Skills split by artifact
  or by domain barely need any, because the boundary is self-evident; skills
  split by *activity* over the same artifact need a clause per neighbour and
  pay for it. `obsidian-cli` is 413 chars where the skill it replaced was 897,
  and almost the whole difference was three "do not use this for X" clauses
  that stopped being necessary once the boundaries moved.
- **A negative clause is worth more than another positive example**, where one
  is genuinely needed. It is where the skill would otherwise misfire.
- **No colons in unquoted values.** ` - ` reads the same and cannot break the
  YAML parse.

Three failure modes to check the draft against:

| Failure | Symptom | Fix |
|---|---|---|
| Too vague | Never fires; the agent solves it from general knowledge | Add concrete outputs and trigger words |
| Too narrow | Fires only when the user names the tool | Add the phrasings that describe the goal, not the tool |
| Too broad | Fires on unrelated requests, crowding out siblings | Add the "do not use it for" clause |

## Choosing a shape

Two shapes. Pick by asking whether a typical request runs the whole document or
only part of it.

### Procedure - one shot, in order

```
# Title

One or two sentences: what this produces, and what "done" means.

## Before you <verb>       <- what to ask, and what not to ask
## Step 1 - ...            <- numbered, imperative, in execution order
## Step N - Verify         <- commands that must go green
## Step N+1 - Report       <- what to tell the user
## Gotchas                 <- only non-obvious, outcome-changing specifics
```

Use this when the skill produces a thing once and every run walks the same
path - scaffolding a project, authoring a skill, generating a document. This
skill and `new-python-project` are both procedures.

### Operations - a menu against a live system

```
# Title

What this operates on, and the one invariant that holds across every operation.

## Workflow                <- numbered imperative verbs, including Validate
## <Operation>             <- one section per independent operation
## Validating a write
## Troubleshooting         <- symptom-led, with WRONG/CORRECT pairs
## Complete example
## References
```

Use this when a request touches two or three sections and never the rest -
reading a vault, managing tasks, driving an API.

**Numbered steps are actively wrong here**, for two reasons. They imply a path
nobody walks: "mark this task done" hit Steps 1, 3 and 7 of a seven-step
document, so six sevenths of the numbering was noise. And step numbers are
load-bearing across skills - one skill said "see `obsidian-tasks` Step 4", and
renumbering broke the reference silently. Section names survive edits.

## Rules for both shapes

- **Imperative voice, addressed to the agent.** "Run every command that
  applies. Read each failure, fix it, run again."
- **A table at every real decision point.** Situation in the left column,
  command or location in the right. Prose describing four options makes the
  agent re-derive the mapping; a table hands it over.
- **Delete what the model already knows, and delegate to live sources.** Do not
  mirror a tool's `--help`; it goes stale and the tool's own copy does not.
  `obsidian-cli` replaced its command tables with "Run `obsidian help` ... this
  is always up to date" and kept only what help cannot teach - the calling
  convention, the resolution semantics, and the failure modes. Its reference
  file went 152 lines to 95.
- **Teach errors as `# WRONG` / `# CORRECT` comment pairs inside code fences**,
  not prose warnings. The pair shows the fix at the same time as the mistake,
  in the form the agent will actually type:

  ````
  ```bash
  # WRONG - runs against the default vault, silently
  obsidian files total vault=work-vault

  # CORRECT - vault= leads
  obsidian vault=work-vault files total
  ```
  ````

- **Say what happens when it goes wrong.** The expected non-failures are as
  load-bearing as the happy path: a first `pre-commit` run that exits non-zero
  *because* it reformatted files is a pass, and an agent that does not know
  that will "fix" it wrongly.
- **Ration emphasis.** Bold belongs on workflow-step verbs and run-in headings.
  Reserve `**IMPORTANT:**` for a genuine footgun and expect to spend it once or
  twice in a document. `obsidian-tasks` once carried 28 bold spans, at which
  point none of them read as emphasis - the reader skims past all of them
  equally.
- **End with verification, not creation.** Every skill that writes should have
  a step whose commands must exit clean, and an explicit "do not report success
  with a red command in the transcript".
- **Explain why, once, where it changes a decision.** "Use `ty` - same team as
  uv and ruff, so the toolchain moves together; switch to mypy when the project
  needs plugins" tells the agent how to handle the case the author did not
  enumerate. Reasons that do not change a decision are filler.
- **Close with `## Complete example` and `## References`** where there is
  something real to show: one end-to-end sequence with its actual output, and
  a bare list of canonical upstream URLs.
- **Wrap at roughly 76 characters** to match the existing files.

## Gotchas and Troubleshooting

Same content, two presentations. `## Gotchas` is a bulleted list, and suits a
procedure where the reader meets them in order. `## Troubleshooting` is
symptom-led - each entry opens with what the author will observe - and suits
operations, where the reader arrives already holding a failure.

This is where the value concentrates. It holds what an agent gets wrong when
left to its own judgment, not general best practice.

An entry earns its place if it is silent (parses fine, fails later), expensive
to undo (a layout decision), counterintuitive (the check passes because nothing
was checked), or version-specific (a renamed hook id, a deprecated alias).

State the rule, then the mechanism, then the fix - and where the fix is a
command, show the pair rather than describing it:

> **Never place a key in `pyproject.toml` by appending to the end of the
> file.** TOML scopes a bare key to the most recent table header, so
> `requires-python` appended after a `[tool.ruff.lint]` section becomes a ruff
> setting that ruff ignores, while `[project]` still has none. It parses
> cleanly and fails silently. Find the table, then insert.

If a bullet would survive being pasted into any other skill unchanged, it is
not a gotcha - delete it.

## Progressive disclosure

`SKILL.md` is loaded whole, every time. Everything under `references/` is
loaded only when the body sends the agent there.

| Content | Where |
|---|---|
| Needed on every run | `SKILL.md` |
| Needed on some runs; long | `references/<topic>.md` |
| Long config blocks to copy out | `references/` |
| Deterministic, better as code | `scripts/` |

Keep the common subset inline and move the exhaustive enumeration out. Duplicate
a reference item back into `SKILL.md` only when it is a high-frequency footgun
the agent must hit whether or not it opens the reference.

When splitting, leave a pointer that states the payoff, so an agent under time
pressure does not skip it: "Read `references/configs.md` and copy out the blocks
that match - the reasoning for each rule selection is there, and the defaults
are chosen to not fight each other."

References are prose for an agent, not appendices for a human: same imperative
voice, same tables, no "as discussed above".
