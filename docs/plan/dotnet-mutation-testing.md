# .NET Mutation Testing Plugin

## Summary

`dotnet-mutation-testing` runs Stryker.NET mutation testing against the existing MSTest unit tests of a .NET consumer repository. A mutation run rebuilds and reruns the tests for many mutants, so it runs once, right before a pull request is opened, and only on code changed against the PR base branch. The regular unit test run stays unchanged.

Tracking: [Issue #113](https://github.com/tfsugjp/skills/issues/113).

## Design

- Keep it a separate plugin from `dotnet-azure-lessons`, which holds phase-based rules. `dotnet-testing` and `pr-issue-workflow` point to it, when installed.
- Pin `dotnet-stryker` in the repository's local tool manifest, reusing an existing manifest. Never install it globally. Validate the version with `nuget-validate` before pinning.
- Keep thresholds, generated-code excludes, and `since.ignore-changes-in` (for `stryker-config.json`) in a root `stryker-config.json`. Pass the base branch on the command line as `--since:origin/<base>`, because it changes per PR. Ignore `StrykerOutput/`. Ask before adding files to the consumer repository.
- Detect the VSTest or Microsoft.Testing.Platform runner from the repository root `global.json` and pass `--test-runner` to Stryker, which defaults to VSTest.
- Diff mode includes uncommitted changes. Any changed non-C# file that Stryker attributes to a test project makes it test every mutant. The helper detects that fallback from the log, stops the process tree, lists the files, and requires an explicit `--allow-full-run`. It also enforces a time budget.
- Write reports to a fixed `--output` path. Summarize Survived and NoCoverage mutants (file, line, mutator, replacement) and propose MSTest tests for high-risk survivors without chasing a 100% score. Pass/fail comes only from the Stryker exit code (`thresholds.break`).
- Implement the helper as a single-file C# app resolved from the skill directory, so consumer .NET repositories need no other runtime and no repository-relative path.
- Never add mutation testing to `dotnet test`, pre-commit hooks, or every-build CI. Optional templates run on the listed PR events or manually, not on ordinary pushes to the PR: GitHub Actions on `pull_request: types: [opened, reopened, ready_for_review]` for non-draft PRs or `workflow_dispatch` with `fetch-depth: 0`, and a manual Azure Pipelines pipeline with `fetchDepth: 0`. Both call a copy of the helper (`eng/mutation-run.cs`) so the fallback stop, time budget, and runner detection apply in CI, and pass the base branch through a validated environment variable instead of interpolating it into script text.

## Verification

A sample based on the Microsoft Learn `PriceCalculator` example (MSTest 4, net11.0, .NET SDK 11.0.100, Stryker.NET 5.1.0) covers a full run (68.75%, the same five survivors as the article), a diff run against the base branch, a break-threshold failure with exit code 2, the full-run fallback caused by uncommitted non-C# files, `since.ignore-changes-in`, both VSTest and MTP runners, and the helper's summary. Marketplace metadata and relative skill links are checked by `scripts/validate_marketplaces.py`.
