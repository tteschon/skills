---
name: new-agent-skill
description: Authors and maintains the agent skills in this repository - a SKILL.md that triggers correctly and passes all three validators, plus the plugin manifests and marketplace entries that scripts/validate.py enforces. Use this skill when the user wants to write a new skill, add one to any existing plugin such as work-skills or fun-skills, scaffold a new plugin in any category, rename or restructure an existing skill, split a long SKILL.md into references, or fix a failing skills validation or CI run. Also use it when the user mentions SKILL.md, the agent skills format, Agent Plugins, marketplace.json, .codex-plugin, .claude-plugin, or skills.sh packaging, and when they ask how skills in this repo are laid out. Do not use it to invoke an existing skill - only to author, package, or repair one.
compatibility: Run from a checkout of the skills repository; needs python3 and uv (for uvx) to run the validators.
---

# New Agent Skill

Turn an idea into a skill directory that does three things: fires when it
should, is worth reading when it does, and passes CI.

The job is not done when `SKILL.md` exists. It is done when Step 6 goes
green and the description has been read cold against the sibling skills.

## Before you write

Ask only what cannot be inferred, in one batch. In clients with structured
questions, use one prompt containing all of them:

1. **What the skill does** - the task, and what "done" looks like for it.
2. **When it should fire** - the sentences a user would actually type. This
   is the raw material for the description, and it is the hardest thing to
   reconstruct later.
3. **Which plugin** - list `plugins/*/` and offer what is actually there, or
   a new plugin. Never assume the set of plugins from memory; it grows.

**Skip any question the user already answered.** "Add a skill to work-skills
that sets up Terraform modules" answers all three. Asking anyway costs a
round trip and tells the user you were not reading.

## Step 1 - Place it

| Situation | Location |
|---|---|
| Fits an existing plugin's theme | `plugins/<plugin>/skills/<name>/` |
| Needs a new theme or audience | New plugin - see `references/packaging.md` |
| Replaces or extends an existing skill | Edit in place; do not fork a near-copy |

Each plugin declares its own theme, so decide fit by reading rather than by
guessing: `.codex-plugin/plugin.json` holds the `shortDescription`,
`longDescription`, and `category` that a user sees at install time. If
widening that text to cover the new skill would make it vague or false, the
skill belongs in a different plugin - or a new one. A new plugin is five
files and two marketplace entries, so do not create one casually, but do not
stuff an unrelated skill into the largest existing plugin either.

This holds for any plugin the repo grows, not just the ones present today.
The only fixed vocabulary is the Codex `category` bucket a new plugin must
pick from; `references/packaging.md` lists the current set.

Directory name rules, checked by three separate validators: lowercase letters,
digits and hyphens only, 1-64 chars, no leading, trailing, or doubled hyphen.
The directory name and the frontmatter `name` must be identical.

## Step 2 - Write the frontmatter

Exactly six keys are permitted. Anything else is an error in `skills-ref` and
a warning in `scripts/validate.py`:

| Key | Required | Rules |
|---|---|---|
| `name` | yes | Matches the directory name exactly |
| `description` | yes | Non-empty, max 1024 chars - the whole triggering surface |
| `compatibility` | no | Max 500 chars; what must exist on the machine |
| `allowed-tools` | no | Narrows the tools the skill may use |
| `license` | no | Only if it differs from the repo's MIT |
| `metadata` | no | Free-form string map |

The description is the only part of the skill an agent sees before deciding
whether to load it. Write it third person and make it carry both halves:
what the skill does, and the concrete situations that should pull it in -
including the words a user would type. Read
`references/writing-style.md` before drafting it; that file has the pattern
the existing descriptions follow and the failure modes on either side of it
(too vague to fire, too narrow to fire, fires on everything).

Keep every value on one line, or continue it on an indented line. The repo's
own validator parses this frontmatter with a small hand-rolled parser, and
`>`/`|` block scalars survive it as literal `>` text in the value. An
unquoted `: ` inside a value is a YAML error - the existing skills use ` - `
where they want a colon.

## Step 3 - Write the body

Read `references/writing-style.md`. It covers the house style these skills
share - imperative steps, a table at every real decision point, a verify
step that must go green, and a Gotchas section that holds only what an agent
would otherwise get wrong.

Two rules worth stating up front, because they are the ones that decide
whether a skill is used or skimmed:

- **Aim for under ~200 lines.** `SKILL.md` is loaded whole. Detail that is
  needed sometimes goes in `references/`, so the common path stays cheap.
- **Write what an agent gets wrong, not what it already knows.** Generic
  advice ("write clear code", "handle errors") is filler that dilutes the
  parts that matter. Every line should change an outcome.

## Step 4 - Supporting files

| Need | Put it in |
|---|---|
| Detail read only in some runs | `references/<topic>.md` |
| Deterministic work better done by code | `scripts/<name>.py` |
| Files the skill copies out verbatim | `assets/` |

Reference them by path relative to the skill directory, and say *when* to
read each one and *why* - "Read `references/configs.md` and copy the blocks
that match" beats a bare link, because an agent that does not know the payoff
will skip it.

Never use a symlink anywhere under a plugin: `scripts/validate.py` treats any
symlink as an error, since package paths must stay inside the plugin root.

## Step 5 - Update the packaging

