---
name: dotnet-ci-cd
description: 'Rules for GitHub Actions and Azure Pipelines definitions and packaging of .NET projects, learned from leaked-secret risks, duplicate runs, and missing platforms found in review. Use while editing workflow or pipeline YAML, triggers, fork pull-request handling, permissions, secrets, variable groups, OIDC federation, build matrices and runner choice, release and tag workflows, rulesets, dotnet pack or VSIX or NuGet packaging, ARM64 builds, solution files, or NuGet audit warnings.'
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
- **Why:** A pull-request job had `id-token: write` and a release token, and a pull-request pipeline referenced a variable group.

### 2. Keep sample workflows out of the active workflow folder

- **Rule:** Example workflows for users go outside `.github/workflows/` (for example `workflows/github-actions/`) so GitHub does not run them.
- **Check:** Every file under `.github/workflows/` is meant to run in this repository.
- **Why:** Example workflows were nearly added where they would run.

### 3. Run each check once, on runners the user is willing to pay for

- **Rule:** One change runs each check once: for example CI on `pull_request` plus `push` to the default branch, and release on tag push only, with branch filters that keep CI from also running for the tag. Use `concurrency` to cancel superseded runs. macOS and Windows runners cost more than Linux in private repositories; when the user limits cost, run those OS jobs only for the default branch or releases and keep pull-request checks on Linux.
- **Check:** A push to a PR branch, and a tag push, each start one run per check; the matrix per trigger matches what the user asked for.
- **Why:** CI ran twice for every push to a PR branch, a tag push started both release and CI, and the user asked to restrict macOS and Windows builds after the minutes ran out.

### 4. Allow Windows targeting on non-Windows runners

- **Rule:** When Windows-targeted projects (`net*-windows`, WPF, WinForms, VSIX) are restored, built, or packed on Linux or macOS, set `<EnableWindowsTargeting>true</EnableWindowsTargeting>` in `Directory.Build.props`, or exclude them from that job.
- **Check:** The non-Windows job restores and packs without a targeting error.
- **Why:** A NuGet submission job failed on a non-Windows runner while packing a Windows-targeted project.

### 5. Carry every platform through build, test, and artifacts

- **Rule:** Each supported platform (x64, ARM64, each OS and runtime identifier) appears in the build matrix, the test matrix, and the published artifacts and checksums. Run tests natively on ARM64 when a runner exists, not only an x64 cross-compile.
- **Check:** The release lists one artifact per platform, and each has a test job.
- **Why:** ARM64 was missing from the build and release notes, and ARM64 tests ran only on x64.

### 6. Build every solution and project

- **Rule:** CI builds every solution, and every project, including tests, belongs to one. Pipelines reference the `.slnx` path (`dotnet-architecture-design`, "Use .slnx as the solution format") with an SDK that supports it.
- **Check:** `dotnet sln <solution>.slnx list` matches the project files; no workflow names an `.sln`.
- **Why:** CI validated one of two solutions, and the other had unregistered projects.

### 7. Fix NuGet audit warnings instead of suppressing them

- **Rule:** For `NU1901`–`NU1904` on a direct or transitive package, update to a patched version within the supported major (add a direct reference for a transitive package when needed). Do not add `NoWarn` or disable auditing.
- **Check:** The build has no audit warnings and no new suppression.
- **Why:** A vulnerable transitive cryptography package was fixed by pinning a patched version.

### 8. Pin actions and check every runner OS before pushing

- **Rule:** Pin third-party actions to a full commit SHA with a version comment, and compare generated YAML with every explicit requirement in the approved plan. Before pushing a .NET change, build on each OS the workflow uses, or use a draft PR run and read its result.
- **Check:** `uses:` lines are SHA-pinned; each OS job's result was read.
- **Why:** Generated workflows were not pinned although the plan required it, and a change that built on Windows failed in the Linux job.

### 9. Configure releases and protection as requested

- **Rule:** Create releases in the state the user chose (for example a draft that is promoted by hand, so a failed release is undone by deleting the draft), attach the installable artifacts, and create tag protection as a ruleset that targets tags, not branches.
- **Check:** A test tag produces a release in the expected state with the expected assets, and the ruleset target is `tag`.
- **Why:** Releases had to be changed to drafts, and a tag rule created under branch rulesets did not protect tags.

### 10. State where local-only gaps are verified

- **Rule:** When a test needs a service unavailable locally (a database container, a signed-in account), name the CI job that runs it and say it did not run locally. When hosted CI is unavailable, run the workflow's steps locally in the same order and say which jobs could not be reproduced.
- **Check:** The report names the job or local command that covered each gap.
- **Why:** SQL container tests could not run locally and were moved to the Linux CI job, and a repository with hosted CI disabled needed its checks run locally before merge.

## Before reporting done

Confirm each applicable Check above, or state which one was not done.
