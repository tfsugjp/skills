---
name: dotnet-testing
description: 'Verification rules for .NET, Azure, and PowerShell, learned from changes reported as done that failed in real use. Use while writing MSTest, xUnit, or NUnit tests, migrating between test frameworks, adding OS-specific tests, validating samples, packages, or release artifacts such as VSIX and NuGet, checking concurrency and serialization, judging a UI change, or deciding and reporting whether a change passed its acceptance gates.'
---

# .NET Testing and Verification

"Built successfully" and "unit tests pass" were reported as done many times before the user found the feature broken. Decide what proves the change works, run that, and report what was not run.

## When not to use

- Finding the cause of a failure: `dotnet-debugging`.
- CI triggers, matrices, platforms, or secrets: `dotnet-ci-cd`.
- Integration tests against the Azure SQL Database container: `azuresql-db-testing`, when installed.

## Rules

### 1. Exercise the requested behavior where the user will use it

- **Rule:** For any user-visible change, run the application on the instance and build the user uses (the CLI they installed, the Visual Studio Experimental instance, the desktop app on their OS) and repeat the user's exact command or UI path. A build or registration check proves only that the code compiles.
- **Check:** The report names the instance, build, command or UI path, and observed result.
- **Why:** A localization fix passed tests but the Experimental instance still showed the old language, and a fix reported as done still threw on the original command.

### 2. Judge UI changes from screenshots

- **Rule:** Capture screenshots of the default, disabled, selected, and narrow-window states (plus theme or high contrast when colors changed), and state pass or fail per screenshot.
- **Check:** The report lists each screenshot with its verdict.
- **Why:** Truncated account details, a white selection, and a stop button that looked disabled were visible in screenshots and missed by tests.

### 3. Show the test fails without the fix, then re-check the neighbors

- **Rule:** For a bug fix or an accepted review finding, run the new test against the unfixed code and see it fail. After the fix, rerun the tests and manual checks for existing paths the change touched (popups, choice prompts, selection, focus, sign-in, cancellation), not only the new test.
- **Check:** The report states the failing-then-passing result and lists the regression paths checked.
- **Why:** One fix stopped answer popups from appearing, another broke sign-in while fixing its message, and a focus fix was pushed before its test had been seen to fail.

### 4. Mark OS-specific tests

- **Rule:** Tests that need Windows (Win32 packaging, registry, COM) or another OS carry an OS condition, for example `[OSCondition(OperatingSystems.Windows)]` in MSTest, and run in a CI job for that OS (`dotnet-ci-cd`, "Carry every platform through build, test, and artifacts").
- **Check:** The suite passes on each OS the workflow uses, and skipped tests name their condition.
- **Why:** Windows-only packaging tests failed on macOS and Linux runners.

### 5. Re-check semantics when migrating test frameworks

- **Rule:** A framework migration is not a rename. Compare assertion semantics (an equality assertion on collections may compare references; use the framework's collection or sequence assertion), async and fixture lifetimes, UI-thread or headless test attributes supplied by an adapter package, and analyzer suppressions the old framework's package provided (for example `CA2007` in test methods). Keep the test count and skip count equal before and after, or explain each difference.
- **Check:** Before and after counts match; no assertion was weakened; new warnings are fixed or suppressed in the test project with a reason.
- **Why:** A migration replaced a collection equality assertion with one that compares references, and new analyzer warnings appeared that the previous framework had suppressed.

### 6. Validate samples and inspect artifacts

- **Rule:** Validate each shipped sample with the product's own validator, keeping intentionally invalid samples in a clearly named folder. For release manifests, verify the digest of the actual asset for the version, OS, and architecture. For installable packages (VSIX, NuGet, MSIX, PKG), open the built file, confirm its type and manifest, and install it once before publishing.
- **Check:** The report gives manifest validity, digest, package contents, and install result separately.
- **Why:** A sample lacked a required field, a manifest listed the wrong digest, and a release uploaded an artifact that was not a VSIX and failed to install.

### 7. Pin serialization of external payloads

- **Rule:** For external API requests, test the serialized payload per resource type and per create, update, and delete operation: every required field is present, and `null` and omitted values are emitted as the receiver expects.
- **Check:** A payload test exists for each resource type and operation the change touches.
- **Why:** A production request lacked required properties, and a delete failed on a `null` field the receiver required.

### 8. Test ordering and concurrency explicitly

- **Rule:** When code depends on order or concurrency, test the relevant race: ordering (A, B, C), concurrent operations, re-initialization, an item added while an operation is pending, a selection switched before a result arrives, a retry started before the previous attempt's timer fires, and both response and notification orders when they can race.
- **Check:** Each race the change can hit has a test that fails when the guard is removed.
- **Why:** Reordered notifications, a single pending-operation slot, and cleared in-flight attachments reached review.

### 9. Record test execution and acceptance gates separately

- **Rule:** After the last code change, rerun the integrated gate on that commit. Record the commit or artifact, configuration, exact commands and environment variables, counts, and skip reasons, and compare them with the required gate even when the process exits successfully. Judge an acceptance criterion by the user's wording; do not add a stricter condition of your own. Attribute user acceptance to the person, target, and conditions verified, appended to the condition it satisfies without rewriting earlier skips or blocked gates. Name any required check that did not run (no local service, hosted CI unavailable) and where or by whom it can run.
- **Check:** The report separates test results, gate status, acceptance evidence, and checks not run.
- **Why:** A run passed with privilege-related skips while an evidence gate stayed blocked, "nothing left open" was reported before the final commit was tested, and the commands to rebuild a test container could not be recovered.

### 10. Clean up what testing created

- **Rule:** Delete work items, issues, cloud resources, containers, worktrees, and scratch folders created for testing, using only targets the user approved, and report what was deleted or left.
- **Check:** The report lists each created item and its final state.
- **Why:** Test work items were left in a live project, and the user had to ask for unused worktrees and scratch folders to be removed.

## Before reporting done

Confirm each applicable Check above, and list what was not run.
