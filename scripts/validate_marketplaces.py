#!/usr/bin/env python3
"""Validate the repository-local Claude/Copilot and Codex marketplaces."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when marketplace content is inconsistent or unsafe."""


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValidationError(f"expected JSON object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def resolved_inside(root: Path, relative: str, description: str) -> Path:
    require(isinstance(relative, str) and relative, f"{description} must be a non-empty string")
    target = (root / relative).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as error:
        raise ValidationError(f"{description} escapes its root: {relative}") from error
    return target


def plugin_paths(entry: dict, root: Path, source_key: str) -> Path:
    source = entry.get("source")
    if source_key == "claude":
        require(isinstance(source, str), f"Claude source for {entry.get('name')} must be a path string")
        return resolved_inside(root, source, f"Claude source for {entry.get('name')}")
    require(isinstance(source, dict), f"Codex source for {entry.get('name')} must be an object")
    require(source.get("source") == "local", f"Codex source for {entry.get('name')} must be local")
    return resolved_inside(root, source.get("path"), f"Codex source path for {entry.get('name')}")


def read_frontmatter(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValidationError(f"cannot read skill: {path}: {error}") from error
    require(lines and lines[0].strip() == "---", f"missing frontmatter start: {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as error:
        raise ValidationError(f"missing frontmatter end: {path}") from error
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    require(fields.get("name"), f"frontmatter name is required: {path}")
    require(fields.get("description"), f"frontmatter description is required: {path}")
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]), f"invalid skill name: {path}")
    return fields


def validate_skill_links(plugin_root: Path, skill_file: Path) -> None:
    markdown_link = re.compile(r"\[[^]]*\]\(([^)]+)\)")
    for reference in markdown_link.findall(skill_file.read_text(encoding="utf-8")):
        reference = reference.strip().split(" ", 1)[0]
        parsed = urlparse(reference)
        if parsed.scheme or reference.startswith("#"):
            continue
        target = (skill_file.parent / reference.split("#", 1)[0]).resolve()
        require(target.is_relative_to(plugin_root.resolve()), f"link leaves plugin root: {skill_file}: {reference}")
        require(target.exists(), f"broken relative link in {skill_file}: {reference}")


def validate_workflow_action_pins(root: Path) -> None:
    action_pattern = re.compile(r"^\s*uses:\s*([^#\s]+)")
    sha_pattern = re.compile(r"^.+@[0-9a-fA-F]{40}$")
    workflow_root = root / ".github/workflows"
    if not workflow_root.is_dir():
        return
    for workflow in sorted(workflow_root.glob("*.y*ml")):
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), start=1):
            match = action_pattern.match(line)
            if match:
                action = match.group(1)
                require(sha_pattern.fullmatch(action), f"GitHub Action is not pinned to a full SHA: {workflow}:{line_number}: {action}")


def skill_directories(plugin_root: Path, manifest: dict, plugin_name: str) -> list[Path]:
    value = manifest.get("skills", "skills/")
    values = value if isinstance(value, list) else [value]
    directories: list[Path] = []
    for item in values:
        directory = resolved_inside(plugin_root, item, f"skills path for {plugin_name}")
        require(directory.is_dir(), f"skills directory does not exist for {plugin_name}: {item}")
        directories.append(directory)
    return directories


def validate_plugin(entry: dict, plugin_root: Path, root: Path) -> None:
    name = entry.get("name")
    version = entry.get("version")
    require(isinstance(name, str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name), f"invalid plugin name: {name}")
    require(isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version), f"invalid version for {name}: {version}")
    require(plugin_root.is_dir(), f"plugin source does not exist: {plugin_root}")
    require((plugin_root / "LICENSE").is_file(), f"plugin LICENSE is missing: {name}")

    manifests = {
        "claude": load_json(plugin_root / ".claude-plugin/plugin.json"),
        "codex": load_json(plugin_root / ".codex-plugin/plugin.json"),
    }
    for product, manifest in manifests.items():
        require(manifest.get("name") == name, f"{product} manifest name mismatch for {name}")
        require(manifest.get("version") == version, f"{product} manifest version mismatch for {name}")
        for directory in skill_directories(plugin_root, manifest, name):
            for skill_file in sorted(directory.glob("*/SKILL.md")):
                skill_name = skill_file.parent.name
                fields = read_frontmatter(skill_file)
                require(fields["name"] == skill_name, f"skill directory/name mismatch: {skill_file}")
                require("[TODO:" not in skill_file.read_text(encoding="utf-8"), f"TODO placeholder in {skill_file}")
                validate_skill_links(plugin_root, skill_file)


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    claude = load_json(root / ".claude-plugin/marketplace.json")
    codex = load_json(root / ".agents/plugins/marketplace.json")
    validate_workflow_action_pins(root)
    claude_entries = {entry.get("name"): entry for entry in claude.get("plugins", [])}
    codex_entries = {entry.get("name"): entry for entry in codex.get("plugins", [])}
    require(set(claude_entries) == set(codex_entries), "Claude/Copilot and Codex plugin lists differ")

    for name, claude_entry in claude_entries.items():
        require(name, "marketplace plugin name is required")
        codex_entry = codex_entries[name]
        if codex_entry.get("version") is not None:
            require(claude_entry.get("version") == codex_entry.get("version"), f"marketplace version mismatch for {name}")
        claude_root = plugin_paths(claude_entry, root, "claude")
        codex_root = plugin_paths(codex_entry, root, "codex")
        require(claude_root == codex_root, f"marketplace source mismatch for {name}")
        require(codex_entry.get("policy", {}).get("installation") in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}, f"invalid Codex installation policy for {name}")
        require(codex_entry.get("policy", {}).get("authentication") in {"ON_INSTALL", "ON_USE"}, f"invalid Codex authentication policy for {name}")
        require(codex_entry.get("category"), f"Codex category is required for {name}")
        validate_plugin(claude_entry, claude_root, root)

    print(f"Validated {len(claude_entries)} plugin(s) under {root}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
