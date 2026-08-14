# Packaging: plugins, manifests, and marketplaces

Read this before creating a plugin, renaming one, or editing any manifest or
marketplace file. Adding a skill to an existing plugin does not require any
of it - only the user-facing text noted at the end.

Every rule below is enforced by `scripts/validate.py`, which is what CI runs.

## Repository layout

```
.agents/plugins/marketplace.json     # Codex marketplace
.claude-plugin/marketplace.json      # Claude Code marketplace
plugins/<plugin>/
├── plugin.json                      # portable Agent Plugins 1.0 manifest
├── .claude-plugin/plugin.json       # Claude Code manifest
├── .codex-plugin/plugin.json        # Codex manifest
└── skills/<skill>/SKILL.md
```

Three manifests describe one plugin because three install surfaces read
different files. They are not allowed to disagree.

## The shared fields

`version`, `description`, `author`, `homepage`, `repository`, `license`, and
`keywords` are compared for **strict equality** across all three manifests.
Lists are compared as lists, so `keywords` must match in order too. Change
one, change all three in the same edit.

Additional per-manifest requirements:

| Manifest | Requirements |
|---|---|
| `plugin.json` | `$schema` exactly `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; closed schema - only `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`, `extensions`; `name` matches the directory |
| `.claude-plugin/plugin.json` | `name` matches the directory; shared fields match |
| `.codex-plugin/plugin.json` | `name` matches; strict semver `version`; non-empty `description`; `author.name` required; `skills` exactly `./skills` or `./skills/`; full `interface` block |

`author` accepts only `name`, `email`, and `url`. Anything else is an error.

## The Codex interface block

Required: `displayName`, `shortDescription`, `longDescription`,
`developerName`, `category`, `capabilities`, `defaultPrompt`.

- `category` must be one of the Codex buckets in `CODEX_CATEGORIES`
  (`Productivity`, `Developer Tools`, `Finance`, `Business & Operations`,
  `Data & Analytics`, `Communication`, `Education & Research`, `Creativity`,
  `Other`, `Travel`, `Security`) **and** must equal the `category` on this
  plugin's entry in the Codex marketplace. That constant in
  `scripts/validate.py` is the source of truth - read it rather than this
  list if a category is rejected, since Codex adds buckets over time.
- `capabilities` is a non-empty array of strings; the existing plugins use
  `["Interactive", "Write"]`.
- `defaultPrompt` is 1-3 strings, each at most 128 chars. Write them as
  sentences a user would say.
- `websiteURL`, `privacyPolicyURL`, `termsOfServiceURL` must be absolute
  `https` URLs; `brandColor` must be `#RRGGBB`.

## What validates what

Coverage is asymmetric because Codex publishes no schemas. Do not read the
gaps as oversights.

| File | Published schema | `scripts/validate.py` |
|---|---|---|
| `plugin.json` | Agent Plugins 1.0 | yes |
| `.claude-plugin/plugin.json` | Schemastore `claude-code-plugin-manifest` | yes |
| `.claude-plugin/marketplace.json` | Schemastore `claude-code-marketplace` | yes |
| `.codex-plugin/plugin.json` | none published | yes - only checker |
| `.agents/plugins/marketplace.json` | none published | yes - only checker |
| `skills/*/SKILL.md` | `skills-ref` (Agent Skills) | yes |

## Marketplace entries

Both marketplaces must list every plugin directory, and must not list one
that does not exist. The two files use different shapes - do not copy an
entry from one into the other.

Claude Code (`.claude-plugin/marketplace.json`) requires `name`, `owner`, and
`plugins` at the top level, where `owner` is an object with a non-empty
`name` and optional `email` and `url`. Both the published schema and
`scripts/validate.py` enforce this. Each entry:

```json
{
  "name": "<plugin>",
  "source": "./plugins/<plugin>",
  "category": "development"
}
```

`source` is a plain string and must be exactly `./plugins/<name>`. Its
`category` is free-form and lowercase - the published schema types it as a
plain string with no enum, and `scripts/validate.py` only requires it to be
non-empty when present. It is unrelated to the Codex category, which *is* a
closed set. Do not copy one into the other.

Codex (`.agents/plugins/marketplace.json`):

```json
{
  "name": "<plugin>",
  "source": { "source": "local", "path": "./plugins/<plugin>" },
  "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
  "category": "Developer Tools"
}
```

`installation` is one of `NOT_AVAILABLE`, `AVAILABLE`,
`INSTALLED_BY_DEFAULT`; `authentication` is `ON_INSTALL` or `ON_USE`.

## Creating a new plugin

The plugin name must be 1-64 chars of lowercase letters, digits, `.` and
`-`, starting and ending alphanumeric, with no `--` or `..`, and must match
its directory name.

1. `plugins/<name>/skills/<skill>/SKILL.md` - at least one skill, or
   `scripts/validate.py` reports "contains no skills".
2. `plugins/<name>/plugin.json` - copy the shape from an existing plugin and
   replace every field. Leave no `[TODO:` markers; they are a hard error.
3. `plugins/<name>/.claude-plugin/plugin.json` - same shared fields, plus
   `"$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json"`.
4. `plugins/<name>/.codex-plugin/plugin.json` - same shared fields, plus
   `skills` and the full `interface` block.
5. Add an entry to both marketplaces, in the shapes above.
6. Update the layout tree and the install commands in `README.MD`.
7. Run all three validators from Step 6 of `SKILL.md`.

## Constraints that apply to the whole plugin tree

- **No symlinks anywhere under `plugins/`.** Package paths must stay within
  the plugin root, and any symlink is reported as an error.
- **`SKILL.md` must be a regular file** in each skill directory.
- **`skills/` must exist and contain at least one directory.**
- **Versions are strict semver.** `1.0` fails; `1.0.0` passes.

## When only adding a skill to an existing plugin

No manifest change is required to pass validation, but three pieces of
user-facing text go stale silently:

- `keywords` - shared across all three manifests, so any change is a
  three-file edit.
- `interface.shortDescription` / `longDescription` / `defaultPrompt` - what a
  user reads on the Codex install surface. If they describe only the plugin's
  first skill, widen them.
- The layout tree in `README.MD`, which names each skill directory.
