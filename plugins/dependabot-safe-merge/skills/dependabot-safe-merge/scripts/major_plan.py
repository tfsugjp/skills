#!/usr/bin/env python3
"""Build a deduplicated major-upgrade implementation-plan issue body."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SAFE_ECOSYSTEM = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SAFE_PACKAGE = re.compile(r"^[A-Za-z0-9@._/+:-]+$")
SAFE_MAJOR = re.compile(r"^\d+$")


@dataclass
class MajorPlanDecision:
    action: str
    operation: str | None = None
    marker: str | None = None
    title: str | None = None
    body: str | None = None
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def blocked(reason: str) -> MajorPlanDecision:
    return MajorPlanDecision(action="blocked", reasons=[reason])


def strings(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field_name} must be a non-empty string array")
    return [item.strip() for item in value]


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def evaluate(payload: Any) -> MajorPlanDecision:
    if not isinstance(payload, dict):
        return blocked("input must be a JSON object")
    ecosystem = str(payload.get("ecosystem", "")).strip().lower()
    package = str(payload.get("package", "")).strip()
    target_major = str(payload.get("target_major", "")).strip()
    if not SAFE_ECOSYSTEM.fullmatch(ecosystem):
        return blocked("ecosystem is missing or unsafe")
    if not SAFE_PACKAGE.fullmatch(package) or "-->" in package:
        return blocked("package is missing or unsafe")
    if not SAFE_MAJOR.fullmatch(target_major):
        return blocked("target_major must be numeric")
    marker = f"<!-- dependabot-safe-merge:key={ecosystem}:{package}:{target_major} -->"
    try:
        current_version = str(payload.get("current_version", "")).strip()
        target_version = str(payload.get("target_version", "")).strip()
        pull_request = str(payload.get("pull_request", "")).strip()
        if not current_version or not target_version or not re.fullmatch(r"#\d+", pull_request):
            raise ValueError("current_version, target_version, and pull_request #number are required")
        official_documents = strings(payload.get("official_documents"), "official_documents")
        breaking_changes = strings(payload.get("breaking_changes"), "breaking_changes")
        affected_code = strings(payload.get("affected_code"), "affected_code")
        implementation_steps = strings(payload.get("implementation_steps"), "implementation_steps")
        tests = strings(payload.get("tests_and_rollback"), "tests_and_rollback")
        acceptance = strings(payload.get("acceptance_criteria"), "acceptance_criteria")
        unresolved = payload.get("unresolved_questions", [])
        if not isinstance(unresolved, list) or not all(isinstance(item, str) and item.strip() for item in unresolved):
            raise ValueError("unresolved_questions must be a string array")
        unresolved_items = [item.strip() for item in unresolved] or ["None identified after the current review."]
    except ValueError as error:
        return blocked(str(error))

    body = "\n".join(
        [
            marker,
            "",
            "## Current and target versions",
            "",
            f"- Dependency: `{package}`",
            f"- Ecosystem: `{ecosystem}`",
            f"- Current version: `{current_version}`",
            f"- Target version: `{target_version}`",
            f"- Related pull request: {pull_request}",
            "",
            "## Official documentation reviewed",
            "",
            bullets(official_documents),
            "",
            "## Incompatible and breaking changes",
            "",
            bullets(breaking_changes),
            "",
            "## Affected code",
            "",
            bullets(affected_code),
            "",
            "## Phased implementation plan",
            "",
            "\n".join(f"{index}. {item}" for index, item in enumerate(implementation_steps, start=1)),
            "",
            "## Tests and rollback",
            "",
            bullets(tests),
            "",
            "## Acceptance criteria",
            "",
            bullets(acceptance),
            "",
            "## Unresolved questions",
            "",
            bullets(unresolved_items),
            "",
        ]
    )
    existing_bodies = payload.get("existing_issue_bodies", [])
    if not isinstance(existing_bodies, list):
        return blocked("existing_issue_bodies must be an array")
    operation = "update" if any(marker in str(item) for item in existing_bodies) else "create"
    return MajorPlanDecision(
        action="major-plan",
        operation=operation,
        marker=marker,
        title=f"Plan {package} {target_major}.x upgrade",
        body=body,
        reasons=["major upgrade requires a draft pull request, source review, and tracked implementation plan"],
    )


def load_payload(path: str | None) -> Any:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON input file; defaults to standard input")
    args = parser.parse_args(argv)
    try:
        result = evaluate(load_payload(args.input))
    except (OSError, json.JSONDecodeError) as error:
        result = blocked(f"invalid input: {error.__class__.__name__}")
    json.dump(result.to_json(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.action != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
