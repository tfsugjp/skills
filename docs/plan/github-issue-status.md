# GitHub Issue Status Skill

## Summary

Add a `github-issue-status` skill to the `github-plan-wiki` plugin. It sets an issue's planning status when the issue is created and when work starts, and keeps parent and sub-issue statuses consistent.

## Tracking

| Kind | Issue |
|---|---|
| Parent | [Issue #126](https://github.com/tfsugjp/skills/issues/126) |
| Sub-issue | [Issue #127](https://github.com/tfsugjp/skills/issues/127) |
| Sub-issue | [Issue #128](https://github.com/tfsugjp/skills/issues/128) |
| Sub-issue | [Issue #129](https://github.com/tfsugjp/skills/issues/129) |

## Background

GitHub issues now have a planning status besides open and closed ([changelog](https://github.blog/changelog/2026-11-23-issue-statuses-and-repository-boards-are-in-public-preview/)). The default statuses are Backlog, Todo, In progress, In review, Done, Not planned, and Duplicate. Each belongs to a category (`backlog`, `planned`, `started`, `completed`, `not_planned`, `duplicate`) that fixes the open/closed state. GitHub moves statuses on some events: assigning a user sets Todo, assigning an agent or linking a draft PR sets In progress, and a ready or open linked PR sets In review. GitHub does not propagate statuses between parent and sub-issues, and `gh` has no status flag. The GraphQL API exposes `Repository.planningStatuses`, `Issue.status`, `Issue.viewerCanSetStatus`, `CreateIssueInput.statusId`, and the `setIssueStatus` mutation, which closes or reopens the issue when the category requires it.

## Design

- **Runtime resolution.** Read `planningStatuses` for the repository and pick statuses by `category.key`; `In progress` and `In review` share `started`, so choose by name within it. Never hardcode status IDs. If `planningStatuses` is null or `viewerCanSetStatus` is false, skip the status step, say so, and continue the main task.
- **Standalone commands.** Reads and writes are standalone `gh api graphql` commands kept in a reference file. A bundled script only computes transitions from JSON, so it works where `gh` must run as its own command.
- **Creation.** `Todo` when the issue is assigned, has a milestone, or comes from an approved plan; otherwise `Backlog`. `gh issue create` has no status flag, so set the status with `setIssueStatus` right after creation and read it back.
- **Start.** Assign first, then set `In progress`, then read back, so the assignment automation cannot overwrite it. Warn when open `blocked-by` issues exist.
- **Parent and sub-issues.** A started child promotes every ancestor to `In progress`; a completed ancestor is reopened to `In progress`. A started parent promotes `Backlog` children to `Todo`. Statuses only move forward, except for the reopen case.
- **Completion.** When all sub-issues are completed, propose `Done` for the parent. `Done`, `Not planned`, and `Duplicate` close the issue, so they run only after confirmation. PR-driven `In progress` and `In review` stay with GitHub's automations.
- **Integration.** `github-plan-issues` uses the skill for initial statuses and readback instead of duplicating GraphQL.

## Implementation phases

1. Add the skill, the GraphQL reference, and the transition script with unit tests (Issue #127).
2. Wire `github-plan-issues` to the skill (Issue #128).
3. Update AGENTS.md, README, CHANGELOG, `docs/plan` in English and Japanese, and both plugin manifests (Issue #129).

## Verification

- Unit tests for every transition, the never-demote rule, and the unavailable-status case.
- Skill evaluation runs against a scratch repository, with and without the skill.
- `scripts/validate_marketplaces.py`, and English/Japanese consistency checks.
