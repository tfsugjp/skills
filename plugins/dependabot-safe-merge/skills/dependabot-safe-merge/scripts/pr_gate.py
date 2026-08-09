#!/usr/bin/env python3
"""Evaluate the final GitHub gates before enabling auto-merge."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ACTIONS = {"merge", "refresh", "major-plan", "blocked"}
PASSING_CONCLUSIONS = {"SUCCESS", "NEUTRAL", "SKIPPED"}
WRITE_PERMISSIONS = {"WRITE", "MAINTAIN", "ADMIN"}
MERGE_METHODS = {"merge", "squash", "rebase"}


@dataclass
class GateDecision:
    action: str
    merge_method: str | None = None
    head_sha: str | None = None
    reasons: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        if self.action not in ACTIONS:
            raise AssertionError(f"invalid action: {self.action}")
        return asdict(self)


def blocked(reason: str, *, pending: list[str] | None = None) -> GateDecision:
    return GateDecision(action="blocked", reasons=[reason], pending=pending or [])


def file_is_allowed(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def latest_reviews(reviews: list[Any]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for review in reviews:
        if not isinstance(review, dict):
            continue
        user = str(review.get("user") or review.get("login") or "").strip()
        state = str(review.get("state") or "").upper()
        if user and state and state != "DISMISSED":
            latest[user] = state
    return latest


def evaluate(payload: Any) -> GateDecision:
    if not isinstance(payload, dict):
        return blocked("input must be a JSON object")
    release = payload.get("release_decision")
    if not isinstance(release, dict):
        return blocked("release_decision is required")
    release_action = str(release.get("action", "blocked"))
    if release_action not in ACTIONS:
        return blocked("release_decision has an invalid action")
    if release_action != "merge":
        reasons = release.get("reasons")
        return GateDecision(
            action=release_action,
            reasons=[str(item) for item in reasons] if isinstance(reasons, list) else ["release policy did not permit merge"],
        )

    if str(payload.get("author", "")).lower() != "dependabot[bot]":
        return blocked("pull request author is not dependabot[bot]")
    if str(payload.get("state", "")).upper() != "OPEN":
        return blocked("pull request is not open")
    permission = str(payload.get("permission", "")).upper()
    if not bool(payload.get("can_write", False)) and permission not in WRITE_PERMISSIONS:
        return blocked("repository write permission is required")
    if bool(payload.get("draft", False)):
        return blocked("compatible update is still a draft")
    if not bool(payload.get("branch_protection_known", False)):
        return blocked("branch protection and required gates could not be determined")
    if not bool(payload.get("auto_merge_allowed", False)):
        return blocked("repository auto-merge is not enabled")

    expected_head = str(payload.get("expected_head_sha", "")).strip()
    head = str(payload.get("head_sha", "")).strip()
    if not expected_head or not head or expected_head != head:
        return blocked("head SHA changed or was not captured")

    mergeable = payload.get("mergeable")
    conflicts = bool(payload.get("conflicts", False))
    if conflicts or mergeable not in {True, "MERGEABLE", "mergeable"}:
        return blocked("pull request has conflicts or mergeability is unknown")

    changed_files = payload.get("changed_files")
    allowed_patterns = payload.get("allowed_patterns")
    if not isinstance(changed_files, list) or not changed_files:
        return blocked("changed file list is missing")
    if not isinstance(allowed_patterns, list) or not allowed_patterns:
        return blocked("manifest and lockfile allowlist is missing")
    unexpected = [
        str(path)
        for path in changed_files
        if not file_is_allowed(str(path), [str(pattern) for pattern in allowed_patterns])
    ]
    if unexpected:
        return blocked("pull request contains unexpected file changes", pending=unexpected)

    checks = payload.get("required_checks", [])
    if not isinstance(checks, list):
        return blocked("required_checks must be an array")
    pending_checks: list[str] = []
    for check in checks:
        if not isinstance(check, dict):
            return blocked("required check record is invalid")
        name = str(check.get("name") or "unnamed-check")
        status = str(check.get("status") or "").upper()
        conclusion = str(check.get("conclusion") or "").upper()
        if status != "COMPLETED" or conclusion not in PASSING_CONCLUSIONS:
            pending_checks.append(name)
    if pending_checks:
        return blocked("required checks are incomplete or unsuccessful", pending=pending_checks)

    requested = payload.get("requested_reviewers", [])
    requested_teams = payload.get("requested_teams", [])
    if requested or requested_teams:
        pending = [str(item) for item in requested] + [str(item) for item in requested_teams]
        return blocked("required reviews are still requested", pending=pending)

    reviews = payload.get("reviews", [])
    if not isinstance(reviews, list):
        return blocked("reviews must be an array")
    latest = latest_reviews(reviews)
    if any(state == "CHANGES_REQUESTED" for state in latest.values()):
        return blocked("a current review requests changes")
    approvals = sum(1 for state in latest.values() if state == "APPROVED")
    required_approvals = int(payload.get("required_approvals", 0))
    if approvals < required_approvals:
        return blocked("required approval count has not been reached")

    unresolved = int(payload.get("unresolved_threads", -1))
    if unresolved < 0:
        return blocked("unresolved review thread count is unknown")
    if unresolved:
        return blocked("review threads remain unresolved")

    merge_method = str(payload.get("merge_method", "")).lower()
    if merge_method not in MERGE_METHODS:
        return blocked("repository merge method is missing or unsupported")

    return GateDecision(
        action="merge",
        merge_method=merge_method,
        head_sha=head,
        reasons=["all release, diff, CI, review, conflict, and head SHA gates passed"],
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
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        result = blocked(f"invalid input: {error.__class__.__name__}")
    json.dump(result.to_json(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.action != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
