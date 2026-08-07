#!/usr/bin/env python3
"""Validate the portable, Codex, Claude Code, and Agent Skills packaging.

Checks every plugin under plugins/ for:
  - a conformant Agent Plugins 1.0 root manifest
  - native Codex and Claude Code manifests with matching shared metadata
  - matching entries in the Codex and Claude Code marketplaces
  - skills that conform to the Agent Skills frontmatter and layout rules

Stdlib only, so CI needs no dependencies. Exits non-zero on any error.

Usage: python3 scripts/validate.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

# Agent Plugins 1.0 section 5.2: the portable manifest schema is closed.
PORTABLE_MANIFEST_FIELDS = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}
CODEX_MANIFEST_FIELDS = {
    "id", "name", "version", "description", "author", "homepage",
    "repository", "license", "keywords", "skills", "hooks", "apps",
    "mcpServers", "interface",
}
# Observed across every plugin in the openai/plugins curated marketplace rather
# than taken from a published schema. Extend this if Codex adds a bucket.
CODEX_CATEGORIES = {
    "Productivity", "Developer Tools", "Finance", "Business & Operations",
    "Data & Analytics", "Communication", "Education & Research", "Creativity",
    "Other", "Travel", "Security",
}
CODEX_INTERFACE_FIELDS = {
    "displayName", "shortDescription", "longDescription", "developerName",
    "category", "capabilities", "websiteURL", "privacyPolicyURL",
    "termsOfServiceURL", "brandColor", "composerIcon", "logo", "logoDark",
    "screenshots", "defaultPrompt", "default_prompt",
}
CODEX_INTERFACE_REQUIRED = {
    "displayName", "shortDescription", "longDescription", "developerName",
    "category",
}
SKILL_FIELDS = {
    "name", "description", "license", "compatibility", "metadata",
    "allowed-tools",
}
SHARED_MANIFEST_FIELDS = {
    "version", "description", "author", "homepage", "repository", "license",
    "keywords",
}
INSTALLATION_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
AUTHENTICATION_POLICIES = {"ON_INSTALL", "ON_USE"}
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

errors: list[str] = []
warnings: list[str] = []


def error(where: Path, msg: str) -> None:
    errors.append(f"{where.relative_to(REPO)}: {msg}")


def warn(where: Path, msg: str) -> None:
    warnings.append(f"{where.relative_to(REPO)}: {msg}")


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        error(path, "missing")
        return None
    except json.JSONDecodeError as exc:
        error(path, f"invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        error(path, "top level must be an object")
        return None
    return data


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_plugin_name(name: Any) -> bool:
    return (
        isinstance(name, str)
        and 1 <= len(name) <= 64
        and re.fullmatch(r"[a-z0-9.-]+", name) is not None
        and name[0].isalnum()
        and name[-1].isalnum()
        and "--" not in name
        and ".." not in name
    )


def valid_skill_name(name: Any) -> bool:
    return (
        isinstance(name, str)
        and 1 <= len(name) <= 64
        and re.fullmatch(r"[a-z0-9-]+", name) is not None
        and not name.startswith("-")
        and not name.endswith("-")
        and "--" not in name
    )


def reject_todo_markers(value: Any, path: Path, location: str = "$") -> None:
    if isinstance(value, str):
        if "[TODO:" in value:
            error(path, f"{location} contains a `[TODO: ...]` placeholder")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_todo_markers(item, path, f"{location}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_todo_markers(item, path, f"{location}.{key}")


def parse_frontmatter(path: Path) -> dict[str, str] | None:
    """Parse the flat scalar frontmatter used by the skills in this repository."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        error(path, "missing YAML frontmatter")
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        error(path, "unterminated YAML frontmatter")
        return None
    fields: dict[str, str] = {}
    key: str | None = None
    for line in lines[1:end]:
        if not line.strip():
            continue
        if line[0] in " \t" and key:
            fields[key] += " " + line.strip()
            continue
        head, sep, tail = line.partition(":")
        if not sep:
            error(path, f"frontmatter line is not `key: value`: {line!r}")
            continue
        key = head.strip()
        if key in fields:
            error(path, f"duplicate frontmatter key {key!r}")
        fields[key] = tail.strip()
    return fields


