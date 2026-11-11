---
name: dotnet-debugging
description: 'Investigation rules for .NET, Azure, and CLI-integration failures, learned from fixes aimed at the wrong cause. Use when a bug report, failed CI job, crash, timeout, HTTP 4xx/5xx from Azure or Graph, or behavior that differs between tests and the real application needs a root cause; when a fix did not work; when the same error appears twice; when the user offers their own diagnosis; or before reporting that some work or file is missing, present, merged, finished, or deployed.'
---

# .NET Debugging

Most wasted debugging time came from testing a different binary than the user ran, trusting a fake instead of the real peer, changing code before reading the failure, or stating a guess as the cause.

## When not to use

- Designing tests, regression scope, or deciding a change is verified: `dotnet-testing`.
- Editing pipeline YAML: `dotnet-ci-cd`.
- A command that fails only inside the agent session (permission or sandbox errors): `agent-sandbox-troubleshooting`.
- Windows argument-quoting failures from `az` or `gh`: `windows-shell-safety`.

## Rules

### 1. Identify the exact binary, instance, and checkout first

- **Rule:** Before reproducing, record the path and version of every executable involved (`Get-Command <tool>` or `command -v <tool>`, `<tool> --version`, any `*_PATH` override), the version the peer reports at connection time, and the instance the user runs (for example the Visual Studio Experimental instance, not Stable). In a git worktree, give the user its absolute path and the solution file to open there.
- **Check:** The report states the tested path, version, instance, and checkout.
- **Why:** A verification ran against an old CLI because an override variable pointed at the previous binary, and the agent proposed testing Stable while the user ran Experimental.

### 2. Reproduce with the real peer, not only with a fake

- **Rule:** Use fakes for unit tests, but reproduce reported bugs against the real CLI, server, service, or IDE, using the user's exact command, options, and data. When the real peer cannot run locally, say so and name the CI job or environment where it will be verified.
- **Check:** The report names the real component that reproduced the failure and confirmed the fix.
- **Why:** A delete passed against the fake server and failed against the real CLI with a missing-field error, and a fix reported as done still threw when the user ran the original command.

### 3. Read the failure before changing code

- **Rule:** For CI failures, identify the run, commit, failed job, and step, and quote the first error that explains the failure from its log. For crashes, read the stack to find the layer (application, framework, native dependency) before editing application code. For HTTP failures, capture the status and response body. For a timeout on an RPC or UI loop, check whether a handler awaits work that needs the loop it is blocking. Redact tokens, device codes, and personal data before recording logs or asking the user to paste them.
- **Check:** The report cites the supporting log line or stack frame, or names the run and the log that could not be retrieved.
- **Why:** A Linux build failure and a Graph 400 were explained by their logs, a crash turned out to be in a dependency's native layer, and a pasted daemon log exposed a device code.

### 4. Separate what is established from what is a hypothesis

- **Rule:** State the cause as established only when evidence excludes the alternatives. Otherwise report the leading hypothesis, its evidence, and what would confirm it, and label the fix as addressing a hypothesis. When the user offers a diagnosis, test it; do not dismiss it with "the logs prove otherwise" unless the report quotes the log lines that do.
- **Check:** The report has separate statements for observed facts, the hypothesis, and what remains undetermined.
- **Why:** The agent declared from logs that an expiring credential was "definitely not" the cause the user described; a later review found the claim overstated and the cause still open.

### 5. Change approach after the same failure twice

- **Rule:** After the same error twice, including two failed reproductions the user ran for you, stop retrying variations. Summarize what was tried, the evidence, and the next hypothesis, and ask the user (or a design-review agent) before a third attempt.
- **Check:** No third attempt of the same shape appears before that summary.
- **Why:** Repeated small variations consumed time without new information.

### 6. Read back state before making a claim about it

- **Rule:** Before saying work is missing, present, committed, merged, finished, or deployed, read the state: `git log`, `git status`, `gh pr view --json state,mergedAt,statusCheckRollup`, `gh pr list --state all`, `az resource show`, `ls -l` for a file's existence and permissions, a code search for a symbol. "Finished" means its condition was observed (merged, checks completed), not that the command was issued.
- **Check:** The report cites the output that shows the state.
- **Why:** Done work was reported missing, an unmerged draft PR was treated as merged, a resource assumed deployed did not exist, a script was called executable without checking its mode, an installed dependency was reported absent, and a task was declared complete while its PR was unmerged and its checks were queued.

### 7. Confirm cancellation actually stops work

- **Rule:** For stop, cancel, or interrupt fixes, confirm from logs or the peer's events that the operation ended, not only that the button changed.
- **Check:** The report quotes the event or log line that shows the operation ended.
- **Why:** A stop button changed state while the turn kept running.

### 8. Preserve evidence from intermittent failures

- **Rule:** Save the initial error, rerun only the affected job or test on the same commit when authorized, and distinguish a download failure, a timeout, a container that exited at startup, and an assertion failure before changing code. A failure that recurs on rerun is not transient; report it as an open infrastructure or product problem.
- **Check:** The initial outcome, rerun scope, and result are recorded; a cause not identified by a passing rerun is reported as undetermined.
- **Why:** A transient download error passed on retry, while a database container that exited one second after start failed again on rerun and was not a one-off.

## Before reporting done

Confirm each applicable Check above, or state the gap.
