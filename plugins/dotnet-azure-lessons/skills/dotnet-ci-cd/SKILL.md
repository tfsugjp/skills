---
name: dotnet-ci-cd
description: 'Guidance for .NET CI workflows, build matrices, packaging, and releases. Use when editing GitHub Actions or Azure Pipelines, triggers, permissions, fork handling, runner choice, release and tag workflows, .NET packaging, solution selection, or NuGet audit policy.'
---

# .NET CI/CD

## When not to use

- Queuing, monitoring, or reading Azure Pipelines runs: `azure-devops-pipelines`.
- Choosing or upgrading NuGet package versions: `nuget-validate`.
- Dependabot pull requests: `dependabot-safe-merge`.
- Investigating a specific failed run: `dotnet-debugging`.

## Rules

### 1. Keep untrusted pull-request code away from privileged credentials

- **Rule:** Do not expose secrets, personal access tokens, protected variable groups, or OIDC write permissions to jobs that execute untrusted pull-request code. Fork behavior and available protections differ by platform; verify the repository's trigger and permissions. Unprivileged build, test, or package-validation jobs may run on pull requests. Keep credentialed publish, deploy, and release steps behind an appropriate trusted event and environment gate.
- **Check:** Trace each job that executes pull-request code and each privileged step; confirm the event and permissions cannot expose credentials to untrusted code.
- **Why:** Pull-request jobs were found with release credentials or OIDC permissions, while ordinary validation does not require those privileges.

### 2. Keep sample workflows outside the active workflow folder

- **Rule:** Store examples outside `.github/workflows/` so GitHub does not execute them.
- **Check:** Every file under `.github/workflows/` is intended to run in this repository.
- **Why:** A user-facing example was nearly added to the active workflow folder.

### 3. Avoid duplicate runs and match runner cost to the request

- **Rule:** Review overlapping `pull_request`, branch `push`, and tag triggers so the same change does not run redundant full checks. Use concurrency cancellation when superseded work has no required side effects. When the user limits runner cost, place expensive OS jobs on the branches or releases needed to preserve the stated coverage.
- **Check:** Inspect representative PR-branch, default-branch, and tag events; confirm the jobs and cost match repository policy.
- **Why:** Push and pull-request triggers duplicated runs, and macOS/Windows runner usage exhausted the available budget.

### 4. Allow Windows targeting on non-Windows runners

- **Rule:** When restoring, building, or packing Windows-targeted projects (`net*-windows`, WPF, WinForms, VSIX) on Linux or macOS, set `<EnableWindowsTargeting>true</EnableWindowsTargeting>` or exclude those projects from that job.
- **Check:** The job restores and packs without a targeting error.
- **Why:** Packing a Windows-targeted project failed on a non-Windows runner.

### 5. Align build, test, and release matrices with supported platforms

- **Rule:** Build and publish the operating systems and runtime identifiers the project supports and release scope promises. Run platform-sensitive tests on the matching native runner when required and available; do not claim an x64 cross-build establishes ARM64 runtime behavior.
- **Check:** Each released artifact maps to its target OS/RID, with a relevant test or an explicit verification gap.
- **Why:** ARM64 was missing from the release, and an x64 run was mistakenly treated as ARM64 test coverage.

### 6. Build the intended solutions and projects

- **Rule:** Include each solution and project required by the repository's build contract. Use the chosen solution format consistently in CI, scripts, and documentation (`dotnet-architecture-design`, "Prefer .slnx for new supported solutions").
- **Check:** Compare the project set in the workflow with the repository's intended solutions and projects.
- **Why:** CI built one of two solutions while the other contained unregistered projects.

### 7. Assess NuGet audit findings and record justified exceptions

- **Rule:** For `NU1901`–`NU1904`, identify whether the vulnerable package is direct or transitive and check supported patched versions. Prefer upgrading within the supported range; add a direct reference for a vulnerable transitive dependency when appropriate. Suppress an audit warning only when a documented, reviewed exception is justified by the actual exposure and mitigation.
- **Check:** Each finding is fixed or has a scoped rationale; no blanket suppression hides unrelated warnings.
- **Why:** A vulnerable transitive cryptography dependency was resolved with a patched compatible version.

### 8. Pin third-party actions and verify target platforms

- **Rule:** Follow repository or user policy for pinning third-party actions; when full commit pinning is required, include a version comment. Verify platform jobs through the configured CI or the corresponding local environment; a push is not evidence that jobs passed.
- **Check:** Action references satisfy the applicable policy, and each required platform result is read or marked unverified.
- **Why:** An approved plan required pinned actions, and a workflow that passed on Windows failed on Linux.

### 9. Match release state, assets, and tag protections to the requested policy

- **Rule:** Configure draft or published release state and tag protection as the user and repository require. Validate release automation with a safe pre-release or draft workflow where available; do not create a public release or tag unless authorized.
- **Check:** Confirm the resulting release state, expected assets, and that any tag ruleset targets tags.
- **Why:** A release needed to remain a draft for manual promotion, and a branch ruleset did not protect tags.

### 10. State where local verification gaps are covered

- **Rule:** When a test requires a service, identity, or platform unavailable locally, identify the CI job or environment that can run it and state whether it actually ran. If hosted CI is unavailable and the user requests verification, run feasible workflow steps locally and list what remains unverified.
- **Check:** Each unavailable local check is linked to an observed external result or clearly marked not run.
- **Why:** Database-container tests were moved to Linux CI when the required service could not run locally.
