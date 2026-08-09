#!/usr/bin/env python3
"""Build non-shell native dependency update commands without executing them."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

SAFE_VALUE = re.compile(r"^[A-Za-z0-9@._/+:-]+$")


@dataclass
class UpdateCommand:
    argv: list[str]
    environment: dict[str, str] = field(default_factory=dict)


@dataclass
class UpdatePlan:
    action: str
    manager: str
    commands: list[UpdateCommand]
    preserve_declaration_style: bool = True
    verify_expected_diff: bool = True
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def validate_value(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not SAFE_VALUE.fullmatch(text) or any(character in text for character in "\r\n\t"):
        raise ValueError(f"{name} is missing or unsafe")
    return text


def build_plan(ecosystem: str, manager: str, package: str, version: str) -> UpdatePlan:
    ecosystem = ecosystem.strip().lower()
    manager = manager.strip().lower()
    package = validate_value("package", package)
    version = validate_value("version", version)
    command: list[UpdateCommand]
    if ecosystem in {"npm", "yarn", "pnpm"}:
        manager = manager or ecosystem
        if manager == "npm":
            command = [UpdateCommand(
                ["npm", "install", "--package-lock-only", "--ignore-scripts", f"{package}@{version}"],
                {"npm_config_ignore_scripts": "true"},
            )]
        elif manager == "yarn":
            command = [UpdateCommand(
                ["yarn", "up", f"{package}@{version}", "--mode=update-lockfile"],
                {"YARN_ENABLE_SCRIPTS": "false"},
            )]
        elif manager == "pnpm":
            command = [UpdateCommand(
                ["pnpm", "update", "--lockfile-only", "--ignore-scripts", f"{package}@{version}"],
                {"npm_config_ignore_scripts": "true"},
            )]
        else:
            raise ValueError("unsupported JavaScript package manager")
    elif ecosystem == "nuget":
        command = [
            UpdateCommand(
                ["dotnet", "add", "package", package, "--version", version, "--no-restore"],
                {"NUGET_XMLDOC_MODE": "skip"},
            ),
            UpdateCommand(["dotnet", "restore"], {"NUGET_XMLDOC_MODE": "skip"}),
        ]
        manager = manager or "dotnet"
    elif ecosystem in {"python", "pip", "pypi", "poetry", "uv"}:
        manager = manager or ecosystem
        if manager in {"pip", "pip-compile"}:
            command = [UpdateCommand(["pip-compile", "--upgrade-package", f"{package}=={version}"])]
        elif manager == "poetry":
            command = [UpdateCommand(["poetry", "update", package, "--lock"])]
        elif manager == "uv":
            command = [UpdateCommand(["uv", "lock", "--upgrade-package", f"{package}=={version}"])]
        else:
            raise ValueError("unsupported Python lock manager")
    elif ecosystem in {"maven", "gradle"}:
        manager = manager or ecosystem
        if manager == "maven":
            command = [UpdateCommand([
                "mvnw",
                "versions:use-dep-version",
                f"-Dincludes={package}",
                f"-DdepVersion={version}",
                "-DgenerateBackupPoms=false",
            ])]
        elif manager == "gradle":
            command = [UpdateCommand(["gradlew", "dependencies", "--write-locks"])]
        else:
            raise ValueError("unsupported JVM package manager")
    elif ecosystem == "cargo":
        manager = manager or "cargo"
        command = [UpdateCommand(["cargo", "update", "-p", package, "--precise", version])]
    elif ecosystem in {"go", "gomod"}:
        manager = manager or "go"
        command = [
            UpdateCommand(["go", "get", f"{package}@{version}"]),
            UpdateCommand(["go", "mod", "tidy"]),
        ]
    elif ecosystem in {"actions", "github-actions"}:
        manager = manager or "manual-edit"
        command = []
    else:
        raise ValueError("unsupported ecosystem")
    return UpdatePlan(
        action="refresh",
        manager=manager,
        commands=command,
        reasons=["update only the selected dependency on the existing pull request branch"],
    )


def execute_plan(plan: UpdatePlan, runner: Callable[..., Any]) -> list[Any]:
    """Execute argv arrays through an injected runner; intended for controlled callers and tests."""
    results = []
    for command in plan.commands:
        results.append(runner(command.argv, env={**os.environ, **command.environment}, check=True, shell=False))
    return results


def load_payload(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON input file; defaults to standard input")
    args = parser.parse_args(argv)
    try:
        payload = load_payload(args.input)
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result: dict[str, Any] = build_plan(
            str(payload.get("ecosystem", "")),
            str(payload.get("manager", "")),
            payload.get("package"),
            payload.get("version"),
        ).to_json()
        status = 0
    except (OSError, json.JSONDecodeError, ValueError) as error:
        result = {"action": "blocked", "reasons": [str(error) if isinstance(error, ValueError) else f"invalid input: {error.__class__.__name__}"]}
        status = 2
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
