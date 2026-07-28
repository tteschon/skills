# Configuration templates

Copy the blocks that match the choices made in "Before you scaffold". Every
setting here is chosen for a reason and the reason is stated - if a project
needs something different, change it deliberately rather than copying past it.

## Contents

- [Editing pyproject.toml](#editing-pyprojecttoml)
- [pyproject.toml - ruff](#pyprojecttoml---ruff)
- [pyproject.toml - pytest](#pyprojecttoml---pytest)
- [pyproject.toml - ty](#pyprojecttoml---ty)
- [pyproject.toml - mypy, when ty is not the right fit](#pyprojecttoml---mypy-when-ty-is-not-the-right-fit)
- [pyproject.toml - packaging and CLI entry points](#pyprojecttoml---packaging-and-cli-entry-points)
- [.pre-commit-config.yaml](#pre-commit-configyaml)
- [Layouts](#layouts)
- [Adopting an existing project](#adopting-an-existing-project)

## Editing pyproject.toml

Every block below gets merged into one file, so read this before applying any
of them. TOML fails in two directions: loudly, with a parse error that breaks
every tool at once, or silently, with a setting that lands in the wrong table
and is simply never read.

### Who owns which table

uv rewrites these. Change them with commands, never by hand - a hand-edit is
not reflected in `uv.lock`, so the environment and the manifest disagree until
the next `uv sync`:

| Table | Command that owns it |
|---|---|
| `[project.dependencies]` | `uv add` / `uv remove` |
| `[dependency-groups]` | `uv add --dev`, `uv add --group <name>` |
| `[project.optional-dependencies]` | `uv add --optional <extra>` |
| `[tool.uv.sources]` | `uv add --git`, `--path`, `--branch` |
| `[project] version` | `uv version` |

Everything else is yours to edit directly: `[tool.ruff]` and its sub-tables,
`[tool.pytest.ini_options]`, `[tool.ty]`, `[tool.mypy]`, `[project.scripts]`,
and `requires-python`.

### Merging a block

1. **Search for the exact table header before writing it.** If
   `[tool.ruff.lint]` already exists, add keys under it. If it does not, append
   the header and its keys together.
2. **Never write a table header twice.** TOML: "Like keys, you cannot define a
   table more than once. Doing so is invalid." Two `[tool.ruff.lint]` headers
   is a parse error, and since everything lives in one file, that error takes
   ruff, pytest, ty, and uv down together.
3. **A key appended to the end of the file joins the last table header, not
   the one you meant.** TOML scopes keys to the most recent header "until the
   next header or EOF". Appending `requires-python = ">=3.13"` to a file whose
   last section is `[tool.ruff.lint]` produces a perfectly valid document in
   which ruff has a meaningless `requires-python` setting and `[project]` still
   has none. Nothing errors. This is the most common way to get it wrong -
   always place a key by finding its table, never by appending to the file.
4. **Parent and child tables are different tables.** `line-length` goes in
   `[tool.ruff]`, `select` goes in `[tool.ruff.lint]`. Declaring the child
   first and the parent later is legal, so fix misplaced keys by moving them
   rather than restructuring the file.
5. **Double brackets mean an array of tables.** `[[tool.mypy.overrides]]`
   repeats legally - each occurrence appends an element. Single brackets in
   that position would be the duplicate-table error from rule 2.

### Edit as text, not through a parser

Apply changes as targeted text edits. Do not read-modify-write the file
through a TOML library: `tomllib` is read-only by design, and round-tripping
through a general parser drops comments and reorders keys, producing a diff
that touches lines nobody meant to change. `uv add` edits in place and
preserves surrounding formatting; a naive rewrite does not.

### Validate after editing

```bash
uv run python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('pyproject.toml OK')"
```

Run this inside `uv run` rather than with a bare `python3` - `tomllib` is
stdlib only on 3.11+, and `uv run` uses the interpreter the project pinned.
The `check-toml` pre-commit hook covers the same ground, but only at commit
time, which is too late to help while editing.

A clean parse proves the syntax, not the placement. For the silent failure in
rule 3, check that the key landed where intended:

```bash
uv run python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(sorted(d['project']))"
```

### The [tool.uv] table

uv's own settings, distinct from the tables it manages on your behalf:

- `package = false` - install dependencies but do not build the project
  itself. This is what makes a plain `uv init` app a "virtual" project.
  Setting `package = true` and adding a `[build-system]` is the supported way
  to make an application installable without re-scaffolding.
- `default-groups = ["dev"]` - which dependency groups sync by default. Add a
  group here after `uv add --group docs ...`, or it only installs on request.
- `required-version = ">=0.9"` - refuse to run under an older uv. Worth
  setting on a team project once the setup depends on recent uv behavior.

### Conventional order

`[build-system]`, `[project]`, `[project.scripts]`, `[dependency-groups]`,
then `[tool.*]`. TOML does not care, but a consistent order keeps `uv add`'s
insertions and hand edits from interleaving into noisy diffs.

## pyproject.toml - ruff

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]
```

What each selector buys, so the list can be trimmed with intent:

- `F` - pyflakes. Real bugs: undefined names, unused imports. Non-negotiable.
- `E` - pycodestyle errors. Style violations the formatter does not fix.
- `I` - isort. Import ordering, applied automatically by `--fix`. Removes a
  whole category of pointless diff noise.
- `UP` - pyupgrade. Rewrites to the syntax available in `requires-python`.
  This is why `requires-python` has to be set correctly.
- `B` - flake8-bugbear. Catches mutable default arguments, loop-variable
  capture in closures, and similar traps that are legal but almost never
  intended.
- `SIM` - flake8-simplify. Collapses redundant conditionals and context
  managers. The most opinionated of the six; drop it first if a team objects.

`E501` (line too long) is ignored because `ruff format` owns line width.
Leaving it on means the linter complains about lines the formatter has
deliberately declined to break - long URLs in strings, long comments - and
there is no fix that satisfies both.

Do not set `line-length` unless the project has a house standard; the default
of 88 is what `ruff format` targets. Do not set `target-version` either - ruff
infers it from `project.requires-python`, and setting both lets them disagree.

Set `requires-python` in `[project]` if `uv init` did not, since three other
settings key off it:

```toml
[project]
requires-python = ">=3.13"
```

## pyproject.toml - pytest

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
```

`testpaths` stops pytest from walking `.venv` and the source tree looking for
tests. `-ra` prints a short reason line for everything that was not a plain
pass, which is the difference between "3 skipped" and knowing why.

Coverage is deliberately not in `addopts` - see the Gotchas in `SKILL.md`.
Add it when the user asks, as its own command:

```bash
uv add --dev pytest-cov
uv run pytest --cov=src --cov-report=term-missing
```

`--cov=src` assumes src layout. For a flat application, point it at the module
or package name instead.

## pyproject.toml - ty

`ty` needs no configuration for a standard layout. Add a block only when
there is something to say:

```toml
[tool.ty.environment]
root = ["./src"]
```

`root` is worth setting for src layout so first-party imports resolve the same
way they do at runtime. Everything else - `[tool.ty.rules]`,
`[tool.ty.src]`, `[tool.ty.terminal]` - should stay unset until a real
diagnostic makes the case for it.

Run it with `uv run ty check`.

## pyproject.toml - mypy, when ty is not the right fit

Use mypy when the project depends on type-checker plugins (Django,
SQLAlchemy, Pydantic) or needs a strict mode that has been shaken out for
years. Replace `ty` with `mypy` in the `uv add --dev` line and use:

```toml
[tool.mypy]
strict = true
```

Do not set `python_version` here either - mypy reads `requires-python`.

`strict = true` on a greenfield project is cheap; on an existing codebase it
produces hundreds of errors at once. For adoption, start without it and turn
on individual flags, or scope strictness per-module:

```toml
[[tool.mypy.overrides]]
module = "mypackage.legacy.*"
ignore_errors = true
```

Run it with `uv run mypy src`.

## pyproject.toml - packaging and CLI entry points

`uv init --package` and `uv init --lib` write the build system already. A CLI
also needs an entry point, which maps a command name to a function:

```toml
[project.scripts]
mytool = "mypackage.cli:main"
```

The value is `module.path:function`. After adding it, `uv run mytool` works;
so does `mytool` on the PATH of anyone who installs the package.

This does nothing in a project scaffolded with plain `uv init` - there is no
build system, so the project is never installed and the script is never
generated. That is the fork described in the Gotchas.

`uv init --lib` writes `src/<package>/py.typed` for you. Add it by hand if a
`--package` project is meant to ship type information, otherwise consumers'
type checkers ignore the annotations entirely.

## .pre-commit-config.yaml

Write this with the `v0.0.0` placeholders intact, then run
`uvx pre-commit autoupdate` to fill in real tags.

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v0.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.0.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/astral-sh/ty-pre-commit
    rev: v0.0.0
    hooks:
      - id: ty
```

Notes:

- `ruff-check` runs before `ruff-format` because `--fix` can leave code the
  formatter still wants to reflow. Reversed, the tree is dirty after a
  "passing" hook run.
- `check-toml` is here and not in most published examples because this project
  keeps all its configuration in `pyproject.toml`. A malformed table breaks
  every tool at once.
- The `ty` hook checks the whole project rather than the changed files, by
  design: an edit to `b.py` can introduce a diagnostic in `a.py`.
- Using mypy instead of ty? There is no official mypy pre-commit repo that
  sees the project's dependencies. Use a local hook so it runs inside the uv
  environment:

  ```yaml
    - repo: local
      hooks:
        - id: mypy
          name: mypy
          entry: uv run mypy src
          language: system
          types: [python]
          pass_filenames: false
  ```

Running pytest as a pre-commit hook is intentionally left out. It makes every
commit as slow as the test suite, which is how people learn to use
`--no-verify`. Tests belong in CI.

## Layouts

Package (`uv init --package` or `--lib`) - importable, installable, and what
a CLI needs:

```
<project>/
  src/<package_name>/
    __init__.py
    py.typed               # --lib only, or added by hand
  tests/
  pyproject.toml
  uv.lock                  # commit this
  .pre-commit-config.yaml
  .python-version
  README.md
```

Application (plain `uv init`) - run directly, never installed:

```
<project>/
  main.py
  tests/
  pyproject.toml
  uv.lock                  # commit this
  .pre-commit-config.yaml
  .python-version
  README.md
```

Both are starting points. The one thing not to improvise is moving between
them after the fact - converting an application to a package means adding a
build system, relocating the code under `src/`, and fixing every import in
the test suite.

## Adopting an existing project

`uv init --bare` writes `pyproject.toml` and nothing else. Then:

- **`requirements.txt`** - read it, then `uv add` the runtime pins and
  `uv add --dev` the tooling. Delete the file once `uv.lock` exists;
  two sources of truth is worse than either one.
- **`setup.py` or `setup.cfg`** - move name, version, `requires-python`,
  dependencies, and entry points into `pyproject.toml`, then delete. Keep
  `setup.py` only if it compiles extension modules.
- **Poetry** - `[tool.poetry.dependencies]` uses caret ranges (`^1.2`) that
  have no PEP 508 equivalent. Translate `^1.2` to `>=1.2,<2.0` rather than
  assuming uv understands it.
- **An existing `.venv`** - delete it. `uv run` builds and manages its own.
- **Existing lint config** (`.flake8`, `setup.cfg`, `.isort.cfg`) - ruff
  replaces all of it. Read the ignore lists before deleting them, since they
  usually encode real exceptions worth carrying over into `[tool.ruff.lint]`.

Expect the first `ruff check` on an adopted codebase to produce a large
number of findings. Run `uv run ruff check --fix` first and re-check; what
remains is the list worth reading with the user rather than fixing silently.
