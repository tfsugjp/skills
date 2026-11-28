---
name: github-issue-status
description: 'Set and synchronize GitHub issue planning statuses (Backlog, Todo, In progress, In review, Done, Not planned, Duplicate) through the GraphQL setIssueStatus API: choose the initial status when an issue is created, move it to In progress when work starts, promote parent issues when a sub-issue starts, move Backlog sub-issues to Todo when a parent starts, return a completed parent to In progress when a sub-issue reopens, and propose Done for a parent once every sub-issue is complete. Use whenever you create a GitHub issue, start, pick up, or resume work on one, close or reopen one, or the user mentions issue status, "In progress", "着手", "ステータスを変更", "ステータスを更新", repository boards, or keeping parent and sub-issue statuses in sync — even if they only say "start working on #42".'
---

# GitHub Issue Status

GitHub issues have a planning status in addition to open/closed. `gh issue create` and `gh issue edit` have no status flag, and GitHub does not sync statuses between parent issues and sub-issues. This skill fills both gaps with GraphQL. The status is what teammates watch on repository boards, so keep it accurate at the moments the work actually changes: creation, start, reopen, and completion.

## How statuses work

- A repository's statuses come from `planningStatuses`. Each status belongs to a category whose `key` is stable: `backlog`, `planned`, `started`, `completed`, `not_planned`, `duplicate`. Names and IDs can differ per owner, so resolve statuses at runtime by category and never hardcode an `IS_…` ID.
- `In progress` and `In review` are both `started`. The script tells them apart by name.
- It also works the other way: closing an issue (`gh issue close --reason completed`, or a merged PR) sets `Done`. Read the status back after closing with another reason. Closing the issue itself needs no status write. What GitHub does not do is look at the parent, so run `complete` afterwards.
- `setIssueStatus` closes or reopens the issue when the category requires it. `Done`, `Not planned`, and `Duplicate` close the issue, and `Duplicate` also needs the original issue's node ID.
- GitHub already moves statuses on some events. Assigning a user sets `Todo`. Assigning an agent or linking a draft PR sets `In progress`. A ready-for-review or open linked PR sets `In review`. Don't duplicate these steps, and order your writes so the automations don't overwrite them.
- Statuses are in public preview and are rolling out gradually. When `planningStatuses` is null or `viewerCanSetStatus` is false, skip the status step, tell the user, and continue the main task. A GitHub server whose schema lacks the fields (an older GitHub Enterprise Server, for example) instead fails the query with `Field '…' doesn't exist` errors. Pass that output to the script anyway: it reports `available: false` for those errors and still raises any other error. A missing status feature never blocks issue work.

## Workflow

Each event uses the same three steps: read the context, plan the changes, apply them and read back.

### 1. Read the issue context

[queries/issue-context.graphql](queries/issue-context.graphql) returns the statuses, the issue, its assignees, milestone, open blockers, direct sub-issues, and the ancestor chain in one call:

```bash
gh api graphql -F query=@<skill-dir>/queries/issue-context.graphql -F owner=<owner> -F repo=<repo> -F number=<n> > <scratch>/ctx.json
```

Run `gh` as its own command. Some agent sandboxes allow authenticated `gh` only when it is the first and only command on the line, and then a redirect or pipe also fails. In that case, run the command without the redirect and save its JSON output to `<scratch>/ctx.json` with your file-writing tool. Re-read the context after every write. Old context leads to wrong plans.

### 2. Plan the changes

```bash
python3 <skill-dir>/scripts/plan_transitions.py --context <scratch>/ctx.json --event <event> --mutation-out <scratch>/status.graphql
```

| Event | When | What the plan does |
|---|---|---|
| `create` | Right after creating an issue. Add `--from-plan` for issues created from an approved plan. | Sets `Todo` when the issue is assigned, has a milestone, or comes from a plan; otherwise leaves it in `Backlog`. A new open sub-issue reopens completed ancestors to `In progress`, and leaves open ancestors as they are. |
| `start` | Work begins on the issue: you or the user picks it up, a branch is created for it, or implementation starts. | Sets `In progress`. Promotes every ancestor to `In progress`, and reopens completed ones. Moves `Backlog` direct sub-issues to `Todo`. Warns about open `blocked-by` issues. |
| `reopen` | A closed issue is reopened without starting work yet, or was just reopened on GitHub (which resets its status to `Backlog`). | Sets `Todo` and moves completed ancestors back to `In progress`. Open ancestors keep their status, because work has not started. |
| `complete` | The issue's work is finished, or a PR merge just closed it. | Proposes `Done` for the issue unless it is already `Done`, including reclassifying an issue closed as not planned. Promotes open ancestors to at least `In progress`, and proposes `Done` for the parent when no sub-issue is left open. |
| `set --status <name>` | The user names a specific status, for example `Not planned`. For `Duplicate`, add `--duplicate-of <node-id>`. | Sets it, even backwards, because the user asked for it. Then runs the matching propagation: `start` for a started status (ancestors and `Backlog` sub-issues), `complete` for a closing one, and `reopen` when an open status reopens a closed issue. Pass `--confirm-close` for a closing status the user asked for. |

