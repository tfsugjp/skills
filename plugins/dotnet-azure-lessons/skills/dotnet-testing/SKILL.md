---
name: dotnet-testing
description: 'Choose and report verification for .NET, Azure, and PowerShell changes, including tests, platform coverage, packages, concurrency, serialization, and UI.'
---

# .NET Testing and Verification

Choose evidence that matches the changed behavior and the user's acceptance criteria. A build or unit test proves only what it exercises. Report required checks that could not run, separately from failures.

## When not to use

- Finding the cause of a failure: `dotnet-debugging`.
- CI triggers, matrices, platforms, and secrets: `dotnet-ci-cd`.
- Azure SQL container integration testing: `azuresql-db-testing`, when installed.

## Rules

### 1. Exercise the requested behavior where the user will use it

- **Rule:** For a user-visible change, use the user's application instance, installed CLI, or IDE when available and appropriate. Repeat the reported command or UI path when it is part of acceptance. If that environment is unavailable, state the limitation and the best evidence collected.
- **Check:** Report the instance or boundary tested, action performed, observed result, and material checks not run.
- **Why:** Tests passed while an installed CLI still failed on the user's original command.

### 2. Judge UI changes from screenshots

- **Rule:** Use screenshots to assess layout and visual states affected by a UI change. Check narrow layouts, themes, selection, or disabled states when relevant; do not require unrelated states.
- **Check:** Report the applicable states inspected and what could not be observed.
- **Why:** Truncation and weak selection contrast were visible in the UI but missed by logic tests.

### 3. Show the test fails without the fix, then re-check the neighbors

- **Rule:** For a regression test, show it fails on the unfixed behavior when practical, then passes after the fix. Recheck nearby paths that share the changed logic. If the original version or environment cannot be run, say so and use other evidence.
- **Check:** Report the regression result and the affected neighboring paths checked; distinguish unavailable evidence from a failed check.
- **Why:** Fixes to popups, sign-in, and focus caused regressions in adjacent paths.

### 4. Mark OS-specific tests

- **Rule:** Mark tests that require OS facilities and run them in an available job for that OS. Do not report an unrun platform check as passed.
- **Check:** Identify platform-specific tests, condition or job, and outcome; report skipped or unavailable checks.
- **Why:** Win32 packaging tests failed on non-Windows runners.

### 5. Re-check semantics when migrating test frameworks

- **Rule:** Check assertion semantics, async/fixture lifetimes, adapters, and analyzer changes when migrating frameworks. Do not weaken assertions to make the new framework pass.
- **Check:** Compare relevant tests and warnings; explain changes in test or skip coverage.
- **Why:** A collection equality assertion changed from sequence comparison to reference comparison.

### 6. Validate samples and inspect artifacts

- **Rule:** Validate samples with the product's validator. Check release manifest digests against the actual asset. Inspect installable package type and manifest; install only when needed to prove the requested behavior and in an authorized, suitable environment (prefer an isolated test environment). A package inspection or installation must not publish or change a user's environment without authorization.
- **Check:** Report sample validity, digest, package contents, and installation outcome as separate observations; mark an unperformed install clearly.
- **Why:** A release manifest used the wrong digest and an uploaded artifact was not a valid VSIX.

### 7. Pin serialization of external payloads

- **Rule:** For resource types and operations changed, test the serialized request fields, including how omitted and `null` values are represented.
- **Check:** Relevant payload tests cover the changed operation and API contract.
- **Why:** A production request omitted required properties.

### 8. Test ordering and concurrency explicitly

- **Rule:** Where behavior depends on order or overlapping operations, test the races the change can reach: response/notification order, retry, reinitialization, target changes, and mutations during a pending send as applicable.
- **Check:** Each material race has a test or an explicit reason it cannot be exercised; test evidence shows the guard matters where practical.
- **Why:** Reordered notifications and a single pending-operation slot caused regressions.

### 9. Record test execution and acceptance gates separately

- **Rule:** Run the relevant integrated gate on the final change when available. Record the revision, commands, configuration, outcome, skips, and acceptance evidence. Do not impose conditions beyond the user's criteria, and do not infer a pass from process exit alone when required jobs were skipped.
- **Check:** State separately what passed, what met acceptance, and what required check did not run or remains open.
- **Why:** A passing command hid skipped checks, and completion was reported before the final revision had run.

### 10. Clean up what testing created

- **Rule:** Remove temporary resources created for testing when cleanup is safe and authorized. Preserve live or user-owned resources; report anything left behind.
- **Check:** Report resources created for testing and their final state when applicable.
- **Why:** Test work items and cloud resources were left behind.