def check_skill(skill_dir: Path) -> None:
    md = skill_dir / "SKILL.md"
    if not md.is_file() or md.is_symlink():
        error(skill_dir, "no SKILL.md regular file")
        return
    fields = parse_frontmatter(md)
    if fields is None:
        return

    name = fields.get("name")
    if not valid_skill_name(name):
        error(md, f"name {name!r} violates the Agent Skills name rules")
    elif name != skill_dir.name:
        error(md, f"name {name!r} must match directory {skill_dir.name!r}")

    description = fields.get("description", "")
    if not description:
        error(md, "frontmatter `description` is required and must be non-empty")
    elif len(description) > 1024:
        error(md, f"description is {len(description)} chars, max 1024")

    compatibility = fields.get("compatibility")
    if compatibility is not None and not 1 <= len(compatibility) <= 500:
        error(md, "compatibility must be between 1 and 500 chars")

    for key in sorted(set(fields) - SKILL_FIELDS):
        warn(md, f"frontmatter key {key!r} is not defined by the Agent Skills spec")


def check_author(path: Path, author: Any, *, required: bool) -> None:
    if author is None and not required:
        return
    if not isinstance(author, dict):
        error(path, "`author` must be an object")
        return
    unknown = set(author) - {"name", "email", "url"}
    if unknown:
        error(path, f"author contains unsupported fields: {sorted(unknown)}")
    if required and not non_empty_string(author.get("name")):
        error(path, "`author.name` must be a non-empty string")
    for key in ("name", "email", "url"):
        if key in author and not non_empty_string(author[key]):
            error(path, f"`author.{key}` must be a non-empty string")


def check_portable_manifest(plugin_dir: Path) -> dict[str, Any] | None:
    path = plugin_dir / "plugin.json"
    manifest = load_json(path)
    if manifest is None:
        return None
    reject_todo_markers(manifest, path)
    if manifest.get("$schema") != PLUGIN_SCHEMA:
        error(path, f"$schema must be exactly {PLUGIN_SCHEMA}")
    for key in sorted(set(manifest) - PORTABLE_MANIFEST_FIELDS):
        error(path, f"{key!r} is not permitted by the closed portable schema")
    name = manifest.get("name")
    if not valid_plugin_name(name):
        error(path, f"name {name!r} violates the Agent Plugins name rules")
    elif name != plugin_dir.name:
        error(path, f"name {name!r} must match directory {plugin_dir.name!r}")
    if "version" in manifest and (
        not non_empty_string(manifest["version"])
        or SEMVER.fullmatch(manifest["version"]) is None
    ):
        error(path, "`version` must use semantic versioning")
    if "description" in manifest and not non_empty_string(manifest["description"]):
        error(path, "`description` must be a non-empty string")
    check_author(path, manifest.get("author"), required=False)
    if "keywords" in manifest and (
        not isinstance(manifest["keywords"], list)
        or not all(non_empty_string(value) for value in manifest["keywords"])
    ):
        error(path, "`keywords` must be an array of non-empty strings")
    if "extensions" in manifest and not isinstance(manifest["extensions"], dict):
        error(path, "`extensions` must be an object")
    return manifest


def check_https_url(path: Path, field: str, value: Any) -> None:
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        error(path, f"`{field}` must be an absolute https URL")


