---
name: dotnet-ci-cd
description: 'Rules for GitHub Actions and Azure Pipelines definitions and packaging of .NET projects, learned from leaked-secret risks, duplicate runs, and missing platforms found in review. Use while editing workflow or pipeline YAML, triggers, permissions, secrets, variable groups, OIDC federation, build matrices, dotnet pack or VSIX or NuGet packaging, ARM64 builds, solution files, or NuGet audit warnings. Not for running or monitoring an Azure Pipelines run (azure-devops-pipelines) or choosing package versions (nuget-validate).'
---

# .NET CI/CD

## When not to use

- Queuing, monitoring, or reading Azure Pipelines runs: use `azure-devops-pipelines`.
- Choosing or upgrading NuGet package versions: use `nuget-validate`.
- Dependabot pull requests: use `dependabot-safe-merge`.
- Investigating a specific failed run: use `dotnet-debugging`.

## Rules

### 1. Keep secrets and OIDC out of pull-request builds

- **Rule:** Jobs and stages that run for pull requests receive no secrets, personal access tokens, variable groups with secrets, or `id-token: write`. Gate release and packaging jobs with conditions such as `if: github.event_name != 'pull_request'` or an Azure Pipelines stage condition on `Build.Reason`.
- **Check:** For each job with secrets or OIDC, the trigger and condition exclude pull requests.
- **Why:** A pull-request-triggered job had `id-token: write` and a release token, and a pull-request pipeline referenced a variable group in its packaging stage.

### 2. Keep sample workflows out of the active workflow folder

- **Rule:** Example or reference workflows for users go outside `.github/workflows/` (for example `workflows/github-actions/`), so GitHub does not run them.
- **Check:** `.github/workflows/` contains only workflows this repository runs.
- **Why:** Example workflows were nearly added where they would run.

### 3. Avoid duplicate runs

- **Rule:** Choose triggers so one change runs a check once: for example CI on `push` to every branch, or on `pull_request` plus `push` to the default branch only; releases on tag push. Use `concurrency` to cancel superseded runs.
- **Check:** Pushing to a branch with an open PR starts one run of each check.
- **Why:** CI ran twice for every push to a PR branch.

### 4. Allow Windows targeting on non-Windows runners

- **Rule:** When a solution includes Windows-targeted projects (`net*-windows`, WPF, WinForms, VSIX) and any job restores, builds, or packs on Linux or macOS, set `<EnableWindowsTargeting>true</EnableWindowsTargeting>` in `Directory.Build.props`, or exclude those projects from that job.
- **Check:** `dotnet restore` succeeds on every runner OS in the workflow.
- **Why:** A NuGet submission job failed on a non-Windows runner while packing a Windows-targeted project.

### 5. Carry every platform through build, test, and artifacts

- **Rule:** When a product supports x64 and ARM64 (or several OSes), each platform appears in the build matrix, the test matrix (natively when a runner exists), and the published artifacts and checksums.
- **Check:** The release lists one artifact per platform, and each has a test job.
- **Why:** ARM64 was missing from the build and release notes, and ARM64 tests ran only on x64.

### 6. Build every solution and project

- **Rule:** CI builds every solution in the repository, and every project, including test projects, is in a solution. Solutions are `.slnx` by default (see `dotnet-architecture-design`): pipelines reference the `.slnx` path, and the SDK installed by the job (`actions/setup-dotnet`, `UseDotNet@2`, or `global.json`) supports `.slnx` (9.0.200 or later).
- **Check:** Compare `dotnet sln <solution>.slnx list` for each solution with the project files in the repository; no workflow or pipeline still names an `.sln`.
- **Why:** CI validated only one of two solutions, and the other had projects that were not registered.

### 7. Fix NuGet audit warnings instead of suppressing them

- **Rule:** When `dotnet restore` reports `NU1901`–`NU1904` for a direct or transitive package, update to a patched version within the supported major version (add a direct reference for a transitive package when needed). Do not add `NoWarn` or disable auditing.
- **Check:** Restore has no audit warnings, and the dependency path of each updated package is known.
- **Why:** A vulnerable transitive cryptography package was fixed by pinning a patched version rather than hiding the warning.

### 8. Pin actions and check every runner OS before pushing

- **Rule:** Pin third-party actions to a full commit SHA with a version comment, and before pushing a .NET change, build on each OS the workflow uses (or rely on a draft PR run) rather than only on Windows.
- **Check:** `uses:` lines are SHA-pinned; the Linux job was run.
- **Why:** A change that built on Windows failed in the Linux job.

### 9. State where local-only gaps are verified

- **Rule:** When an integration test needs a service that is unavailable locally (Docker, a database container, a signed-in account), make the CI job that runs it explicit and say in the report that it did not run locally.
- **Check:** The CI job exists and the report names it.
- **Why:** SQL container tests could not run locally and were moved to the Linux CI job.

## Done checklist

- [ ] Pull-request jobs have no secrets, variable groups with secrets, or OIDC.
- [ ] Sample workflows are outside `.github/workflows/`.
- [ ] One run per check per push.
- [ ] Windows targeting is enabled where non-Windows runners restore Windows projects.
- [ ] Every platform has build, test, and artifact entries.
- [ ] Every solution and project is built, through `.slnx` paths with an SDK that supports them.
- [ ] NuGet audit warnings are fixed, not suppressed.
- [ ] Actions are SHA-pinned; every runner OS was exercised.
- [ ] Local gaps name the CI job that covers them.
