---
name: new-python-project
description: Sets up Python projects with the modern uv toolchain - uv for packages and environments, ruff for lint and format, pytest for tests, ty for type checking, and pre-commit to run them on every commit. Use this skill when the user starts a new Python project, package, CLI, library, or service; when they want to add testing, linting, formatting, or type checking to an existing Python directory; when they ask to turn a script or legacy project into a proper package; or when they mention uv, ruff, pytest, pre-commit, pyproject.toml, or src layout. Also use it when the user asks for a Python project without naming any tooling, or reaches for pip, venv, requirements.txt, poetry, or setup.py - the setup should still go through uv. Do not use it to add a runtime dependency to an already-configured project.
compatibility: Requires uv and git
allowed-tools: Bash(uv init*) Bash(uv add*) Bash(uv sync*) Bash(uv lock*) Bash(uv python*)
---

# New Python Project

Turn a directory into a working uv project: dependencies locked, tests
running, lint and format clean, types checked, and all of it wired into a
pre-commit hook so it stays that way.

The job is not done when the files exist. It is done when Step 5 goes green.

## Before you scaffold

Ask the user the things you genuinely cannot infer, in one batch (in Claude
Code, one `AskUserQuestion` call with multiple questions):

1. **Location** - which directory, or a new subdirectory of the cwd.
2. **Package or application** - packages are imported or installed as a
   command; applications are just run. This one is load-bearing, see Gotchas.
3. **Tooling depth** - full (ruff + pytest + ty + pre-commit), or lighter.

**Skip any question the user already answered.** "Make me a CLI called foo in
~/src" answers all three well enough to proceed. Asking anyway costs a round
trip and tells the user you were not reading. Ask about what is actually
undetermined, and if nothing is, just build.

## Step 1 - Scaffold or adopt

Pick one. The flag is not cosmetic - it decides the layout and whether the
project is installable.

| Situation | Command |
|---|---|
| Library, distributed or imported | `uv init --lib <name>` |
| CLI or packaged application | `uv init --package <name>` |
| Script, service, or one-off app | `uv init <name>` |
| Existing directory that already has code | `uv init --bare` |

`--lib` implies `--package` and additionally writes a `py.typed` marker.
Everything except `--bare` also runs `git init`, writes a `.gitignore`, and
pins a `.python-version` - do not redo that work.

For the existing-directory case, `--bare` writes only `pyproject.toml` and
leaves the tree alone. Read what is already there before changing anything:
an existing `requirements.txt` becomes `uv add` calls, an existing `setup.py`
means the metadata moves into `pyproject.toml`.

Everyday commands, for this session and for the summary in Step 6:

| Task | Command |
|---|---|
| Add a dependency | `uv add <package>` |
| Add a dev dependency | `uv add --dev <package>` |
| Run anything in the env | `uv run <command>` |
| Run a tool without installing it | `uvx <tool>` |
| Pin the interpreter | `uv python pin <version>` |

## Step 2 - Add the toolchain

```bash
uv add --dev ruff pytest ty
```

Use `ty` for type checking - it is from the same team as uv and ruff, so the
whole toolchain moves together. Switch to mypy instead when the project needs
type-checker plugins (Django, SQLAlchemy, Pydantic) or a mature strict mode;
`ty` is still beta and will not have them.

pre-commit is not a project dependency. Run it with `uvx pre-commit` so it
does not end up in the lockfile of every project that uses it.

## Step 3 - Configure

Read `references/configs.md` and copy out the blocks that match the choices
from "Before you scaffold" - it has the `pyproject.toml` tables, the
`.pre-commit-config.yaml`, and the two layouts. Read it now rather than
writing config from memory: the reasoning for each rule selection is there,
and the defaults are chosen to not fight each other.

Its first section, "Editing pyproject.toml", covers how to merge these blocks
into the file uv already wrote without corrupting it. Read that part even if
you only need one config block - the two failure modes it describes are the
ones that cost the most time to find later.

Skip the rest only if the user asked for something so minimal that `uv init`'s
output is already the answer.

## Step 4 - Wire pre-commit

Write `.pre-commit-config.yaml` with `rev: v0.0.0` on every repo as a
placeholder, then let pre-commit fill in real versions:

```bash
uvx pre-commit autoupdate
uvx pre-commit install
```

`autoupdate` rewrites every `rev` to that repo's latest tag, reporting each
one as `updating v0.0.0 -> v6.0.0`. Never hand-write a version - a pinned
`rev` copied from documentation is stale the moment the tool releases.
Confirm no `v0.0.0` survives in the file before moving on; if `autoupdate`
fails on a repo, get the tag with
`git ls-remote --tags --sort=-v:refname <repo-url> | head -1`.