def check_codex_interface(path: Path, interface: Any) -> None:
    if not isinstance(interface, dict):
        error(path, "`interface` must be an object")
        return
    unknown = set(interface) - CODEX_INTERFACE_FIELDS
    if unknown:
        error(path, f"interface contains unsupported fields: {sorted(unknown)}")
    for field in CODEX_INTERFACE_REQUIRED:
        if not non_empty_string(interface.get(field)):
            error(path, f"`interface.{field}` must be a non-empty string")
    category = interface.get("category")
    if non_empty_string(category) and category not in CODEX_CATEGORIES:
        error(path, f"`interface.category` {category!r} is not a Codex category")
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities or not all(
        non_empty_string(value) for value in capabilities
    ):
        error(path, "`interface.capabilities` must be a non-empty array of strings")
    prompts = interface.get("defaultPrompt", interface.get("default_prompt"))
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        error(path, "`interface.defaultPrompt` must contain 1 to 3 strings")
    elif not all(non_empty_string(prompt) and len(prompt) <= 128 for prompt in prompts):
        error(path, "each default prompt must be a non-empty string of at most 128 chars")
    for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
        if field in interface:
            check_https_url(path, f"interface.{field}", interface[field])
    if "brandColor" in interface and (
        not isinstance(interface["brandColor"], str)
        or HEX_COLOR.fullmatch(interface["brandColor"]) is None
    ):
        error(path, "`interface.brandColor` must use #RRGGBB")


def check_codex_manifest(
    plugin_dir: Path,
    portable: dict[str, Any] | None,
    entry: dict[str, Any] | None,
) -> None:
    path = plugin_dir / ".codex-plugin" / "plugin.json"
    manifest = load_json(path)
    if manifest is None:
        return
    reject_todo_markers(manifest, path)
    for key in sorted(set(manifest) - CODEX_MANIFEST_FIELDS):
        error(path, f"{key!r} is not accepted by Codex plugin validation")
    name = manifest.get("name")
    if not valid_plugin_name(name):
        error(path, f"name {name!r} violates the plugin name rules")
    elif name != plugin_dir.name:
        error(path, f"name {name!r} must match directory {plugin_dir.name!r}")
    version = manifest.get("version")
    if not non_empty_string(version) or SEMVER.fullmatch(version) is None:
        error(path, "`version` must use strict semantic versioning")
    if not non_empty_string(manifest.get("description")):
        error(path, "`description` must be a non-empty string")
    check_author(path, manifest.get("author"), required=True)
    if manifest.get("skills") not in {"./skills", "./skills/"}:
        error(path, "`skills` must point to `./skills/`")
    if "apps" in manifest and not (plugin_dir / ".app.json").is_file():
        error(path, "`apps` is present but `.app.json` is missing")
    if "mcpServers" in manifest and isinstance(manifest["mcpServers"], str):
        if not (plugin_dir / ".mcp.json").is_file():
            error(path, "`mcpServers` points to a missing `.mcp.json`")
    check_codex_interface(path, manifest.get("interface"))
    interface = manifest.get("interface")
    if entry is not None and isinstance(interface, dict):
        if interface.get("category") != entry.get("category"):
            error(path, "`interface.category` disagrees with the marketplace entry")
    if portable is not None:
        for key in sorted(SHARED_MANIFEST_FIELDS):
            if manifest.get(key) != portable.get(key):
                error(path, f"{key} disagrees with root plugin.json")


def check_claude_manifest(
    plugin_dir: Path,
    portable: dict[str, Any] | None,
) -> None:
    path = plugin_dir / ".claude-plugin" / "plugin.json"
    manifest = load_json(path)
    if manifest is None:
        return
    if manifest.get("name") != plugin_dir.name:
        error(path, f"name {manifest.get('name')!r} must match directory {plugin_dir.name!r}")
    if portable is not None:
        for key in sorted(SHARED_MANIFEST_FIELDS):
            if manifest.get(key) != portable.get(key):
                error(path, f"{key} disagrees with root plugin.json")


