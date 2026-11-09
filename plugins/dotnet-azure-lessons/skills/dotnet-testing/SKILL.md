---
name: dotnet-testing
description: 'Verification rules for .NET, Azure, and PowerShell, learned from changes reported as done that failed in real use. Use while writing MSTest, xUnit, or NUnit tests, adding OS-specific or ARM64 tests, validating samples or artifacts, checking concurrency and serialization, or deciding whether a change passed its acceptance gates. Not for investigating an existing failure (dotnet-debugging) or CI YAML changes (dotnet-ci-cd).'
---

# .NET Testing and Verification

"Built successfully" and "unit tests pass" were reported as done many times before a user found the feature broken. Decide what proves the change works, run that, and report what was not run.

## When not to use

- Finding the cause of a failure: use `dotnet-debugging`.
- Changing CI triggers, matrices, or secrets: use `dotnet-ci-cd`.
- Integration tests against the Azure SQL Database container: use the `azuresql-db-testing` skill when it is installed.

## Rules

### 1. A build is not a behavior check

- **Rule:** For any user-visible change, run the application (CLI, service, or IDE Experimental instance) and exercise the changed behavior. A successful build or registration check proves only that the code compiles.
- **Check:** The report names the command or UI path executed and its observed result.
- **Why:** A localization fix built and passed tests, but the Experimental instance still showed the old language.

### 2. Judge UI changes from screenshots

- **Rule:** For UI changes, capture screenshots of the default, disabled, selected, and narrow-window states (and theme or high contrast when colors changed), and state pass or fail per screenshot.
- **Check:** Screenshots are attached or referenced in the report.
- **Why:** Truncated account details, a white selection, and a stop button that looked disabled were all visible in screenshots and missed by tests.

### 3. Re-check neighbors of every fix

- **Rule:** After a fix, run the tests and manual checks for the existing paths the change touched, not only the new test.
- **Check:** The report lists the regression paths checked.
- **Why:** A review fix silently disabled answer popups.

### 4. Mark OS-specific tests

- **Rule:** Tests that need Windows (Win32 packaging, registry, COM) or another OS carry an OS condition, for example `[OSCondition(OperatingSystems.Windows)]` in MSTest, and run in a CI job for that OS.
- **Check:** The test suite passes on every OS in the CI matrix.
- **Why:** Windows-only packaging tests failed on macOS and Linux runners.

### 5. Run ARM64 natively when a runner exists

- **Rule:** When a native ARM64 runner or agent is available, build and run the full test suite on it instead of only cross-compiling from x64.
- **Check:** The CI matrix has an ARM64 test job, not only an ARM64 build step.
- **Why:** The user had to ask for native ARM64 testing after ARM64 was only cross-compiled.

### 6. Validate samples and verify artifacts

- **Rule:** Validate each shipped sample manifest, configuration, or template with the product's own validator. Keep intentionally invalid samples in a separate, clearly named folder. For release manifests, verify the digest of the actual asset for the specified version, OS, and architecture. When package contents are an acceptance condition, inspect the built package for its required files and contract metadata.
- **Check:** A test enumerates and validates the sample files. Report manifest validity, digest verification, and package contents separately when applicable.
- **Why:** A sample failed validation for a missing required field. A different manifest was structurally valid but listed the wrong digest for its asset.

### 7. Pin serialization of external payloads

- **Rule:** For requests to external APIs, add a test that serializes the payload for each resource type and asserts every required field is present and that `null` and omitted values are emitted as the receiver expects.
- **Check:** One payload test per resource type and per create, update, and delete operation.
- **Why:** A production request failed for missing required properties, and a delete failed on a `null` field the receiver required.

### 8. Test ordering and concurrency explicitly

- **Rule:** When code depends on order or runs concurrently, choose cases that exercise the relevant race: ordering (A, B, C), concurrent operations, re-initialization, or an item added while an operation is pending. For an operation tied to a selection, cover switching the selection before a success, failure, or notification arrives and both response and notification orders when they can race.
- **Check:** Each affected queue, pending operation, or post-send cleanup has a test that exercises the relevant ordering or race.
- **Why:** Reordered notifications, a single pending-operation slot, and cleared in-flight attachments all reached review.

### 9. Record test execution and acceptance gates separately

- **Rule:** Record the commit or artifact, configuration, counts, and skip reasons. Compare these with the required gate even if the test process exits successfully. Attribute user acceptance to the person, target, and conditions verified. Record harness results and real-host acceptance separately. If a required check could not start, name the gap and the job or person that can run it.
- **Check:** The report separates test results, gate status, acceptance evidence, and checks that did not run. Later user acceptance retains the original test and gate results.
- **Why:** A test process succeeded with privilege-related skips while a mandatory evidence gate remained blocked. Later real-host acceptance covered a different verification condition.

### 10. Clean up test data in real services

- **Rule:** Delete work items, issues, resources, or files created while testing against a real service, and report what was deleted. Use only the test targets the user approved.
- **Check:** The report lists created and deleted test data.
- **Why:** Test work items were left behind in a live project.

## Done checklist

- [ ] The changed behavior was exercised in the running application.
- [ ] UI states were checked from screenshots.
- [ ] Neighboring paths were re-checked.
- [ ] OS-specific tests are conditioned; ARM64 runs natively when possible.
- [ ] Samples pass the product validator, and required artifact contents and digests are checked separately.
- [ ] External payloads, ordering, and concurrency have tests.
- [ ] The report separates test execution, skips, gate status, and user or real-host acceptance.
- [ ] Test data in real services is deleted.
