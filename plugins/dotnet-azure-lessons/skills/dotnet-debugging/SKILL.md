---
name: dotnet-debugging
description: 'Investigation rules for .NET, Azure, and CLI-integration failures, learned from fixes aimed at the wrong cause. Use when a bug report, failed CI job, timeout, HTTP 4xx/5xx from Azure or Graph, or behavior that differs between tests and the real application needs a root cause; when a fix did not work; when the same error appears twice; or before reporting that some work is missing, merged, or deployed. Not for writing new tests (dotnet-testing) or CI definition changes (dotnet-ci-cd).'
---

# .NET Debugging

Most wasted debugging time came from testing a different binary than the user ran, trusting a fake instead of the real peer, or changing code before reading the actual failure.

## When not to use

- Designing tests, regression scope, or deciding a change is verified: `dotnet-testing`.
- Editing pipeline YAML: `dotnet-ci-cd`.
- Windows argument-quoting failures from `az` or `gh`: `windows-shell-safety`.

## Rules

### 1. Identify the exact binary, instance, and checkout first

- **Rule:** Before reproducing, record the path and version of every executable involved (`Get-Command <tool>`, `<tool> --version`, any `*_PATH` override), the version the peer reports at connection time, and the instance the user runs (for example the Visual Studio Experimental instance, not Stable). When working in a git worktree, give the user its absolute path and the solution file to open there.
- **Check:** The notes and report state the tested path, version, instance, and checkout.
- **Why:** A verification ran against an old CLI because an override variable pointed at the previous binary; the agent proposed testing Stable while the user ran Experimental; and the user had to ask which worktree solution to open.

### 2. Reproduce with the real peer, not only with a fake

- **Rule:** Use fakes for unit tests, but reproduce reported bugs against the real CLI, server, service, or IDE, using the user's exact command, options, and data. When the user reports that the same data reproduced the symptom, rerun or compare that data before calling it expected behavior. When the real peer cannot run locally, say so and name where it will be verified.
- **Check:** The report names the real component that reproduced the failure and confirmed the fix.
- **Why:** A delete passed against the fake server and failed against the real CLI with a missing-field error, and a fix reported as done still threw when the user ran the original command.

### 3. Read the failure before changing code

- **Rule:** For CI failures, identify the run, commit, failed job, and step, and quote the first error that explains the failure from its log. If log retrieval is blocked, try an already authorized path to the same run, then report the retrieval error with the cause undetermined. For HTTP failures, capture the status. Redact tokens, device codes, and personal data before recording or asking the user to paste logs.
- **Check:** The report cites the supporting log, or names the run and the missing log.
- **Why:** A Linux build failure and a Graph 400 were explained by their logs; a pasted daemon log exposed a device code.

### 4. Change approach after the same failure twice

- **Rule:** After the same error twice, including two failed reproductions the user ran for you, stop retrying variations. Summarize what was tried, the evidence, and the next hypothesis, and ask the user (or a design-review agent) before a third attempt.
- **Why:** Repeated small variations consumed time without new information.

### 5. Look for hangs on a shared loop

- **Rule:** For RPC or UI timeouts, check whether a handler awaits work that needs the loop or thread it is blocking (see `dotnet-coding` rule 1).
- **Check:** A task dump or timestamped log shows the waiting chain.

### 6. Read back state before calling something missing, merged, or deployed

- **Rule:** Before saying work is missing, not committed, merged, or deployed, check the branch, commits, PRs, and the deployed resource (`git log`, `git status`, `gh pr list --state all`, `az resource show`, a code search).
- **Check:** The report cites the output that shows the state.
- **Why:** Done work was reported missing, an unmerged draft PR was treated as merged, a resource assumed deployed did not exist, and a closed PR's issue was assumed implemented.

### 7. Confirm cancellation actually stops work

- **Rule:** For stop, cancel, or interrupt fixes, confirm from logs or the peer's events that the operation ended, not only that the button changed.
- **Why:** A stop button changed state while the turn kept running.

### 8. Preserve evidence from intermittent failures

- **Rule:** Save the initial error, rerun only the affected job or test on the same commit when authorized, and distinguish a download failure, a timeout, and an assertion failure before changing code.
- **Check:** The initial outcome, rerun scope, and result are recorded; a cause not identified by a passing rerun is reported as undetermined.
- **Why:** A transient download error and an intermittent test timeout both passed on retry, with different failure points.

## Done checklist

- [ ] Binary paths, versions, instance, and worktree are recorded.
- [ ] The failure and fix were confirmed with the real peer and the user's command, or the gap is stated.
- [ ] The first job error is quoted or the blocked retrieval is stated; logs are redacted.
- [ ] No third retry of the same shape.
- [ ] Missing, merged, or deployed claims cite command output.
- [ ] Cancellation was confirmed from events; intermittent failures record both runs.
