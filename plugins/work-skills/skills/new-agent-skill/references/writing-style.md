# Writing style for skills in this repository

Two jobs, and they fail in different ways. The **description** decides
whether the skill is loaded at all. The **body** decides whether loading it
changed the outcome. A perfect body behind a vague description is dead
weight; a great description in front of a body of generic advice is worse -
it costs context and gives nothing back.

## Writing the description

The description is the only text an agent sees before deciding to load the
skill. It is not a summary. It is a routing decision, written for a reader
who has the user's message and a list of thirty other descriptions.

The pattern the existing skills follow:

1. **What it does**, third person, active, one sentence. Name the concrete
   outputs, not the theme. "Sets up Python projects with the modern uv
   toolchain - uv for packages, ruff for lint and format, pytest for tests"
   routes; "helps with Python tooling" does not.
2. **When to use it**, as a list of concrete situations that runs wide.
   Cover the phrasings a user actually types, including the ones that never
   name the tool: someone who says "turn this script into a package" is
   asking for the Python project skill without using any of its keywords.
3. **The keyword surface** - the file names, tool names, and jargon that
   should pull it in (`pyproject.toml`, `SKILL.md`, `marketplace.json`).
4. **When not to use it**, one clause, if there is a near neighbor it keeps
   getting confused with. This is the highest-value sentence in a repo with
   several skills, and the one most often left out.

Rules of thumb:

- **Third person, no "you".** It is read by an agent about a skill, not
  addressed to the user.
- **Length: roughly 400-900 chars.** The cap is 1024. Under ~200 chars there
  is usually not enough trigger surface to route reliably.
- **Include the negative cases the author already knows about.** The
  `new-python-project` description ends by excluding "add a dependency to an
  already-configured project" - that exclusion is worth more than another
  positive example, because it is where the skill would otherwise misfire.
- **No colons in unquoted values.** ` - ` reads the same and cannot break the
  YAML parse.

Three failure modes to check the draft against:

| Failure | Symptom | Fix |
|---|---|---|
| Too vague | Never fires; the agent solves it from general knowledge | Add concrete outputs and trigger words |
| Too narrow | Fires only when the user names the tool | Add the phrasings that describe the goal, not the tool |
| Too broad | Fires on unrelated requests, crowding out siblings | Add the "do not use it for" clause |

## Writing the body

### Shape

```
# Title

One or two sentences: what this produces, and what "done" means.

## Before you <verb>       <- what to ask, and what not to ask
## Step 1 - ...            <- numbered, imperative, in execution order
## Step N - Verify         <- commands that must go green
## Step N+1 - Report       <- what to tell the user
## Gotchas                 <- only non-obvious, outcome-changing specifics
```

### Rules

- **Imperative voice, addressed to the agent.** "Run every command that
  applies. Read each failure, fix it, run again."
- **A table at every real decision point.** Situation in the left column,
  command or location in the right. Prose that describes four options makes
  the agent re-derive the mapping; a table hands it over.
- **Say what happens when it goes wrong.** The expected non-failures are as
  load-bearing as the happy path: a first `pre-commit` run that exits
  non-zero *because* it reformatted files is a pass, and an agent that does
  not know that will "fix" it wrongly.
- **End with verification, not creation.** Every skill that produces files
  should have a step whose commands must exit clean, and an explicit "do not
  report success with a red command in the transcript".
- **Explain why, once, where it changes a decision.** "Use `ty` - same team
  as uv and ruff, so the toolchain moves together; switch to mypy when the
  project needs plugins" tells the agent how to handle the case the author
  did not enumerate. Reasons that do not change a decision are filler.
- **Wrap at roughly 76 characters** to match the existing files.

### The Gotchas section

This is where the value concentrates. It holds what an agent gets wrong when
left to its own judgment - not general best practice.

A gotcha earns its place if it is: silent (parses fine, fails later),
expensive to undo (a layout decision), counterintuitive (the check passes
because nothing was checked), or version-specific (a renamed hook id, a
deprecated alias). Lead with the rule in bold, then the mechanism, then the
fix:

> **Never place a key in `pyproject.toml` by appending to the end of the
> file.** TOML scopes a bare key to the most recent table header, so
> `requires-python` appended after a `[tool.ruff.lint]` section becomes a
> ruff setting that ruff ignores, while `[project]` still has none. It parses
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

When splitting, leave a pointer that states the payoff, so an agent under
time pressure does not skip it: "Read `references/configs.md` and copy out
the blocks that match - the reasoning for each rule selection is there, and
the defaults are chosen to not fight each other."

References are prose for an agent, not appendices for a human: same
imperative voice, same tables, no "as discussed above".
