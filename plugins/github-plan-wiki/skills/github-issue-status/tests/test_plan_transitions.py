#!/usr/bin/env python3
"""Behavioral checks for issue planning-status transitions."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/plan_transitions.py"
spec = importlib.util.spec_from_file_location("plan_transitions", SCRIPT)
planner = importlib.util.module_from_spec(spec)
sys.modules["plan_transitions"] = planner  # dataclasses resolve annotations through sys.modules
spec.loader.exec_module(planner)

STATUSES = [
    {"id": "S_backlog", "name": "Backlog", "category": {"key": "backlog"}},
    {"id": "S_todo", "name": "Todo", "category": {"key": "planned"}},
    {"id": "S_progress", "name": "In progress", "category": {"key": "started"}},
    {"id": "S_review", "name": "In review", "category": {"key": "started"}},
    {"id": "S_done", "name": "Done", "category": {"key": "completed"}},
    {"id": "S_notplanned", "name": "Not planned", "category": {"key": "not_planned"}},
    {"id": "S_dup", "name": "Duplicate", "category": {"key": "duplicate"}},
]
BY_NAME = {s["name"]: s for s in STATUSES}
CLOSED = {"Done": "COMPLETED", "Not planned": "NOT_PLANNED", "Duplicate": "DUPLICATE"}


def issue(number, status="Backlog", repo="team/repo", **extra):
    node = {
        "id": f"I_{number}",
        "number": number,
        "title": f"Issue {number}",
        "state": "CLOSED" if status in CLOSED else "OPEN",
        "stateReason": CLOSED.get(status),
        "repository": {"nameWithOwner": repo},
        "status": {"id": BY_NAME[status]["id"], "name": status, "category": BY_NAME[status]["category"]}
        if status
        else None,
    }
    node.update(extra)
    return node


def parent_of(number, status, children, parent=None):
    node = issue(number, status, subIssues={"nodes": children}, subIssuesSummary={"total": len(children)})
    node["parent"] = parent
    return node


def context(target, statuses=STATUSES):
    target.setdefault("viewerCanSetStatus", True)
    target.setdefault("assignees", {"nodes": []})
    target.setdefault("milestone", None)
    target.setdefault("blockedBy", {"nodes": []})
    target.setdefault("subIssues", {"nodes": []})
    target.setdefault("parent", None)
    planning = {"nodes": statuses} if statuses is not None else None
    return {"data": {"repository": {"planningStatuses": planning, "issue": target}}}


def run(ctx, event, *extra):
    args = planner.parse_args(["--context", "unused", "--event", event, *extra])
    return planner.Planner(copy.deepcopy(ctx), args).run()


def moves(changes):
    return [(c.number, c.to_status) for c in changes]


class CreateTests(unittest.TestCase):
    def test_unplanned_issue_stays_in_backlog(self):
        plan = run(context(issue(1, "Backlog")), "create")
        self.assertEqual([], plan.changes)

    def test_assigned_or_planned_issue_moves_to_todo(self):
        assigned = issue(1, "Backlog", assignees={"nodes": [{"login": "dev"}]})
        self.assertEqual([(1, "Todo")], moves(run(context(assigned), "create").changes))
        self.assertEqual([(2, "Todo")], moves(run(context(issue(2)), "create", "--from-plan").changes))
        milestone = issue(3, "Backlog", milestone={"title": "v1"})
        self.assertEqual([(3, "Todo")], moves(run(context(milestone), "create").changes))

    def test_create_never_moves_back(self):
        plan = run(context(issue(1, "In progress")), "create", "--from-plan")
        self.assertEqual([], plan.changes)

    def test_new_child_reopens_completed_parent(self):
        target = issue(5)
        target["parent"] = parent_of(4, "Done", [issue(9, "Done"), target])
        plan = run(context(target), "create", "--from-plan")
        self.assertEqual([(5, "Todo"), (4, "In progress")], moves(plan.changes))
        self.assertTrue(plan.changes[1].reopens)


class StartTests(unittest.TestCase):
    def test_child_start_promotes_every_ancestor(self):
        grand = parent_of(1, "Backlog", [])
        parent = parent_of(2, "Todo", [], parent=grand)
        target = issue(3, "Todo", parent=parent)
        plan = run(context(target), "start")
        self.assertEqual([(3, "In progress"), (2, "In progress"), (1, "In progress")], moves(plan.changes))
        self.assertEqual([], plan.proposals)

    def test_ancestor_in_review_is_not_demoted(self):
        parent = parent_of(2, "In review", [])
        plan = run(context(issue(3, "Todo", parent=parent)), "start")
        self.assertEqual([(3, "In progress")], moves(plan.changes))

    def test_completed_ancestor_is_reopened(self):
        parent = parent_of(2, "Done", [])
        plan = run(context(issue(3, "Todo", parent=parent)), "start")
        self.assertEqual([(3, "In progress"), (2, "In progress")], moves(plan.changes))
        self.assertTrue(plan.changes[1].reopens)

    def test_not_planned_ancestor_stops_propagation(self):
        grand = parent_of(1, "Backlog", [])
        parent = parent_of(2, "Not planned", [], parent=grand)
        plan = run(context(issue(3, "Todo", parent=parent)), "start")
        self.assertEqual([(3, "In progress")], moves(plan.changes))
        self.assertTrue(any("#2" in w for w in plan.warnings))

    def test_parent_start_moves_backlog_children_to_todo_only(self):
        children = [issue(11, "Backlog"), issue(12, "Todo"), issue(13, "In progress"), issue(14, "Done")]
        plan = run(context(issue(10, "Todo", subIssues={"nodes": children})), "start")
        self.assertEqual([(10, "In progress"), (11, "Todo")], moves(plan.changes))

    def test_target_in_review_is_not_moved_back(self):
        plan = run(context(issue(3, "In review")), "start")
        self.assertEqual([], plan.changes)
        self.assertTrue(plan.warnings)

    def test_open_blocker_warns(self):
        blocked = issue(3, "Todo", blockedBy={"nodes": [{"number": 7, "title": "API", "state": "OPEN"}]})
        plan = run(context(blocked), "start")
        self.assertEqual([(3, "In progress")], moves(plan.changes))
        self.assertTrue(any("#7" in w for w in plan.warnings))

    def test_other_owner_ancestor_is_attempted_with_warning(self):
        parent = parent_of(2, "Todo", [])
        parent["repository"] = {"nameWithOwner": "elsewhere/repo"}
        plan = run(context(issue(3, "Todo", parent=parent)), "start")
        self.assertEqual([(3, "In progress"), (2, "In progress")], moves(plan.changes))
        self.assertTrue(any("elsewhere/repo" in w for w in plan.warnings))


class CompleteTests(unittest.TestCase):
    def test_last_child_completion_proposes_parent_done(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "In progress", [issue(4, "Done"), target])
        plan = run(context(target), "complete")
        self.assertEqual([], plan.changes)
        self.assertEqual([(2, "Done")], moves(plan.proposals))
        self.assertTrue(plan.proposals[0].closes)

    def test_confirmed_close_becomes_a_change(self):
        target = issue(3, "In progress")
        target["parent"] = parent_of(2, "In progress", [issue(4, "Done"), target])
        plan = run(context(target), "complete", "--confirm-close", "3")
        self.assertEqual([(3, "Done")], moves(plan.changes))
        self.assertEqual([(2, "Done")], moves(plan.proposals))

    def test_open_sibling_keeps_parent_open(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "Todo", [issue(4, "Todo"), target])
        plan = run(context(target), "complete")
        self.assertEqual([(2, "In progress")], moves(plan.changes))
        self.assertEqual([], plan.proposals)

    def test_grandparent_check_is_a_follow_up(self):
        grand = parent_of(1, "In progress", [])
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "In progress", [target], parent=grand)
        plan = run(context(target), "complete")
        self.assertEqual([(2, "Done")], moves(plan.proposals))
        self.assertTrue(plan.follow_up)

    def test_all_children_not_planned_is_left_to_the_user(self):
        target = issue(3, "Todo")
        target["parent"] = parent_of(2, "In progress", [issue(4, "Not planned"), target])
        plan = run(context(target), "set", "--status", "Not planned", "--confirm-close", "3")
        self.assertEqual([(3, "Not planned")], moves(plan.changes))
        self.assertTrue(any("without completion" in w for w in plan.warnings))

    def test_unconfirmed_child_closure_does_not_close_parent(self):
        # Only the parent is confirmed; the child's own closure stays a proposal.
        target = issue(3, "In progress")
        target["parent"] = parent_of(2, "In progress", [issue(4, "Done"), target])
        plan = run(context(target), "complete", "--confirm-close", "2")
        self.assertEqual([(3, "Done")], moves(plan.proposals))
        self.assertEqual([], [c for c in plan.changes if c.number == 2])
        self.assertTrue(any("#2" in f for f in plan.follow_up))
        plan = run(context(target), "set", "--status", "Not planned", "--confirm-close", "2")
        self.assertEqual([(3, "Not planned")], moves(plan.proposals))
        self.assertEqual([], plan.changes)


class ReviewRegressionTests(unittest.TestCase):
    def test_confirmation_is_scoped_to_repository(self):
        target = issue(12, "Done")
        target["parent"] = parent_of(12, "In progress", [target])
        target["parent"]["repository"] = {"nameWithOwner": "other/repo"}
        plan = run(context(target), "complete", "--confirm-close", "12")
        self.assertEqual([], plan.changes)
        self.assertEqual([(12, "Done")], moves(plan.proposals))
        plan = run(context(target), "complete", "--confirm-close", "other/repo#12")
        self.assertEqual([(12, "Done")], moves(plan.changes))

    def test_invalid_confirmation_is_a_clean_error(self):
        for bad in ("abc", "owner/repo12", "foo/12"):
            with self.assertRaises(SystemExit):
                run(context(issue(3)), "complete", "--confirm-close", bad)

    def test_reclassifying_done_child_to_not_planned_does_not_propose_parent_done(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "In progress", [issue(4, "Not planned"), target])
        plan = run(context(target), "set", "--status", "Not planned", "--confirm-close", "3")
        self.assertEqual([(3, "Not planned")], moves(plan.changes))
        self.assertEqual([], plan.proposals)
        self.assertTrue(any("without completion" in w for w in plan.warnings))

    def test_reopen_after_github_reset_to_backlog_moves_to_todo(self):
        target = issue(3, "Backlog")
        target["parent"] = parent_of(2, "Done", [target])
        plan = run(context(target), "reopen")
        self.assertEqual([(3, "Todo"), (2, "In progress")], moves(plan.changes))

    def test_set_todo_on_closed_child_reopens_completed_parent(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "Done", [target])
        plan = run(context(target), "set", "--status", "Todo")
        self.assertEqual([(3, "Todo"), (2, "In progress")], moves(plan.changes))

    def test_unconfirmed_parent_done_keeps_promotion_and_updates_from_status(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "Todo", [target])
        plan = run(context(target), "complete")
        self.assertEqual([(2, "In progress")], moves(plan.changes))
        self.assertEqual("In progress", plan.proposals[0].from_status)

    def test_confirmed_parent_done_replaces_promotion(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "Todo", [target])
        plan = run(context(target), "complete", "--confirm-close", "2")
        self.assertEqual([(2, "Done")], moves(plan.changes))

    def test_reclassifying_closed_issue_needs_confirmation(self):
        plan = run(context(issue(3, "Not planned")), "complete")
        self.assertEqual([(3, "Done")], moves(plan.proposals))

    def test_create_sets_backlog_on_statusless_issue_and_skips_closed(self):
        self.assertEqual([(3, "Backlog")], moves(run(context(issue(3, None)), "create").changes))
        plan = run(context(issue(4, "Done")), "create", "--from-plan")
        self.assertEqual([], plan.changes)
        self.assertTrue(plan.warnings)

    def test_start_warns_when_sub_issues_exceed_page(self):
        target = issue(3, "Todo", subIssues={"nodes": [issue(4)]}, subIssuesSummary={"total": 150})
        plan = run(context(target), "start")
        self.assertTrue(any("150" in w for w in plan.warnings))

    def test_missing_category_warns(self):
        custom = [s for s in STATUSES if s["category"]["key"] != "planned"]
        plan = run(context(issue(3, "Backlog"), statuses=custom), "create", "--from-plan")
        self.assertEqual([], plan.changes)
        self.assertTrue(any("no status fits" in w for w in plan.warnings))

    def test_duplicate_mutation_carries_original(self):
        plan = run(context(issue(3, "Todo")), "set", "--status", "Duplicate", "--duplicate-of", "I_9",
                   "--confirm-close", "3")
        self.assertIn('duplicateIssueId: "I_9"', planner.mutation_text(plan.changes))


class ReopenAndSetTests(unittest.TestCase):
    def test_reopen_child_returns_completed_parent_to_in_progress(self):
        target = issue(3, "Done")
        target["parent"] = parent_of(2, "Done", [target])
        plan = run(context(target), "reopen")
        self.assertEqual([(3, "Todo"), (2, "In progress")], moves(plan.changes))
        self.assertTrue(all(c.reopens for c in plan.changes))

    def test_duplicate_requires_original_issue(self):
        with self.assertRaises(SystemExit):
            run(context(issue(3, "Todo")), "set", "--status", "Duplicate")
        plan = run(context(issue(3, "Todo")), "set", "--status", "Duplicate", "--duplicate-of", "I_9",
                   "--confirm-close", "3")
        self.assertEqual("I_9", plan.changes[0].duplicate_issue_id)

    def test_unknown_status_lists_available_names(self):
        with self.assertRaises(SystemExit) as raised:
            run(context(issue(3)), "set", "--status", "Blocked")
        self.assertIn("In review", str(raised.exception))


class AvailabilityTests(unittest.TestCase):
    def test_statuses_unavailable_skips(self):
        plan = run(context(issue(3, None), statuses=None), "start")
        self.assertFalse(plan.available)
        self.assertEqual([], plan.changes)

    def test_viewer_cannot_set_status_skips(self):
        plan = run(context(issue(3, "Todo", viewerCanSetStatus=False)), "start")
        self.assertFalse(plan.available)

    def test_custom_started_names_are_resolved_by_category(self):
        custom = [s for s in STATUSES if s["name"] not in ("In progress", "In review")]
        custom.insert(2, {"id": "S_doing", "name": "Doing", "category": {"key": "started"}})
        plan = run(context(issue(3, "Todo"), statuses=custom), "start")
        self.assertEqual([(3, "Doing")], moves(plan.changes))


class CommandLineTests(unittest.TestCase):
    def test_writes_mutation_in_order(self):
        parent = parent_of(2, "Todo", [])
        ctx = context(issue(3, "Todo", parent=parent))
        with tempfile.TemporaryDirectory() as tmp:
            ctx_file = Path(tmp, "ctx.json")
            ctx_file.write_text(json.dumps(ctx), encoding="utf-8")
            mutation = Path(tmp, "m.graphql")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--context", str(ctx_file), "--event", "start",
                 "--mutation-out", str(mutation)],
                check=True, capture_output=True, text=True,
            )
            plan = json.loads(result.stdout)
            self.assertEqual([3, 2], [c["number"] for c in plan["changes"]])
            text = mutation.read_text(encoding="utf-8")
            self.assertLess(text.index('"I_3"'), text.index('"I_2"'))
            self.assertIn('statusId: "S_progress"', text)

    def test_rejects_unexpected_node_ids(self):
        change = planner.Change(1, "team/repo", 'I_1"){x}', None, "Todo", "S_todo", "test")
        with self.assertRaises(SystemExit):
            planner.mutation_text([change])


if __name__ == "__main__":
    unittest.main()
