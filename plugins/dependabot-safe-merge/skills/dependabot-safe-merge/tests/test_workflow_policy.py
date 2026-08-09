from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import major_plan  # noqa: E402
import native_update  # noqa: E402
import pr_gate  # noqa: E402
import refresh_policy  # noqa: E402


def refresh_payload(**overrides):
    value = {
        "eligible_version": "1.2.0",
        "proposed_version": "1.1.0",
        "refresh_iterations": 0,
        "recreate_requested": True,
        "poll_interval_seconds": 30,
        "poll_count": 0,
        "elapsed_seconds": 0,
        "expected_head_sha": "abc",
        "head_sha": "abc",
        "native_update_attempted": False,
    }
    value.update(overrides)
    return value


def gate_payload(**overrides):
    value = {
        "release_decision": {"action": "merge", "reasons": []},
        "author": "dependabot[bot]",
        "state": "OPEN",
        "permission": "WRITE",
        "draft": False,
        "branch_protection_known": True,
        "auto_merge_allowed": True,
        "expected_head_sha": "abc",
        "head_sha": "abc",
        "mergeable": True,
        "conflicts": False,
        "changed_files": ["package.json", "package-lock.json"],
        "allowed_patterns": ["package.json", "package-lock.json"],
        "required_checks": [{"name": "test", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        "requested_reviewers": [],
        "requested_teams": [],
        "reviews": [{"user": "reviewer", "state": "APPROVED"}],
        "required_approvals": 1,
        "unresolved_threads": 0,
        "merge_method": "squash",
    }
    value.update(overrides)
    return value


def major_payload(**overrides):
    value = {
        "ecosystem": "npm",
        "package": "@example/demo",
        "target_major": 2,
        "current_version": "1.5.0",
        "target_version": "2.1.0",
        "pull_request": "#42",
        "official_documents": ["Migration guide for version 2", "Version 2 release notes"],
        "breaking_changes": ["The legacy client constructor was removed."],
        "affected_code": ["src/client.ts uses the legacy constructor."],
        "implementation_steps": ["Add an adapter.", "Migrate call sites.", "Remove the adapter."],
        "tests_and_rollback": ["Run focused client tests.", "Revert the upgrade commit if rollout fails."],
        "acceptance_criteria": ["All call sites use the version 2 client."],
        "unresolved_questions": [],
        "existing_issue_bodies": [],
    }
    value.update(overrides)
    return value


class RefreshPolicyTests(unittest.TestCase):
    def test_recreate_is_requested_before_direct_update(self):
        result = refresh_policy.evaluate(refresh_payload(recreate_requested=False))
        self.assertEqual(("refresh", "comment-recreate"), (result.action, result.step))

    def test_recreate_wait_uses_thirty_second_interval(self):
        result = refresh_policy.evaluate(refresh_payload())
        self.assertEqual("wait-for-recreate", result.step)
        self.assertEqual(30, result.retry_after_seconds)

    def test_ten_minute_timeout_falls_back_to_native_update(self):
        result = refresh_policy.evaluate(refresh_payload(poll_count=20, elapsed_seconds=600))
        self.assertEqual(("refresh", "native-update"), (result.action, result.step))

    def test_head_change_forces_full_recheck(self):
        result = refresh_policy.evaluate(refresh_payload(head_sha="def"))
        self.assertEqual("recheck-head", result.step)

    def test_refresh_loop_is_limited_to_three(self):
        result = refresh_policy.evaluate(refresh_payload(refresh_iterations=3))
        self.assertEqual(("blocked", "refresh-limit"), (result.action, result.step))

    def test_unexpected_native_diff_blocks(self):
        result = refresh_policy.evaluate(refresh_payload(
            poll_count=20,
            elapsed_seconds=600,
            native_update_attempted=True,
            changed_files=["package.json", "src/app.ts"],
            allowed_patterns=["package.json", "package-lock.json"],
        ))
        self.assertEqual(("blocked", "unexpected-diff"), (result.action, result.step))

    def test_refreshed_version_moves_to_gate_evaluation(self):
        result = refresh_policy.evaluate(refresh_payload(proposed_version="1.2.0"))
        self.assertEqual(("merge", "evaluate-pr-gates"), (result.action, result.step))


class NativeUpdateTests(unittest.TestCase):
    def test_all_supported_ecosystem_plans_are_argv_arrays(self):
        cases = [
            ("npm", "npm"),
            ("nuget", "dotnet"),
            ("python", "pip-compile"),
            ("maven", "maven"),
            ("cargo", "cargo"),
            ("go", "go"),
            ("github-actions", "manual-edit"),
        ]
        for ecosystem, manager in cases:
            with self.subTest(ecosystem=ecosystem):
                plan = native_update.build_plan(ecosystem, manager, "example/demo", "1.2.3")
                self.assertEqual("refresh", plan.action)
                self.assertTrue(all(isinstance(item.argv, list) for item in plan.commands))

    def test_native_runner_is_injected_and_never_uses_a_shell(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append((argv, kwargs))
            return 0

        plan = native_update.build_plan("npm", "npm", "@example/demo", "1.2.3")
        native_update.execute_plan(plan, runner)
        self.assertEqual(1, len(calls))
        self.assertFalse(calls[0][1]["shell"])
        self.assertTrue(any(key.lower() == "path" for key in calls[0][1]["env"]))
        self.assertEqual("true", calls[0][1]["env"]["npm_config_ignore_scripts"])
        self.assertNotIn("token", json.dumps(plan.to_json()).lower())

    def test_nuget_plan_targets_package_before_restore(self):
        plan = native_update.build_plan("nuget", "dotnet", "Example.Package", "2.3.4")
        self.assertEqual(
            ["dotnet", "add", "package", "Example.Package", "--version", "2.3.4", "--no-restore"],
            plan.commands[0].argv,
        )
        self.assertEqual(["dotnet", "restore"], plan.commands[1].argv)


class MajorPlanTests(unittest.TestCase):
    def test_grouped_dependencies_receive_distinct_markers(self):
        first = major_plan.evaluate(major_payload(package="@example/one"))
        second = major_plan.evaluate(major_payload(package="@example/two"))
        self.assertEqual("major-plan", first.action)
        self.assertNotEqual(first.marker, second.marker)

    def test_existing_marker_updates_instead_of_duplicates(self):
        initial = major_plan.evaluate(major_payload())
        repeated = major_plan.evaluate(major_payload(existing_issue_bodies=[initial.body]))
        self.assertEqual("update", repeated.operation)

    def test_missing_official_documentation_blocks(self):
        result = major_plan.evaluate(major_payload(official_documents=[]))
        self.assertEqual("blocked", result.action)


class PullRequestGateTests(unittest.TestCase):
    def test_all_gates_pass_for_compatible_update(self):
        result = pr_gate.evaluate(gate_payload())
        self.assertEqual("merge", result.action)
        self.assertEqual("squash", result.merge_method)

    def test_required_ci_must_complete(self):
        result = pr_gate.evaluate(gate_payload(required_checks=[
            {"name": "test", "status": "IN_PROGRESS", "conclusion": ""},
        ]))
        self.assertEqual("blocked", result.action)

    def test_required_reviews_must_complete(self):
        result = pr_gate.evaluate(gate_payload(requested_reviewers=["reviewer"]))
        self.assertEqual("blocked", result.action)

    def test_unresolved_thread_blocks(self):
        result = pr_gate.evaluate(gate_payload(unresolved_threads=1))
        self.assertEqual("blocked", result.action)

    def test_conflict_blocks(self):
        result = pr_gate.evaluate(gate_payload(conflicts=True))
        self.assertEqual("blocked", result.action)

    def test_head_sha_change_blocks(self):
        result = pr_gate.evaluate(gate_payload(head_sha="def"))
        self.assertEqual("blocked", result.action)

    def test_unexpected_file_blocks(self):
        result = pr_gate.evaluate(gate_payload(changed_files=["package.json", "src/app.ts"]))
        self.assertEqual("blocked", result.action)

    def test_major_decision_never_reaches_merge_gates(self):
        result = pr_gate.evaluate(gate_payload(release_decision={"action": "major-plan", "reasons": ["major"]}))
        self.assertEqual("major-plan", result.action)

    def test_pending_gate_does_not_request_auto_merge(self):
        result = pr_gate.evaluate(gate_payload(auto_merge_allowed=False))
        self.assertEqual("blocked", result.action)
        self.assertIsNone(result.merge_method)


if __name__ == "__main__":
    unittest.main()