def load_marketplace(path: Path, *, client: str) -> dict[str, dict[str, Any]]:
    marketplace = load_json(path)
    if marketplace is None:
        return {}
    if not non_empty_string(marketplace.get("name")):
        error(path, "`name` must be a non-empty string")
    if client == "codex":
        interface = marketplace.get("interface")
        if not isinstance(interface, dict) or not non_empty_string(interface.get("displayName")):
            error(path, "`interface.displayName` must be a non-empty string")
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        error(path, "`plugins` must be an array")
        return {}

    entries: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            error(path, f"plugins[{index}] must be an object")
            continue
        name = entry.get("name")
        if not valid_plugin_name(name):
            error(path, f"plugins[{index}].name {name!r} is invalid")
            continue
        if name in entries:
            error(path, f"duplicate marketplace entry {name!r}")
            continue
        entries[name] = entry

        expected_path = f"./plugins/{name}"
        if client == "codex":
            source = entry.get("source")
            if not isinstance(source, dict):
                error(path, f"{name!r} source must be an object")
            elif source.get("source") != "local" or source.get("path") != expected_path:
                error(path, f"{name!r} source must be local path {expected_path!r}")
            policy = entry.get("policy")
            if not isinstance(policy, dict):
                error(path, f"{name!r} policy must be an object")
            else:
                if policy.get("installation") not in INSTALLATION_POLICIES:
                    error(path, f"{name!r} has invalid installation policy")
                if policy.get("authentication") not in AUTHENTICATION_POLICIES:
                    error(path, f"{name!r} has invalid authentication policy")
            category = entry.get("category")
            if not non_empty_string(category):
                error(path, f"{name!r} category must be a non-empty string")
            elif category not in CODEX_CATEGORIES:
                error(path, f"{name!r} category {category!r} is not a Codex category")
        elif entry.get("source") != expected_path:
            error(path, f"{name!r} source must be {expected_path!r}")
    return entries


def check_plugin(
    plugin_dir: Path,
    claude_entries: dict[str, dict[str, Any]],
    codex_entries: dict[str, dict[str, Any]],
) -> None:
    name = plugin_dir.name
    for path in plugin_dir.rglob("*"):
        if path.is_symlink():
            error(path, "symlink: package paths must stay within the plugin root")

    portable = check_portable_manifest(plugin_dir)
    check_codex_manifest(plugin_dir, portable, codex_entries.get(name))
    check_claude_manifest(plugin_dir, portable)

    if name not in claude_entries:
        error(REPO / ".claude-plugin" / "marketplace.json", f"no entry for {name!r}")
    if name not in codex_entries:
        error(REPO / ".agents" / "plugins" / "marketplace.json", f"no entry for {name!r}")

    skills = plugin_dir / "skills"
    if not skills.is_dir():
        error(plugin_dir, "no skills/ directory")
        return
    children = sorted(path for path in skills.iterdir() if path.is_dir())
    if not children:
        error(skills, "contains no skills")
    for skill_dir in children:
        check_skill(skill_dir)


def check_extra_entries(
    path: Path,
    entries: dict[str, dict[str, Any]],
    plugin_names: set[str],
) -> None:
    for name in sorted(set(entries) - plugin_names):
        error(path, f"entry {name!r} has no directory under plugins/")


def main() -> int:
    claude_path = REPO / ".claude-plugin" / "marketplace.json"
    codex_path = REPO / ".agents" / "plugins" / "marketplace.json"
    claude_entries = load_marketplace(claude_path, client="claude")
    codex_entries = load_marketplace(codex_path, client="codex")

    plugins_root = REPO / "plugins"
    plugin_dirs = sorted(path for path in plugins_root.iterdir() if path.is_dir())
    if not plugin_dirs:
        errors.append("plugins/: no plugins found")
    for plugin_dir in plugin_dirs:
        check_plugin(plugin_dir, claude_entries, codex_entries)

    plugin_names = {path.name for path in plugin_dirs}
    check_extra_entries(claude_path, claude_entries, plugin_names)
    check_extra_entries(codex_path, codex_entries, plugin_names)

    for line in warnings:
        print(f"warning: {line}")
    for line in errors:
        print(f"error: {line}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"ok: {len(plugin_dirs)} plugin(s) valid for Agent Plugins, Codex, and Claude Code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
