---
name: dependabot-safe-merge
description: Safely review, refresh, and merge Dependabot pull requests after selecting the newest stable release that has been public for at least 24 hours. Use for a Dependabot PR URL or owner/repository#number, including grouped updates, security updates, major upgrades, breaking-change review, and implementation-plan issue creation.
---

# Dependabot Safe Merge

Use the required GitHub Connector for repository, pull request, review, check, comment, draft, issue, and auto-merge operations. Use local package managers only for a bounded update of the pull request branch.

## Guardrails

- Accept a pull request URL or `owner/repository#number`. If no target is supplied, list candidates and ask the user to select one. Process all candidates only after an explicit request and do so serially.
- Require an open pull request authored by `dependabot[bot]`, repository write permission, a captured head SHA, and identifiable manifest or lock files.
- Read repository `AGENTS.md`, contribution rules, issue and pull-request templates, Dependabot configuration, merge settings, branch protection, review state, and changed files before writing.
- Apply the independent 24-hour publication rule to every update, including security updates. Never rely on Dependabot cooldown settings.
- Never force-push, bypass administrators, expose credentials, accept mutable GitHub Actions tags, or merge when evidence is incomplete.
- Stop with `blocked` for missing publication times, private-registry authentication gaps, unsupported version schemes, unexpected files, or changing policy results.

## Workflow

1. Capture the pull request identity, author, state, base, head branch, head SHA, dependency group, ecosystem, current version, proposed version, manifests, lock files, and repository merge method.
2. Read [ecosystems.md](references/ecosystems.md) for metadata normalization and native update rules. Normalize registry responses with `scripts/registry_metadata.py`, then evaluate them with `scripts/release_policy.py`.
3. Select the highest comparable, stable release whose UTC publication instant is no later than `now - 24 hours`. Exclude prerelease, yanked, retracted, unlisted, deprecated, draft, or timestamp-free records.
4. If the eligible target is newer than the pull request, comment exactly `@dependabot recreate` before any direct edit. Poll every 30 seconds for at most 20 attempts. Re-read the head SHA and diff after every change.
5. If recreate times out or remains stale, check out the same pull-request branch and run the ecosystem's native targeted updater with lifecycle scripts disabled where supported. Preserve the manifest declaration style, regenerate only the associated lock or verification files, and reject unexpected changes.
6. Requery the registry immediately before merge. Repeat refresh and re-evaluation at most three times. Return `blocked` when the target does not stabilize.
7. For a numeric major increase, a pre-1.0 minor boundary, or another ecosystem compatibility boundary, refresh the same pull request to the eligible target, convert the grouped pull request to Draft, and follow [major-upgrade-review.md](references/major-upgrade-review.md). Never merge it.
8. For a compatible non-major update, evaluate the latest pull-request snapshot with `scripts/pr_gate.py`. Do not enable auto-merge until required checks and reviews pass, no review threads remain unresolved, the branch is conflict-free, the changed files are expected, and the head SHA still matches.
9. Enable auto-merge with the repository's configured merge method. Never substitute an immediate merge for auto-merge. If any gate is pending, make no merge change and report that a later rerun is required.

## Deterministic policy tools

- Pass registry payloads to `python scripts/registry_metadata.py --ecosystem <name> --package <name>` on standard input. Feed its JSON output into `python scripts/release_policy.py`.
- Pass the release decision and the current pull-request snapshot to `python scripts/pr_gate.py`.
- Generate or compare a major-upgrade issue with `python scripts/major_plan.py`; search the exact marker before creating an issue.
- Treat script output as a lower-level decision aid. Repository policy and missing GitHub evidence can only make the result more restrictive.

## Completion report

Report the selected release and publication time, release-policy decision, refresh attempts, head SHA verification, files reviewed, check and review gates, major-review evidence, issue number when applicable, and whether auto-merge was enabled. Never print registry credentials or authenticated request headers.
