#!/usr/bin/env python3
"""Plan GitHub issue planning-status changes for one issue event.

Reads the JSON printed by ``gh api graphql -F query=@queries/issue-context.graphql``
and prints a JSON plan: changes that are safe to apply, proposals that close an
issue and need the user's confirmation, and warnings. With ``--mutation-out`` it
also writes a ``setIssueStatus`` mutation for the planned changes, to be sent
with a standalone ``gh api graphql -F query=@<file>`` command.

The script never calls GitHub itself, so it works where ``gh`` must run as its
own command and can be unit tested offline.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

OPEN_KEYS = ("backlog", "planned", "started")
CLOSED_KEYS = ("completed", "not_planned", "duplicate")
EVENTS = ("create", "start", "reopen", "complete", "set")
NODE_ID = re.compile(r"[A-Za-z0-9_=+/-]+")
CONFIRM = re.compile(r"(?:(?P<repo>[\w.-]+/[\w.-]+)#|#?)(?P<number>\d+)")


@dataclass
class Change:
    number: int
    repository: str
    issue_id: str
    from_status: str | None
    to_status: str
    status_id: str
    reason: str
    closes: bool = False
    reopens: bool = False
    duplicate_issue_id: str | None = None


@dataclass
class Plan:
    available: bool
    skip_reason: str | None = None
    changes: list[Change] = field(default_factory=list)
    proposals: list[Change] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    follow_up: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class Statuses:
    """The repository's planning statuses, resolved by category key."""

    def __init__(self, nodes: list[dict[str, Any]]):
        self.nodes = nodes
        self.by_id = {n["id"]: n for n in nodes}

    def in_category(self, key: str) -> list[dict[str, Any]]:
        return [n for n in self.nodes if n["category"]["key"] == key]

    def pick(self, key: str, *, review: bool = False) -> dict[str, Any] | None:
        candidates = self.in_category(key)
        if not candidates:
            return None
        if key == "started":
            reviewish = [n for n in candidates if "review" in n["name"].lower()]
            working = [n for n in candidates if n not in reviewish]
            if review:
                return (reviewish or candidates[-1:])[0]
            progress = [n for n in working if n["name"].lower() == "in progress"]
            # Never fall back to a review status for ordinary work; let the caller warn instead.
            choices = progress or working
            return choices[0] if choices else None
        return candidates[0]

    def by_name(self, name: str) -> dict[str, Any] | None:
        for node in self.nodes:
            if node["name"].lower() == name.lower():
                return node
        return None


def category(issue: dict[str, Any]) -> str | None:
    status = issue.get("status")
    if status:
        return status["category"]["key"]
    # An issue without a status still has a state; treat it by state.
    if issue.get("state") == "CLOSED":
        return {"NOT_PLANNED": "not_planned", "DUPLICATE": "duplicate"}.get(
            issue.get("stateReason") or "", "completed"
        )
    return None


def rank(issue: dict[str, Any]) -> int:
    """Order statuses so propagation only moves issues forward."""
    key = category(issue)
    if key is None or key == "backlog":
        return 0
    if key == "planned":
        return 1
    if key == "started":
        name = (issue.get("status") or {}).get("name", "")
        return 3 if "review" in name.lower() else 2
    return 4


def status_rank(node: dict[str, Any]) -> int:
    return rank({"status": {"name": node["name"], "category": node["category"]}})


def ancestors(issue: dict[str, Any]) -> list[dict[str, Any]]:
    chain = []
    parent = issue.get("parent")
    while parent:
        chain.append(parent)
        parent = parent.get("parent")
    return chain


def repo_of(issue: dict[str, Any]) -> str:
    return (issue.get("repository") or {}).get("nameWithOwner", "")


def owner_of(issue: dict[str, Any]) -> str:
    return repo_of(issue).split("/")[0].lower()


def nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    return (connection or {}).get("nodes") or []


