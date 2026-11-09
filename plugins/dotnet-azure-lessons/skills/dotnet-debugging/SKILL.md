---
name: dotnet-debugging
description: 'Investigation rules for .NET, Azure, and CLI-integration failures, learned from fixes aimed at the wrong cause. Use when a bug report, failed CI job, timeout, HTTP 4xx/5xx from Azure or Graph, or behavior that differs between tests and the real application needs a root cause; when a fix did not work; when the same error appears twice; or before reporting that some work is missing or not implemented. Not for writing new tests (dotnet-testing) or CI definition changes (dotnet-ci-cd).'
---

# .NET Debugging

Most wasted debugging time in past sessions came from testing a different binary than the user ran, trusting a fake instead of the real peer, or changing code before reading the actual failure.

## When not to use

- Designing new tests or deciding coverage: use `dotnet-testing`.
- Editing pipeline YAML: use `dotnet-ci-cd`.
- Windows argument-quoting failures from `az` or `gh`: use `windows-shell-safety`.

## Rules

### 1. Identify the exact binary and version first

- **Rule:** Before reproducing, record the path and version of every executable involved (`Get-Command <tool>`, `<tool> --version`, and any override variable such as a `*_PATH` setting), and the version the peer reports at connection time.
- **Check:** The investigation notes and the final report state the path and version that were tested.
- **Why:** A verification ran against an old CLI because an override variable still pointed at the previous binary, and the design had to be rebased on the version actually installed.

### 2. Reproduce with the real peer, not only with a fake

- **Rule:** Use fakes for unit tests, but reproduce reported bugs against the real CLI, server, service, or IDE instance. When the real peer cannot run locally, say so and name where it will be verified.
- **Check:** The report says which real component reproduced the failure and confirmed the fix.
- **Why:** A delete operation passed against the fake server and failed against the real CLI with a missing-field error; the user had to ask for real-CLI verification.

### 3. Read the failure before changing code

- **Rule:** For CI failures, identify the run, commit, failed job, and step. Read the failed job's log and quote the first error that explains the failure. If credentials or the CLI prevent log retrieval, try an already authorized path to the same run. If access remains blocked, report the retrieval error and the evidence needed to resume, with the job's cause undetermined. For HTTP failures, capture the status and redact sensitive fields before recording the response or request.
- **Check:** The report cites the log that supports the diagnosis or names the run and missing log explicitly.
- **Why:** A Linux build failure and a Graph 400 were explained by their logs. A credential-store failure occurred before an Azure Pipelines job log could be read.

### 4. Change approach after the same failure twice

- **Rule:** If the same error appears after two attempts, stop retrying variations. Summarize what was tried, the evidence, and the next hypothesis, and ask the user (or a design-review agent, when the environment provides one) before the third attempt.
- **Check:** No third attempt with the same shape.
- **Why:** Repeated retries with small variations consumed time without new information.

### 5. Look for hangs on a shared loop

- **Rule:** For timeouts in RPC or UI code, check whether a handler awaits work that needs the same loop or thread it is blocking (a response read by the same parse loop, a UI-thread call from a UI-thread wait).
- **Check:** A thread or task dump, or a log with timestamps, shows the waiting chain.
- **Why:** A 15-second timeout came from a notification handler that awaited a response stuck behind its own read loop.

### 6. Verify the current state before calling something missing

- **Rule:** Before reporting that work is missing, not implemented, or not committed, check the branch, recent commits, open and merged PRs, and the files (`git log`, `git status`, `gh pr list --state all`, a code search).
- **Check:** The report cites the command output that shows the state.
- **Why:** Work that had already been done was reported as missing, and a closed PR's linked issue was assumed implemented when it was not.

### 7. Confirm the fix did not break a neighbor

- **Rule:** After a fix, exercise the existing feature paths the change touched (popups, choice prompts, selection, cancellation) in the real application, not only the path that was broken.
- **Check:** The report lists the neighboring paths checked.
- **Why:** A fix for one issue stopped answer popups from appearing at all.

### 8. Confirm cancellation actually stops work

- **Rule:** For stop, cancel, or interrupt fixes, confirm from logs or the peer's events that the running operation ended, not only that the button changed state.
- **Check:** The log shows the interrupt request and the operation's completion event.
- **Why:** A stop button changed state while the turn kept running to the end.

### 9. Preserve evidence from intermittent failures

- **Rule:** Save the initial error and, when useful and authorized, rerun only the affected job or test on the same commit and configuration. Distinguish a dependency download failure, a timeout, and an assertion failure before deciding whether to change code.
- **Check:** Record the initial outcome, the rerun scope, and the result. Report an intermittent cause as undetermined when the rerun passes without identifying it.
- **Why:** A transient download error and an intermittent test timeout both passed on retry, but involved different failure points.

## Done checklist

- [ ] Binary paths and versions are recorded.
- [ ] The failure and the fix were confirmed with the real peer, or the gap is stated.
- [ ] The first job error is quoted, or the blocked log retrieval and missing evidence are stated.
- [ ] No third retry of the same shape.
- [ ] Missing-work claims cite `git` or `gh` output.
- [ ] Neighboring paths and cancellation were checked when relevant.
- [ ] Initial and rerun outcomes are both recorded for intermittent failures.