**Bump the plugin `version` in all three manifests.** This is not
bookkeeping - see the first entry under Gotchas. Adding a skill is a minor
bump (`1.0.0` to `1.1.0`); rewriting one in place is a patch bump.

The rest needs no manifest change to *validate*, but the manifests carry
user-facing text that a new skill can make stale:

- `keywords` in all three of `plugin.json`, `.claude-plugin/plugin.json`, and
  `.codex-plugin/plugin.json` - these must stay byte-identical to each other.
- `interface.shortDescription`, `interface.longDescription`, and
  `interface.defaultPrompt` in `.codex-plugin/plugin.json` - this is the copy
  a user reads on the install surface.
- The layout tree in `README.MD`, which names each skill directory.

Creating a new plugin, renaming one, or changing shared metadata is a
different job with exact field-sync rules. Read `references/packaging.md`
before touching any manifest or marketplace file - the shared fields are
compared for strict equality across three manifests, and the Codex category
is compared against the marketplace entry as well.

## Step 6 - Verify until green

Run all of them. Read each failure, fix it, run again, until every one exits
clean. These are exactly what `.github/workflows/validate.yml` runs, so a
green local run is a green CI run.

```bash
uvx check-jsonschema --schemafile https://agent-plugins.org/schemas/1.0.0/plugin.schema.json plugins/*/plugin.json
uvx check-jsonschema --schemafile https://www.schemastore.org/claude-code-marketplace.json .claude-plugin/marketplace.json
uvx check-jsonschema --schemafile https://www.schemastore.org/claude-code-plugin-manifest.json plugins/*/.claude-plugin/plugin.json
uv run --no-project --with skills-ref==0.1.1 python -m skills_ref.cli validate plugins/<plugin>/skills/<name>
python3 scripts/validate.py
```

The three schema checks need network access. `scripts/validate.py` is
stdlib-only and offline, so run it first when working without a connection -
it catches most structural mistakes on its own.

`scripts/validate.py` prints warnings to stdout and errors to stderr, and
only errors set the exit code. Read the warnings anyway - an unrecognized
frontmatter key shows up there, and it means some clients will ignore it.

Then do the check no validator performs: **read the description cold** beside
the descriptions of every sibling skill in the repo and answer two questions.
Which user sentences pull this skill in? Which sentences would wrongly pull
it in, or pull in a sibling instead? Fix the overlap now; a skill that never
fires is worse than no skill, and one that fires on everything is worse
still.

## Step 7 - Report

Tell the user the path, the description as written, the trigger phrases it is
meant to catch, and any manifest or README text updated alongside it. Do not
commit unless asked.

## Gotchas

These are the mistakes made without being told otherwise. They are specific
to this repository's validators.

- **A new skill that ships without a `version` bump is invisible to everyone
  who already installed the plugin.** Claude Code caches the extracted plugin
  under its version number - `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`.
  Re-adding the marketplace re-clones the repository, so the clone looks
  current and the skill is plainly there on disk, but the cache key did not
  change, so the stale payload is reused and the new skill never loads. Every
  validator passes, CI is green, and the skill simply does not appear. Bump
  `version` in all three manifests in the same commit that adds the skill.
  The local escape hatch is `rm -rf` on that one version directory, but it
  fixes only the machine it is run on.
- **The name must match the directory in three places at once.** Renaming a
  skill means renaming the directory *and* the frontmatter `name`. `skills-ref`
  NFKC-normalizes both before comparing, so visually identical Unicode names
  can still pass - but `scripts/validate.py` compares raw strings and will
  not. Stay in ASCII.
- **`scripts/validate.py` parses frontmatter itself, and its parser is not
  YAML.** It handles `key: value` lines plus indented continuations, nothing
  else. A construct that `strictyaml` accepts can still be misread here -
  block scalars in particular. One line per key, or indented continuation.
- **Shared manifest fields are compared with `!=`, not "compatible with".**
  `version`, `description`, `author`, `homepage`, `repository`, `license`,
  and `keywords` must be identical across the portable, Claude, and Codex
  manifests - including keyword *order*, since the lists are compared
  directly. Change one, change all three.
- **`interface.category` must equal the Codex marketplace entry's
  `category`,** and both must be one of the Codex buckets listed in
  `scripts/validate.py`. The Claude marketplace's `category` is separate,
  lowercase, and unvalidated - do not copy one into the other.
- **`skills` in `.codex-plugin/plugin.json` must be exactly `./skills` or
  `./skills/`.** No other spelling passes, including `skills/`.
- **A literal `[TODO:` anywhere in a manifest is an error.** Scaffolding a
  plugin by copying another one and leaving placeholders will fail CI, by
  design. Fill them in before running the validator.
- **`defaultPrompt` takes 1 to 3 strings, each at most 128 chars.** They are
  the suggested prompts shown at install time, so write them as things a user
  would actually say, not as feature names.
- **The portable `plugin.json` schema is closed.** Only the ten fields in
  `PORTABLE_MANIFEST_FIELDS` are permitted, and `$schema` must be exactly the
  1.0.0 plugin schema URL. Extra keys go in `extensions`, not at the top level.
- **Skill names are namespaced per plugin (`work-skills:foo`), but the
  descriptions all compete in one list.** Two skills in different plugins can
  share a name without failing validation and still confuse every agent that
  loads both. Check for a name or trigger collision across the whole repo,
  not just within the plugin.
