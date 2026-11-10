---
name: dotnet-testing
description: 'Verification rules for .NET, Azure, and PowerShell, learned from changes reported as done that failed in real use. Use while writing MSTest, xUnit, or NUnit tests, adding OS-specific or ARM64 tests, validating samples, packages, or release artifacts such as VSIX and NuGet, checking concurrency and serialization, or deciding whether a change passed its acceptance gates. Not for investigating an existing failure (dotnet-debugging) or CI YAML changes (dotnet-ci-cd).'
---

# .NET Testing and Verification

"Built successfully" and "unit tests pass" were reported as done many times before the user found the feature broken. Decide what proves the change works, run that, and report what was not run.

## When not to use

- Finding the cause of a failure: `dotnet-debugging`.
- CI triggers, matrices, or secrets: `dotnet-ci-cd`.
- Integration tests against the Azure SQL Database container: `azuresql-db-testing`, when installed.

## Rules

### 1. Exercise the requested behavior where the user will use it

- **Rule:** For any user-visible change, run the application on the instance and build the user uses (the CLI they installed, the Visual Studio Experimental instance) and repeat the user's exact command or UI path. A build or registration check proves only that the code compiles. Implement the behavior as requested; do not mark part of it out of scope, or add verification for areas the user excluded, without asking.
- **Check:** The report names the instance, build, command or UI path, and observed result. Do not call a fix done until it was observed there.
- **Why:** A localization fix passed tests but the Experimental instance still showed the old language; a requested fallback was left "out of scope" and the original command still threw.

### 2. Judge UI changes from screenshots

- **Rule:** Capture screenshots of the default, disabled, selected, and narrow-window states (plus theme or high contrast when colors changed), and state pass or fail per screenshot.
- **Why:** Truncated account details, a white selection, and a stop button that looked disabled were visible in screenshots and missed by tests.

### 3. Re-check neighbors of every fix

- **Rule:** After a fix, rerun the tests and manual checks for existing paths the change touched (popups, choice prompts, selection, sign-in, cancellation), not only the new test.
- **Check:** The report lists the regression paths checked.
- **Why:** One fix stopped answer popups from appearing; another broke sign-in while fixing its message.

### 4. Mark OS-specific tests

- **Rule:** Tests that need Windows (Win32 packaging, registry, COM) or another OS carry an OS condition, for example `[OSCondition(OperatingSystems.Windows)]` in MSTest, and run in a CI job for that OS.
- **Why:** Windows-only packaging tests failed on macOS and Linux runners.

### 5. Run ARM64 natively when a runner exists

- **Rule:** When a native ARM64 runner or agent is available, run the full test suite on it, not only an x64 cross-compile.
- **Why:** The user had to ask for native ARM64 testing.

### 6. Validate samples and inspect artifacts

- **Rule:** Validate each shipped sample with the product's own validator, keeping intentionally invalid samples in a clearly named folder. For release manifests, verify the digest of the actual asset for the version, OS, and architecture. For installable packages (VSIX, NuGet, MSIX), open the built file, confirm its type and manifest or nuspec, and install it once before publishing.
- **Check:** Report manifest validity, digest, package contents, and install result separately.
- **Why:** A sample lacked a required field, a manifest listed the wrong digest, and a release uploaded an artifact that was not a VSIX and failed to install with a missing-manifest error.

### 7. Pin serialization of external payloads

- **Rule:** For external API requests, test the serialized payload per resource type and per create, update, and delete operation: every required field is present, and `null` and omitted values are emitted as the receiver expects.
- **Why:** A production request lacked required properties, and a delete failed on a `null` field the receiver required.

### 8. Test ordering and concurrency explicitly

- **Rule:** When code depends on order or concurrency, test the relevant race: ordering (A, B, C), concurrent operations, re-initialization, an item added while an operation is pending, a selection switched before a result arrives, and both response and notification orders when they can race.
- **Why:** Reordered notifications, a single pending-operation slot, and cleared in-flight attachments reached review.

### 9. Record test execution and acceptance gates separately

- **Rule:** After the last code change, rerun the integrated gate on that commit. Record the commit or artifact, configuration, exact commands and environment variables, counts, and skip reasons, and compare them with the required gate even when the process exits successfully. Judge an acceptance criterion by the user's wording; do not add a stricter condition (such as "root cause identified") of your own. Attribute user acceptance to the person, target, and conditions verified, separate from harness results. Name any required check that did not start and who can run it.
- **Check:** The report separates test results, gate status, acceptance evidence, and checks not run; later acceptance keeps the original results.
- **Why:** A run passed with privilege-related skips while an evidence gate stayed blocked; "nothing left open" was reported before the final commit was tested and its release check failed; the commands to rebuild a test container could not be recovered; and an item the user accepted stayed unmarked.

### 10. Clean up what testing created

- **Rule:** Delete work items, issues, cloud resources, containers, worktrees, and scratch folders created for testing, using only targets the user approved, and report what was deleted or left.
- **Why:** Test work items were left in a live project, and the user had to ask for unused worktrees and scratch folders to be removed.

## Done checklist

- [ ] The requested behavior was exercised on the user's instance and build with the user's command.
- [ ] UI states were judged from screenshots; neighboring paths were re-checked.
- [ ] OS-specific tests are conditioned; ARM64 runs natively when possible.
- [ ] Samples validate; artifacts were opened, digest-checked, and installed.
- [ ] External payloads, ordering, and concurrency have tests.
- [ ] The report separates execution, skips, gates, and acceptance, with reproducible commands.
- [ ] Test data and local resources created for testing are deleted.