The script prints JSON with `changes` (safe to apply), `proposals` (they close an issue), `warnings`, and `follow_up`. It writes a mutation for `changes` only. Propagation only moves issues forward: it never moves an issue back from `In review` to `In progress`, or from `In progress` to `Todo`. The one exception is reopening a completed ancestor when a sub-issue has open work again. That reopen is a planned change; report it to the user.

### 3. Confirm closures, apply, and read back

- **Proposals need the user's yes.** Closing an issue notifies watchers and ends its tracking. Show each proposal (issue, current status, new status, reason) and ask. If they confirm, read the context again, because a sub-issue may have been added or reopened while you waited. Then re-run the plan with `--confirm-close <number>` for each confirmed issue (`--confirm-close <owner>/<repo>#<number>` for an issue in another repository), so the closure lands in the mutation. If the fresh plan no longer proposes the confirmed closure, or proposes a different one, don't apply it: show the new plan and ask again. An explicit request like "close #12 as not planned" is that confirmation: pass `--confirm-close 12` on the first run. Reclassifying an already closed issue, such as Not planned to Done, is a proposal too.
- **Warnings go to the user** as they are, especially open blockers on an issue being started. A blocker is a warning, not a stop: the user may have reasons to start anyway.
- Apply the mutation only when `changes` is non-empty. The mutation sets the target first, then its ancestors, in order:

  ```bash
  gh api graphql -F query=@<scratch>/status.graphql
  ```

- Read back with the context query and confirm each issue shows the planned status. Report what changed, for example `#41 Todo → In progress; parent #40 Backlog → In progress`. If a mutation errored for one issue (permissions on an ancestor, for example), report that issue separately. Don't call the whole step failed.
- Act on `follow_up`. After a parent is confirmed `Done`, run `complete` for that parent to check the next level up.

## Event recipes

### Creating issues

Create the issue as usual, including the assignees and milestone you intend to set (see [github-plan-issues](../github-plan-issues/SKILL.md) for plan-driven hierarchies). Then run `create`, adding `--from-plan` when the issue comes from an approved plan. For a parent plus sub-issues, run it for every issue you created. Report the final status of each.

### Starting work

1. Read the context and note the issue's current status and assignees.
2. Assign only if the person who will do the work is not assigned yet: `gh issue edit <n> --repo <owner>/<repo> --add-assignee @me`. Assignment triggers GitHub's `Todo` automation, which can move the issue back if `In progress` was set first.
3. Re-read the context. If assignment moved a started status (`In progress` or `In review`) back, restore it with `set --status "<status noted in step 1>"` before running `start`, so `start` keeps `In review` instead of replacing it.
4. Run `start`, apply, and read back.
5. Starting a parent issue does not mean its sub-issues have started. It moves `Backlog` sub-issues to `Todo` and leaves them otherwise untouched. When you begin a specific sub-issue, run `start` for that sub-issue.

### Pull requests

Leave PR-driven changes to GitHub. Linking a draft PR moves the issue to `In progress`, and marking it ready moves it to `In review`. After a merge closes the issue, run `complete` for it. That event exists for the parent: it proposes `Done` when the last sub-issue closes, and promotes ancestors otherwise. When you create or update the PR itself, use [github-pull-request](../github-pull-request/SKILL.md).

### Closing without completing

Use `set --status "Not planned"`, or `set --status Duplicate --duplicate-of <original node id>`. Get the original's node ID from the context query on that issue. Both close the issue. When the user asked for it, pass `--confirm-close <number>`; otherwise they stay proposals. When the last open sub-issue closes this way and none was completed, the script warns instead of proposing `Done`. Ask the user what the parent should be.

## Pitfalls

- `gh issue create` and `gh issue edit` have no `--status` flag. Don't invent one; use the mutation.
- Never hardcode status IDs from another repository or from this file's examples. IDs differ per owner.
- Sub-issues can live in another repository. The script still plans ancestors owned by another account, using this repository's status IDs, and warns. If the mutation rejects one of them, don't re-run the event from that repository, because a different event would plan a different transition. Read that repository's statuses with [queries/statuses.graphql](queries/statuses.graphql), find the status with the planned name and category, and apply exactly that transition to the ancestor with that repository's ID.
- The context query reads up to 100 sub-issues per issue and seven ancestor levels, which is GitHub's nesting limit. When a parent has more sub-issues, the script warns and leaves completion to you.
- Always pass `--repo <owner>/<repo>` to `gh issue` commands. The issue number alone is ambiguous outside the repository directory.

## Reference

- [queries/issue-context.graphql](queries/issue-context.graphql): everything the planner needs for one issue.
- [queries/statuses.graphql](queries/statuses.graphql): only the repository's statuses, to check availability or list names.
- [scripts/plan_transitions.py](scripts/plan_transitions.py): the offline transition planner. Its tests are in `tests/`.
