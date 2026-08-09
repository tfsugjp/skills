# Dependabot Safe Merge Implementation Plan

## Scope

- Parent issue: #20
- Plugin version: 0.1.0
- Marketplace category: Developer Tools
- Child issues: #21 plugin structure, #22 release policy engine, #23 GitHub workflow and major-upgrade review

## Release eligibility

For every Dependabot pull request, independently re-query the package registry and select the newest stable release across all major versions whose UTC publication timestamp is at least 24 hours old.

Reject prereleases, yanked, unlisted, retracted, deprecated, mutable tags, missing timestamps, unsupported version schemes, and insufficient registry authentication. Security updates have no 24-hour exception.

The supported metadata sources are npm/Yarn/pnpm, NuGet, pip/Poetry/uv, Maven/Gradle, Cargo, Go modules, and GitHub Actions. Registry metadata is normalized into release records before comparison.

## Refresh and merge flow

1. Validate the pull request author, open state, repository write permission, head SHA, manifest and lockfile scope, repository instructions, templates, Dependabot configuration, branch protection, and review state.
2. If a newer eligible release exists, issue the Dependabot recreate command first.
3. Poll at 30-second intervals for no more than 10 minutes, then re-check the head SHA and expected diff.
4. If necessary, update only the target dependency with the native package manager, preserve declaration style, regenerate the lock or verification metadata, and disable package-manager scripts where supported.
5. Re-query the registry immediately before merge. Repeat refresh evaluation at most three times and stop closed if the candidate is unstable.
6. Configure repository-default auto-merge only after required checks, reviews, threads, conflict state, branch protection, merge method, and current head SHA all pass.

No force-push, administrator bypass, secret output, unexpected file change, or direct merge is permitted.

## Major-upgrade review

A numeric major increase or ecosystem-specific compatibility boundary crossing causes the complete group pull request to become Draft. If Draft conversion is unavailable, apply the repository breaking-change convention and leave a blocking comment.

Review official migration guides, release notes, changelogs, and API documentation. Record removed or incompatible APIs, changed defaults, runtime and toolchain requirements, and evidence gaps. Map each change to repository usage, inspect the pull request diff and configuration/API call sites, and review build and test results.

Create or update one issue per dependency and target major using this fixed marker:

<!-- dependabot-safe-merge:key=<ecosystem>:<package>:<target-major> -->

Each issue must contain current and target versions, official evidence, breaking changes, affected code, staged implementation steps, tests, rollback, acceptance criteria, and unresolved questions. Link the pull request by issue number only.

## Validation

- 44 Python unit tests
- Quick skill validation
- JSON/YAML validation
- Marketplace validation
- Three fixture-only forward tests: compatible refresh, grouped major planning, and fail-closed cases
- Forward tests perform no live GitHub writes

## Implementation notes

The existing marketplace name and existing English SECURITY.md were preserved for compatibility. The application manifest retains the required GitHub Connector field even though the current validator schema does not yet accept that field.