`install` is what puts the hook in `.git/hooks`. Without it the config file
sits there and nothing ever runs.

## Step 5 - Verify until green

Run every command that applies. Read each failure, fix it, run again. Repeat
until all of them exit clean.

```bash
uv run python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest
git add -A && uvx pre-commit run --all-files
```

The `tomllib` line goes first because a malformed `pyproject.toml` makes every
command after it fail with an unrelated-looking error.

The `git add -A` is not optional. `pre-commit run --all-files` means all
*tracked* files, and on a freshly scaffolded project nothing is staged yet -
so every hook reports "no files to check", the run exits 0, and it looks like
a pass when nothing was checked at all. Stage first or the check is theater.

Two expected non-failures:

- The first real `pre-commit run --all-files` reformats files and exits
  non-zero because of it ("files were modified by this hook"). Stage the
  changes and re-run; the second run passes.
- On a fresh `uv init` app there is a `main.py` and no tests, so pytest exits
  with "no tests ran". Write one real test before calling this green - a test
  suite that has never run is not a test suite.

Do not report success with a red command in the transcript. If something
cannot be made to pass, say which one and why.

## Step 6 - Report

Tell the user what was created, which type checker was chosen and why, and
the four commands they will actually type:

```bash
uv run pytest         # tests
uv run ruff check .   # lint
uv run ruff format .  # format
uv add <package>      # dependencies
```

## Gotchas

These are the mistakes made without being told otherwise. They are not
general advice.

- **`uv add`, never `pip install`. `uv run <cmd>`, never a hand-activated
  `.venv`.** `uv run` re-syncs the environment against `uv.lock` first; an
  activated shell silently drifts from it.
- **`uv init --package` vs plain `uv init` is expensive to undo, and the
  difference shows up in the test suite.** Plain `uv init` writes no build
  system, so the project is never installed into its own environment: a test
  doing `from main import main` fails with `ModuleNotFoundError`, and
  `[project.scripts]` is inert - `uv run <command>` reports "Failed to
  spawn". With `--package` the project is installed into the venv via a
  `.pth` file and both work. Decide before scaffolding. If it was decided
  wrong, the fix is `[tool.uv] package = true` plus a `[build-system]` and
  moving the code under `src/` - not a re-run of `uv init`, which will not
  overwrite an existing project.
- **Never place a key in `pyproject.toml` by appending to the end of the
  file.** TOML scopes a bare key to the most recent table header, so
  `requires-python` appended after a `[tool.ruff.lint]` section becomes a ruff
  setting that ruff ignores, while `[project]` still has none. It parses
  cleanly and fails silently. Find the table, then insert.
- **Never hand-edit `[project.dependencies]` or `[dependency-groups]`.** uv
  owns them. Editing them directly leaves `uv.lock` stale, so the manifest and
  the installed environment disagree until something forces a re-sync. Use
  `uv add`, `uv add --dev`, `uv add --group <name>`, and `uv remove`.
- **`uv run` is what keeps the environment honest.** It syncs against
  `pyproject.toml` and `uv.lock` before running the command. A `pytest`
  invoked any other way - a global install, `uvx pytest`, a shell whose venv
  has gone stale - runs against whatever happens to be installed. Adding a
  dependency and then running the venv's own `pytest` directly will not see
  it; `uv run pytest` syncs first and does.
- **`uv add --dev` writes `[dependency-groups] dev`.** That is the current
  form. Do not hand-write `[project.optional-dependencies]` with a `dev`
  extra; it is the older convention and uv will not manage it.
- **In `.pre-commit-config.yaml` the hook id is `ruff-check`.** Plain `ruff`
  still resolves but is a deprecated alias. Put `ruff-check` (with `--fix`)
  *before* `ruff-format`: fixes can change formatting, so the reverse order
  leaves a dirty tree after the hook "passes".
- **Do not put `--cov` in pytest's `addopts`.** It makes every single test
  run pay for coverage instrumentation and clutters `pytest -k` debugging.
  Keep coverage as its own command.
- **Set `requires-python` and let ruff infer `target-version` from it.**
  Ruff reads `project.requires-python` when `target-version` is unset. Setting
  both invites them to disagree, and `target-version` silently wins.
- **Commit `uv.lock` for applications and CLIs.** For libraries it is
  optional - it pins contributors' environments but has no effect on anyone
  installing the published package.
- **`ty` is beta (0.x).** On spurious errors, or when the project needs
  plugin support, switch to mypy rather than adding suppressions to work
  around a young checker.