class Planner:
    def __init__(self, context: dict[str, Any], args: argparse.Namespace):
        repository = context["data"]["repository"]
        self.issue = repository["issue"]
        statuses = repository.get("planningStatuses")
        self.statuses = Statuses(nodes(statuses)) if statuses else None
        self.args = args
        self.repo = repo_of(self.issue)
        self.confirmed = {self.parse_confirmation(value) for value in args.confirm_close or []}
        self.plan = Plan(available=True)
        self.owner = owner_of(self.issue)

    # -- helpers -----------------------------------------------------------

    def parse_confirmation(self, value: str) -> str:
        match = CONFIRM.fullmatch(value.strip())
        if not match:
            raise SystemExit(f"--confirm-close expects NUMBER or OWNER/REPO#NUMBER, not {value!r}")
        return f"{(match['repo'] or self.repo).lower()}#{match['number']}"

    def key(self, issue: dict[str, Any]) -> str:
        return f"{(repo_of(issue) or self.repo).lower()}#{issue['number']}"

    def label(self, issue: dict[str, Any]) -> str:
        repo = repo_of(issue)
        if repo and repo.lower() != self.repo.lower():
            return f"{repo}#{issue['number']}"
        return f"#{issue['number']}"

    def make_change(self, issue: dict[str, Any], target: dict[str, Any], reason: str) -> Change:
        current = issue.get("status")
        # Any move into a closing status needs confirmation, including reclassifying a closed issue.
        # add() has already skipped a no-op to the identical status.
        closes = target["category"]["key"] in CLOSED_KEYS
        reopens = target["category"]["key"] in OPEN_KEYS and issue.get("state") == "CLOSED"
        return Change(
            number=issue["number"],
            repository=(issue.get("repository") or {}).get("nameWithOwner", ""),
            issue_id=issue["id"],
            from_status=current["name"] if current else None,
            to_status=target["name"],
            status_id=target["id"],
            reason=reason,
            closes=closes,
            reopens=reopens,
        )

    def add(self, issue: dict[str, Any], target: dict[str, Any] | None, reason: str) -> Change | None:
        if target is None:
            self.plan.warnings.append(
                f"{self.label(issue)}: no status fits '{reason}'; this repository's statuses differ from the defaults"
            )
            return None
        if (issue.get("status") or {}).get("id") == target["id"]:
            return None
        if issue is not self.issue and owner_of(issue) and owner_of(issue) != self.owner:
            self.plan.warnings.append(
                f"{self.label(issue)} is in {issue['repository']['nameWithOwner']}; the status ID comes from this"
                f" repository, so if the mutation rejects it, read that repository's statuses and set"
                f" '{target['name']}' (category {target['category']['key']}) on it with that repository's ID"
            )
        change = self.make_change(issue, target, reason)
        if change.closes and self.key(issue) not in self.confirmed:
            self.plan.proposals.append(change)
        else:
            self.plan.changes.append(change)
        return change

    def promote(self, issue: dict[str, Any], target: dict[str, Any] | None, reason: str) -> None:
        """Move an open issue forward to target; never move it back."""
        if target is not None and rank(issue) >= status_rank(target):
            return
        self.add(issue, target, reason)  # warns when target is None

    def promote_ancestors(self, reason: str, *, reopen_completed: bool) -> None:
        in_progress = self.statuses.pick("started")
        for ancestor in ancestors(self.issue):
            key = category(ancestor)
            if key in ("not_planned", "duplicate"):
                self.plan.warnings.append(
                    f"{self.label(ancestor)} is closed as {ancestor['status']['name'] if ancestor.get('status') else key};"
                    " it was left unchanged and propagation stopped there"
                )
                return
            if key == "completed":
                if reopen_completed:
                    self.add(ancestor, in_progress, f"{reason}; reopened because a sub-issue has open work")
                continue
            self.promote(ancestor, in_progress, reason)

    def reopen_completed_ancestors(self, reason: str) -> None:
        """Return completed ancestors to In progress without promoting open ones; work has not started."""
        in_progress = self.statuses.pick("started")
        for ancestor in ancestors(self.issue):
            key = category(ancestor)
            if key in ("not_planned", "duplicate"):
                self.plan.warnings.append(
                    f"{self.label(ancestor)} is closed as {ancestor['status']['name'] if ancestor.get('status') else key};"
                    " it was left unchanged and propagation stopped there"
                )
                return
            if key == "completed":
                self.add(ancestor, in_progress, f"{reason}; reopened because a sub-issue has open work")

    def promote_backlog_children(self) -> None:
        """A started parent moves its Backlog sub-issues to Todo; they have not started themselves."""
        todo = self.statuses.pick("planned")
        children = nodes(self.issue.get("subIssues"))
        total = (self.issue.get("subIssuesSummary") or {}).get("total", len(children))
        if len(children) < total:
            self.plan.warnings.append(
                f"{self.label(self.issue)} has {total} sub-issues; only the first {len(children)} were checked for Backlog"
            )
        for child in children:
            if child.get("state") == "OPEN" and rank(child) == 0:
                self.promote(child, todo, f"parent {self.label(self.issue)} started")

    def sync_parent_completion(self) -> None:
        """Propose Done for the parent once this issue's closure leaves no open sub-issue."""
        parent = self.issue.get("parent")
        if not parent or parent.get("state") == "CLOSED":
            return
        # Count this issue as closed only if it already is, or its closure is a confirmed change.
        # An unconfirmed closure stays a proposal, so the parent must not be closed on its account.
        closure = next((c for c in self.plan.changes if c.issue_id == self.issue["id"] and c.closes), None)
        if closure:
            final_key = self.statuses.by_id[closure.status_id]["category"]["key"]
        elif category(self.issue) in CLOSED_KEYS:
            final_key = category(self.issue)
        else:
            self.plan.follow_up.append(
                f"After {self.label(self.issue)} is confirmed closed, re-run the event to check {self.label(parent)}"
            )
            return
        children = nodes(parent.get("subIssues"))
        total = (parent.get("subIssuesSummary") or {}).get("total", len(children))
        if len(children) < total:
            self.plan.warnings.append(
                f"{self.label(parent)} has more than {len(children)} sub-issues; check completion manually"
            )
            return

        def final_category(child: dict[str, Any]) -> str | None:
            # This issue's status in the parent's list is stale; use the event's outcome instead.
            return final_key if child.get("id") == self.issue["id"] else category(child)

        if children and all(final_category(c) in CLOSED_KEYS for c in children):
            def completed_child(child: dict[str, Any]) -> bool:
                return final_category(child) == "completed"

            if not any(completed_child(c) for c in children):
                self.plan.warnings.append(
                    f"All sub-issues of {self.label(parent)} are closed without completion; decide its status manually"
                )
                return
            change = self.add(parent, self.statuses.pick("completed"), "all sub-issues are completed")
            if change and parent.get("parent"):
                self.plan.follow_up.append(
                    f"After {self.label(parent)} is Done, run the complete event for {self.label(parent)}"
                    " to check its own parent"
                )

    # -- events ------------------------------------------------------------

    def run(self) -> Plan:
        if self.statuses is None or not self.statuses.nodes:
            return Plan(available=False, skip_reason="issue statuses are not available for this repository or viewer")
        if self.issue.get("viewerCanSetStatus") is False:
            return Plan(available=False, skip_reason="the viewer cannot set statuses on this issue")
        getattr(self, f"event_{self.args.event}")()
        self.drop_superseded()
        return self.plan

    def drop_superseded(self) -> None:
        """Keep one write per issue: a confirmed closure supersedes an interim promotion of the same issue.

        An unconfirmed closure keeps the promotion, so a declined proposal still leaves the
        issue consistent, and the proposal starts from the promoted status.
        """
        closing = {c.issue_id for c in self.plan.changes if c.closes}
        self.plan.changes = [c for c in self.plan.changes if c.closes or c.issue_id not in closing]
        interim = {c.issue_id: c.to_status for c in self.plan.changes}
        for proposal in self.plan.proposals:
            proposal.from_status = interim.get(proposal.issue_id, proposal.from_status)

    def event_create(self) -> None:
        planned = bool(nodes(self.issue.get("assignees")) or self.issue.get("milestone") or self.args.from_plan)
        target = self.statuses.pick("planned" if planned else "backlog")
        reason = "new issue is planned work" if planned else "new issue is not yet planned"
        if self.issue.get("state") == "CLOSED":
            self.plan.warnings.append(f"{self.label(self.issue)} is already closed; its status was left unchanged")
            return
        if self.issue.get("status") is None:
            self.add(self.issue, target, reason)
        else:
            self.promote(self.issue, target, reason)
        self.reopen_completed_ancestors(f"new sub-issue {self.label(self.issue)} was added")

    def event_start(self) -> None:
        in_progress = self.statuses.pick("started")
        for blocker in nodes(self.issue.get("blockedBy")):
            if blocker.get("state") == "OPEN":
                self.plan.warnings.append(
                    f"{self.label(self.issue)} is blocked by open {self.label(blocker)} ({blocker.get('title', '')})"
                )
        if in_progress is None:
            reason = "work started on a closed issue; reopened" if self.issue.get("state") == "CLOSED" else "work started"
            self.add(self.issue, in_progress, reason)
            return
        if self.issue.get("state") == "CLOSED":
            change = self.add(self.issue, in_progress, "work started on a closed issue; reopened")
            if change is None:
                return
        elif rank(self.issue) == 3:
            self.plan.warnings.append(f"{self.label(self.issue)} is already In review; it was not moved back")
        else:
            self.promote(self.issue, in_progress, "work started")
        self.promote_ancestors(f"sub-issue {self.label(self.issue)} started", reopen_completed=True)
        self.promote_backlog_children()

    def event_reopen(self) -> None:
        todo = self.statuses.pick("planned")
        if self.issue.get("state") == "CLOSED":
            change = self.add(self.issue, todo, "issue reopened")
            if change is None:
                return
        else:
            # Reopening on GitHub resets the status to Backlog; a reopened issue is still planned work.
            self.promote(self.issue, todo, "issue reopened")
        self.reopen_completed_ancestors(f"sub-issue {self.label(self.issue)} reopened")

    def event_complete(self) -> None:
        if category(self.issue) != "completed":
            self.add(self.issue, self.statuses.pick("completed"), "work completed")
        self.promote_ancestors(f"sub-issue {self.label(self.issue)} completed", reopen_completed=False)
        self.sync_parent_completion()

    def event_set(self) -> None:
        if not self.args.status:
            raise SystemExit("--status is required for the set event")
        target = self.statuses.by_name(self.args.status)
        if target is None:
            names = ", ".join(n["name"] for n in self.statuses.nodes)
            raise SystemExit(f"Unknown status '{self.args.status}'. Available: {names}")
        key = target["category"]["key"]
        change = self.add(self.issue, target, f"explicit request for {target['name']}")
        if key == "duplicate":
            if not self.args.duplicate_of or not NODE_ID.fullmatch(self.args.duplicate_of):
                raise SystemExit("--duplicate-of <issue node id> is required for a duplicate status")
            if change:
                change.duplicate_issue_id = self.args.duplicate_of
        if key == "started":
            self.promote_ancestors(f"sub-issue {self.label(self.issue)} started", reopen_completed=True)
            self.promote_backlog_children()
        elif key == "completed":
            self.promote_ancestors(f"sub-issue {self.label(self.issue)} completed", reopen_completed=False)
            self.sync_parent_completion()
        elif key in ("not_planned", "duplicate"):
            self.sync_parent_completion()
        elif change and change.reopens:
            self.reopen_completed_ancestors(f"sub-issue {self.label(self.issue)} reopened")


