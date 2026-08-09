#!/usr/bin/env python3
"""Decide the next bounded refresh step for a stale Dependabot pull request."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ACTIONS = {"merge", "refresh", "major-plan", "blocked"}
POLL_INTERVAL_SECONDS = 30
MAX_POLLS = 20
MAX_WAIT_SECONDS = 600
MAX_REFRESH_ITERATIONS = 3


@dataclass
class RefreshDecision:
    action: str
    step: str
    retry_after_seconds: int | None = None
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        if self.action not in ACTIONS:
            raise AssertionError(f"invalid action: {self.action}")
        return asdict(self)


def decision(action: str, step: str, reason: str, retry: int | None = None) -> RefreshDecision:
    return RefreshDecision(action=action, step=step, retry_after_seconds=retry, reasons=[reason])


def matches_expected_files(changed_files: list[str], allowed_patterns: list[str]) -> bool:
    if not changed_files or not allowed_patterns:
        return False
    return all(any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed_patterns) for path in changed_files)


def evaluate(payload: Any) -> RefreshDecision:
    if not isinstance(payload, dict):
        return decision("blocked", "invalid-input", "input must be a JSON object")
    eligible = str(payload.get("eligible_version", "")).strip()
    proposed = str(payload.get("proposed_version", "")).strip()
    if not eligible or not proposed:
        return decision("blocked", "invalid-input", "eligible_version and proposed_version are required")
    iterations = int(payload.get("refresh_iterations", 0))
    if iterations < 0:
        return decision("blocked", "invalid-input", "refresh_iterations cannot be negative")
    if proposed == eligible:
        expected_sha = str(payload.get("expected_head_sha", ""))
        head_sha = str(payload.get("head_sha", ""))
        if not expected_sha or head_sha != expected_sha:
            return decision("refresh", "recheck-head", "head SHA changed; refetch policy and pull request evidence")
        return decision("merge", "evaluate-pr-gates", "eligible target is present at the expected head SHA")
    if iterations >= MAX_REFRESH_ITERATIONS:
        return decision("blocked", "refresh-limit", "eligible release did not stabilize within three refresh iterations")
    if not bool(payload.get("recreate_requested", False)):
        return decision("refresh", "comment-recreate", "send @dependabot recreate before direct branch updates")
    if int(payload.get("poll_interval_seconds", POLL_INTERVAL_SECONDS)) != POLL_INTERVAL_SECONDS:
        return decision("blocked", "invalid-poll-policy", "recreate polling interval must be 30 seconds")
    expected_sha = str(payload.get("expected_head_sha", ""))
    head_sha = str(payload.get("head_sha", ""))
    if expected_sha and head_sha and head_sha != expected_sha:
        return decision("refresh", "recheck-head", "Dependabot changed the head SHA; refetch the diff and registry policy")
    poll_count = int(payload.get("poll_count", 0))
    elapsed = int(payload.get("elapsed_seconds", 0))
    if poll_count < 0 or elapsed < 0:
        return decision("blocked", "invalid-input", "poll counters cannot be negative")
    if poll_count < MAX_POLLS and elapsed < MAX_WAIT_SECONDS:
        return decision("refresh", "wait-for-recreate", "wait for Dependabot to recreate the pull request", POLL_INTERVAL_SECONDS)
    if not bool(payload.get("native_update_attempted", False)):
        return decision("refresh", "native-update", "recreate timed out; run the targeted native updater on the same branch")
    changed_files = payload.get("changed_files", [])
    allowed_patterns = payload.get("allowed_patterns", [])
    if not isinstance(changed_files, list) or not isinstance(allowed_patterns, list):
        return decision("blocked", "invalid-input", "changed_files and allowed_patterns must be arrays")
    if not matches_expected_files([str(item) for item in changed_files], [str(item) for item in allowed_patterns]):
        return decision("blocked", "unexpected-diff", "native update changed files outside the manifest and lockfile allowlist")
    return decision("blocked", "stale-after-native-update", "native update completed but the eligible target is still absent")


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
        result = decision("blocked", "invalid-input", f"invalid input: {error.__class__.__name__}")
    json.dump(result.to_json(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.action != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
