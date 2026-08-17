> **Note:** This is a public repository to share some of my AI agent skills.

[![Install the tteschon skills pack from skills.sh](https://img.shields.io/badge/skills.sh-install%20pack-000000?logo=vercel&logoColor=white)](https://www.skills.sh/p/k9F32rDgRDOqfsd3)

# Skills

> Skills are reusable capabilities for AI agents. They provide procedural knowledge that helps agents accomplish specific tasks more effectively. Skills can include code generation patterns, domain expertise, tool integrations, and more.

The skills in this repository follow the open source [agent skills format](http://agentskills.io/specification), and they are packaged as [Agent Plugins 1.0](https://agent-plugins.org/specification) plugins.

## Layout

```
.agents/plugins/marketplace.json       # Codex marketplace
.claude-plugin/marketplace.json        # Claude Code marketplace
plugins/
├── fun-skills/            # Fun and creative agent skills
│   ├── plugin.json
│   ├── .codex-plugin/plugin.json
│   ├── .claude-plugin/plugin.json
│   └── skills/chompsaw-project-designer/
└── work-skills/           # Productivity and work-focused agent skills
    ├── plugin.json
    ├── .codex-plugin/plugin.json
    ├── .claude-plugin/plugin.json
    └── skills/
        ├── new-agent-skill/
        ├── new-python-project/
        └── obsidian-vault/
```

Each plugin keeps a portable Agent Plugins manifest at its root plus native
Codex and Claude Code manifests for their respective install surfaces.

## Codex

Add this repository as a Codex marketplace:

```bash
codex plugin marketplace add tteschon/skills
```

Then install either or both plugins:

```bash
codex plugin add fun-skills@tteschon-agent-skills
codex plugin add work-skills@tteschon-agent-skills
```

Start a new Codex session after installation so the bundled skills are loaded.

## Claude Code

You can register this repository as a Claude Code Plugin marketplace by running the following command in Claude Code:

```
/plugin marketplace add tteschon/skills
```

Then, to install a specific set of skills:

1. Select `Browse and install plugins`
2. Select `tteschon-agent-skills`
3. Select `fun-skills` or `work-skills`
4. Select `Install now`

Alternatively, directly install either Plugin via:

```
/plugin install fun-skills@tteschon-agent-skills
/plugin install work-skills@tteschon-agent-skills
```

## Other agents

`plugins/fun-skills` and `plugins/work-skills` are self-contained [Agent Plugins 1.0](https://agent-plugins.org/specification) packages, so any client that supports the spec can load either directory straight from a clone:

```
git clone https://github.com/tteschon/skills
```
Then point your agent at `skills/plugins/work-skills` (or `fun-skills`) using its own plugin-install command.

## Validation

```
python3 scripts/validate.py
```
Checks each plugin against the Agent Plugins 1.0 manifest rules, validates the
Codex and Claude Code manifests and marketplaces, keeps shared metadata in
agreement, and validates every `SKILL.md` against the Agent Skills format. Runs
on every push via [.github/workflows/validate.yml](.github/workflows/validate.yml),
which additionally checks the Claude Code marketplace and plugin manifests
against their published Schemastore schemas.

## License

[MIT](LICENSE)