def mutation_text(changes: list[Change]) -> str:
    lines = ["mutation {"]
    for index, change in enumerate(changes):
        for value in (change.issue_id, change.status_id, change.duplicate_issue_id):
            if value is not None and not NODE_ID.fullmatch(value):
                raise SystemExit(f"Refusing to build a mutation with an unexpected node id: {value!r}")
        extra = f', duplicateIssueId: "{change.duplicate_issue_id}"' if change.duplicate_issue_id else ""
        lines.append(
            f'  m{index}: setIssueStatus(input: {{issueId: "{change.issue_id}", statusId: "{change.status_id}"{extra}}})'
            " { issue { number state status { name } } }"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--context", required=True, help="file with the JSON output of queries/issue-context.graphql, or - for stdin"
    )
    parser.add_argument("--event", required=True, choices=EVENTS)
    parser.add_argument("--from-plan", action="store_true", help="create: the issue comes from an approved plan")
    parser.add_argument("--status", help="set: the status name to apply")
    parser.add_argument("--duplicate-of", help="set Duplicate: node id of the original issue")
    parser.add_argument(
        "--confirm-close",
        action="append",
        metavar="NUMBER",
        help="issue the user confirmed may be closed, as NUMBER (this repository) or OWNER/REPO#NUMBER; repeat per issue",
    )
    parser.add_argument("--mutation-out", help="write a setIssueStatus mutation for the planned changes here")
    return parser.parse_args(argv)


