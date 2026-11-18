---
name: dotnet-mutation-testing
description: 'Run Stryker.NET mutation testing on existing MSTest unit tests once, right before opening a pull request, limited to code changed against the base branch. Use when asked to run mutation tests, check test strength or test quality before a PR, find surviving mutants, set up Stryker.NET or dotnet-stryker, or "ミューテーションテスト". Not for the regular test run: it never goes into dotnet test, pre-commit hooks, or every-build CI.'
---

# .NET Mutation Testing

Mutation testing checks whether unit tests detect behavior changes. Stryker.NET makes small code changes (mutants), reruns the tests, and reports mutants that survive. A survivor points to a missing or weak assertion. See [Mutation testing on Microsoft Learn](https://learn.microsoft.com/dotnet/core/testing/mutation-testing).

A mutation run rebuilds and reruns the tests for many mutants and is much slower than `dotnet test` (about 1.5 minutes for a single small class in a sample). Run it **once per pull request, right before opening it**, on the code changed against the PR base branch. Leave the regular unit test run unchanged.

The bundled helper [scripts/mutation-run.cs](scripts/mutation-run.cs) is a single-file C# app. Resolve it from this skill's directory (`<skill-dir>` below), not from a path in the consumer repository.

## When not to use

- Choosing or reporting regular verification for a change: `dotnet-testing`, when installed.
- Adding or updating NuGet packages: `nuget-validate`, when installed. Use it to validate the `dotnet-stryker` version before pinning it.
- Running mutation testing on every build, commit, or push. Do not add it to `dotnet test`, pre-commit hooks, or the regular CI pipeline.

## Prerequisites

- .NET SDK 10 or later (file-based apps with `dotnet run <file>.cs`). Verified with SDK 11.0.100.
- MSTest test projects. Verified with MSTest 4 in both VSTest and Microsoft.Testing.Platform (MTP) modes, targeting net11.0.
- A Git repository whose PR base branch exists as `origin/<base>`.

## Workflow

### 1. Inspect the repository

From the repository root, identify the solution, the MSTest test projects, and the test runner mode:

- `global.json` with `"test": { "runner": "Microsoft.Testing.Platform" }` means MTP mode; otherwise VSTest mode. `global.json` is resolved from the current directory, so check the repository root.
- MSTest test projects reference the `MSTest` package (or `MSTest.TestFramework`).
- Existing local tool manifest: `.config/dotnet-tools.json` or `dotnet-tools.json`.

### 2. Set up once (ask before changing the repository)

These changes are committed to the consumer repository, so describe them and get the user's agreement first. Skip anything already in place.

1. Validate the Stryker version with `nuget-validate` (for example `latest-safe dotnet-stryker`).
2. Pin it as a local tool. Reuse an existing manifest; never install globally.

   ```bash
   dotnet new tool-manifest
   dotnet tool install dotnet-stryker --version 5.1.0
   ```

   Run these in the repository root. Skip `dotnet new tool-manifest` when a manifest already exists.
3. Copy [templates/stryker-config.json](templates/stryker-config.json) to the repository root and adjust `thresholds` and `mutate` excludes. Do not put the base branch in the file; it changes per PR and is passed on the command line.
4. Add `StrykerOutput/` to `.gitignore`.

Land the setup on the base branch (merge it first) before relying on diff mode. Diff mode compares the working tree with `origin/<base>`, so setup files that exist only on the feature branch, committed or not, make it fall back to a full run (see Gotchas).

### 3. Run once before opening the PR

Fetch the base branch, then run the helper from the repository root. Always pass `--base` with the PR's actual base branch; the default (`origin/HEAD`) may point at another branch.

```bash
git fetch origin main
dotnet run <skill-dir>/scripts/mutation-run.cs -- run --base main
```

The helper:

- checks that `origin/<base>` and the local `dotnet-stryker` tool exist,
- detects VSTest or MTP mode and passes `--test-runner` to Stryker,
- runs `dotnet tool run dotnet-stryker -- --since:origin/<base>` with reports written to `StrykerOutput/pre-pr/reports/`,
- **stops the run** when diff mode falls back to testing every mutant, and lists the changed files that caused it,
- stops after a time budget (`--timeout-minutes`, default 30),
- prints the mutation summary when Stryker finishes.

| Exit code | Meaning | What to do |
|---|---|---|
| 0 | Score meets `thresholds.break` | Review survivors in changed code |
| 1 | Helper usage error, or a Stryker failure passed through (for example rejected options or a build failure) | Read the log; fix the arguments or the build |
| 2 | Score below `thresholds.break` (from Stryker) | Strengthen tests or discuss the threshold with the user |
| 3 | Missing base branch or tool, or Stryker exited 0 without writing a fresh report | Fix the precondition shown in the message |
| 4 | Diff mode fell back to a full run; stopped | Land or revert the listed files, or ask the user before `--allow-full-run` |
| 5 | Time budget exceeded; stopped | Report it; ask before rerunning with a larger `--timeout-minutes` |

Other Stryker exit codes are passed through. When the diff has no mutable C# changes (and no non-C# change that triggers the full-run fallback), Stryker ignores every mutant and exits 0; the helper prints that no mutants were tested and the score is `n/a`. Report that nothing was tested rather than a pass. Relative `--output` and `--solution` paths are resolved against the repository root.

Pass extra Stryker options after `--`. Stryker requires `break <= low <= high`, so raising `--break-at` above the configured `low` also needs `--threshold-low` (and `--threshold-high`); otherwise Stryker rejects the options with exit code 1:

```bash
dotnet run <skill-dir>/scripts/mutation-run.cs -- run --base main -- --threshold-high 95 --threshold-low 90 --break-at 90
```

Use `--json` for machine-readable output (Stryker's own log goes to stderr).

### 4. Act on survivors

Summarize an existing report at any time:

```bash
dotnet run <skill-dir>/scripts/mutation-run.cs -- summarize --report StrykerOutput/pre-pr/reports/mutation-report.json
```

For each `Survived` or `NoCoverage` mutant, read the original code at the reported line and the replacement:

- Equality mutants (`price <= 0` -> `price < 0`) usually need a boundary test.
- String mutants (`"message"` -> `""`) are killed by asserting the exception message, when the message matters.
- `NoCoverage` means no test reaches the code at all.

Propose MSTest tests for business-critical and high-risk survivors first. Do not chase a 100% score, and do not weaken or skip mutants just to pass the threshold. After adding tests, rerun the helper once.

### 5. Report

Report the final mutation score (Stryker's final line is authoritative), the exit code, the base branch compared, the test runner mode, survivors addressed and left open, and anything not run (for example a fallback that was stopped or a timeout).

## Optional CI

When the user wants the same check in CI, offer one of these templates. They run on the listed PR events or manually, not on ordinary pushes to the PR:

- GitHub Actions: [templates/github-actions-mutation-testing.yml](templates/github-actions-mutation-testing.yml) (`pull_request: types: [opened, reopened, ready_for_review]` for non-draft PRs, plus `workflow_dispatch` for manual reruns; `fetch-depth: 0`).
- Azure Pipelines: [templates/azure-pipelines-mutation-testing.yml](templates/azure-pipelines-mutation-testing.yml) (manual run; set the `base` parameter to the PR's target branch on every run; `fetchDepth: 0`).

Both templates call the helper, so the full-run fallback stop, the time budget, and runner detection also apply in CI. Copy [scripts/mutation-run.cs](scripts/mutation-run.cs) to `eng/mutation-run.cs` in the consumer repository; CI needs .NET SDK 10 or later. The base branch name is passed through an environment variable and validated with `git check-ref-format`, never interpolated into script text; give the bare branch name (`main`), not `origin/main`. A helper copied into the repository builds with that repository's `Directory.Build.props` and `global.json`; strict analyzer or `TreatWarningsAsErrors` settings there can break its build, so run it once locally from `eng/` before adding the workflow. Adding a workflow and the helper copy are repository changes; ask first.

## Gotchas

- **Diff mode falls back to a full run on non-C# changes.** Any non-C# file that differs from `origin/<base>` and that Stryker labels a "Changed test file" (it labels `global.json` and even `src/` files this way), such as `stryker-config.json`, `global.json`, or a `.csproj`, logs `will be tested because: Non-CSharp files in test project were changed` and tests every mutant. The helper stops there and lists the non-C# files as the likely trigger. Land infrastructure changes on the base branch first. `since.ignore-changes-in` excludes known-safe files such as `stryker-config.json`; do not add files that can change test behavior.
- **The fallback is detected late.** The trigger line appears only after the build, the initial test run, and coverage capture (about a minute in a small sample), so exit code 4 comes after that time, not at startup.
- **Uncommitted changes count.** `--since` compares the working tree with the target, so uncommitted edits are included in the diff.
- **Stryker defaults to the VSTest runner.** In MTP mode, pass `--test-runner mtp` (the helper does this). MSTest 4 projects keep working under the VSTest runner as well.
- **`dotnet test --solution` is MTP-only.** In VSTest mode, pass the solution path positionally: `dotnet test Sample.slnx`.
- **SDK 11 `dotnet new tool-manifest` writes `dotnet-tools.json` at the root**, not `.config/dotnet-tools.json`. Both locations are found by `dotnet tool run`.
- **Local tools resolve from the current directory.** Run `dotnet tool run dotnet-stryker` from the repository root.
- **The ClearText reporter truncates columns in narrow terminals.** Use the JSON report (the helper's summary) for file-level numbers.
