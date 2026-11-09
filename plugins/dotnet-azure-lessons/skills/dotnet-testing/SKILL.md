---
name: dotnet-testing
description: 'Verification rules for .NET and Azure work, learned from changes reported as done that failed in real use. Use while writing MSTest, xUnit, or NUnit tests; adding OS-specific or ARM64 tests; adding sample files or manifests the product validates; testing concurrency, ordering, or serialization; and before reporting any change as verified or done. Not for investigating an existing failure (dotnet-debugging) or CI YAML changes (dotnet-ci-cd).'
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

### 6. Keep samples valid under the product's own validator

- **Rule:** Every sample manifest, configuration, or template shipped in the repository passes the product's `validate` command in a test or CI step. Intentionally invalid samples live in a separate, clearly named folder.
- **Check:** A test enumerates the sample folder and validates each file.
- **Why:** A macOS sample failed the product's own validation for a missing required field.

### 7. Pin serialization of external payloads

- **Rule:** For requests to external APIs, add a test that serializes the payload for each resource type and asserts every required field is present and that `null` and omitted values are emitted as the receiver expects.
- **Check:** One payload test per resource type and per create, update, and delete operation.
- **Why:** A production request failed for missing required properties, and a delete failed on a `null` field the receiver required.

### 8. Test ordering and concurrency explicitly

- **Rule:** When code depends on order or runs concurrently, test the order (A, B, C), concurrent operations (two requests in flight), re-initialization, and an item added while an async operation is pending.
- **Check:** Such tests exist for every queue, pending-operation field, and post-send cleanup.
- **Why:** Reordered notifications, a single pending-operation slot, and cleared in-flight attachments all reached review.

### 9. Report what was not run

- **Rule:** When a test cannot run locally (no Docker, no ARM64 machine, no signed-in account), state that it was not run and which CI job or person will run it. Never mark an item verified without evidence; record who verified it and how when the user did.
- **Check:** The report separates "verified", "verified by the user", and "not run".
- **Why:** Unverified items were nearly recorded as verified.

### 10. Clean up test data in real services

- **Rule:** Delete work items, issues, resources, or files created while testing against a real service, and report what was deleted. Use only the test targets the user approved.
- **Check:** The report lists created and deleted test data.
- **Why:** Test work items were left behind in a live project.

## Done checklist

- [ ] The changed behavior was exercised in the running application.
- [ ] UI states were checked from screenshots.
- [ ] Neighboring paths were re-checked.
- [ ] OS-specific tests are conditioned; ARM64 runs natively when possible.
- [ ] Samples pass the product validator.
- [ ] External payloads, ordering, and concurrency have tests.
- [ ] The report separates verified, user-verified, and not run.
- [ ] Test data in real services is deleted.