STATUS_FIELDS = {"planningStatuses", "status", "viewerCanSetStatus"}


def is_missing_status_field(error: dict[str, Any]) -> bool:
    """True for a GraphQL 'field does not exist' error on one of the issue-status fields."""
    extensions = error.get("extensions") or {}
    if extensions.get("code") == "undefinedField":
        return extensions.get("fieldName") in STATUS_FIELDS
    match = re.match(r"Field '(\w+)' doesn't exist on type '(Repository|Issue)'", error.get("message", ""))
    return bool(match and match.group(1) in STATUS_FIELDS)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    raw = sys.stdin.read() if args.context == "-" else Path(args.context).read_text(encoding="utf-8")
    context = json.loads(raw)
    errors = context.get("errors") or []
    if errors and all(is_missing_status_field(e) for e in errors):
        # A GitHub server without the issue-status schema rejects the fields instead of returning null.
        plan = Plan(available=False, skip_reason="this GitHub server does not support issue statuses")
    elif errors or not ((context.get("data") or {}).get("repository") or {}).get("issue"):
        raise SystemExit(f"The context JSON has no issue: {json.dumps(errors)}")
    else:
        plan = Planner(context, args).run()
    if args.mutation_out:
        out = Path(args.mutation_out)
        if plan.changes:
            out.write_text(mutation_text(plan.changes), encoding="utf-8")
        elif out.exists():
            out.unlink()
    json.dump(plan.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
