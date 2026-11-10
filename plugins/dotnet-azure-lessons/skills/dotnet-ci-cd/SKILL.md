---
name: dotnet-ci-cd
description: 'Rules for GitHub Actions and Azure Pipelines definitions and packaging of .NET projects, learned from leaked-secret risks, duplicate runs, and missing platforms found in review. Use while editing workflow or pipeline YAML, triggers, fork pull-request handling, permissions, secrets, variable groups, OIDC federation, build matrices, release and tag workflows, rulesets, dotnet pack or VSIX or NuGet packaging, ARM64 builds, solution files, or NuGet audit warnings. Not for running or monitoring an Azure Pipelines run (azure-devops-pipelines) or choosing package versions (nuget-validate).'
---

# .NET CI/CD

## When not to use

- Queuing, monitoring, or reading Azure Pipelines runs: `azure-devops-pipelines`.
- Choosing or upgrading NuGet package versions: `nuget-validate`.
- Dependabot pull requests: `dependabot-safe-merge`.
- Investigating a specific failed run: `dotnet-debugging`.

## Rules

### 1. Keep secrets, OIDC, and fork code apart

- **Rule:** Jobs that run for pull requests receive no secrets, personal access tokens, secret variable groups, or `id-token: write`; gate release and packaging jobs with `if: github.event_name != 'pull_request'` or an Azure Pipelines condition on `Build.Reason`. Skip CI for pull requests from forks when the user asks (for example `if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository`, which keeps push and tag runs), and never use `pull_request_target` to build fork code.
- **Check:** For each job with secrets or OIDC, the trigger and condition exclude pull requests; fork pull requests start only the jobs the user allows.
- **Why:** A pull-request job had `id-token: write` and a release token, a pull-request pipeline referenced a variable group, and the user asked for fork pull requests not to run CI.

### 2. Keep sample workflows out of the active workflow folder

- **Rule:** Example workflows for users go outside `.github/workflows/` (for example `workflows/github-actions/`) so GitHub does not run them.
- **Why:** Example workflows were nearly added where they would run.

### 3. Avoid duplicate runs

- **Rule:** One change runs each check once: for example CI on `pull_request` plus `push` to the default branch, and release on tag push only, with branch filters that keep CI from also running for the tag. Use `concurrency` to cancel superseded runs.
- **Check:** A push to a PR branch, and a tag push, each start one run per check.
- **Why:** CI ran twice for every push to a PR branch, and a tag push started both the release and CI workflows.

### 4. Allow Windows targeting on non-Windows runners

- **Rule:** When Windows-targeted projects (`net*-windows`, WPF, WinForms, VSIX) are restored, built, or packed on Linux or macOS, set `<EnableWindowsTargeting>true</EnableWindowsTargeting>` in `Directory.Build.props`, or exclude them from that job.
- **Why:** A NuGet submission job failed on a non-Windows runner while packing a Windows-targeted project.

### 5. Carry every platform through build, test, and artifacts

- **Rule:** Each supported platform (x64, ARM64, each OS) appears in the build matrix, the test matrix (natively when a runner exists), and the published artifacts and checksums.
- **Check:** The release lists one artifact per platform, and each has a test job.
- **Why:** ARM64 was missing from the build and release notes, and ARM64 tests ran only on x64.

### 6. Build every solution and project

- **Rule:** CI builds every solution, and every project, including tests, belongs to one. Pipelines reference the `.slnx` path (`dotnet-architecture-design` rule 9) with an SDK that supports it.
- **Check:** `dotnet sln <solution>.slnx list` matches the project files; no workflow names an `.sln`.
- **Why:** CI validated one of two solutions, and the other had unregistered projects.

### 7. Fix NuGet audit warnings instead of suppressing them

- **Rule:** For `NU1901`–`NU1904` on a direct or transitive package, update to a patched version within the supported major (add a direct reference for a transitive package when needed). Do not add `NoWarn` or disable auditing.
- **Why:** A vulnerable transitive cryptography package was fixed by pinning a patched version.

### 8. Pin actions and check every runner OS before pushing

- **Rule:** Pin third-party actions to a full commit SHA with a version comment, and compare generated YAML with every explicit requirement in the approved plan. Before pushing a .NET change, build on each OS the workflow uses (or use a draft PR run).
- **Check:** `uses:` lines are SHA-pinned; the Linux job ran.
- **Why:** Generated workflows were not pinned although the plan required it, and a change that built on Windows failed in the Linux job.

### 9. Configure releases and protection as requested

- **Rule:** Create releases in the state the user chose (for example a draft that is promoted by hand), attach the installable artifacts, and create tag protection as a ruleset that targets tags, not branches.
- **Check:** A test tag produces a release in the expected state with the expected assets, and the ruleset target is `tag`.
- **Why:** Releases had to be changed to drafts, and a tag rule created under branch rulesets did not protect tags.

### 10. State where local-only gaps are verified

- **Rule:** When a test needs a service unavailable locally (a database container, a signed-in account), name the CI job that runs it and say it did not run locally.
- **Why:** SQL container tests could not run locally and were moved to the Linux CI job.

## Done checklist

- [ ] Pull-request jobs have no secrets or OIDC; fork pull requests run only allowed jobs.
- [ ] Sample workflows are outside `.github/workflows/`.
- [ ] One run per check per push or tag.
- [ ] Windows targeting is enabled where non-Windows runners restore Windows projects.
- [ ] Every platform has build, test, and artifact entries.
- [ ] Every solution and project is built through `.slnx` paths.
- [ ] NuGet audit warnings are fixed, not suppressed.
- [ ] Actions are SHA-pinned, generated YAML matches the plan, and every runner OS was exercised.
- [ ] Release state, assets, and tag rulesets match the request.
- [ ] Local gaps name the CI job that covers them.
