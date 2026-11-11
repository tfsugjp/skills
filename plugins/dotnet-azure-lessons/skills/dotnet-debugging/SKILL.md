---
name: dotnet-debugging
description: 'Find and verify root causes for .NET, Azure, and CLI integration failures, crashes, timeouts, or behavior that differs between tests and production.'
---

# .NET Debugging

Use evidence from the binary, peer, and environment involved in the report. Keep observed facts, hypotheses, reproduction, and post-fix acceptance distinct.

## When not to use

- Designing regression coverage or deciding whether a change meets acceptance: `dotnet-testing`.
- Editing pipeline definitions: `dotnet-ci-cd`.
- A failure caused by the agent session's permissions or sandbox: `agent-sandbox-troubleshooting`.
- Windows command quoting: `windows-shell-safety`.

## Rules

### 1. Identify the exact binary, instance, and checkout first

- **Rule:** Confirm the executable path and version, relevant overrides, peer version, and user instance or checkout when they affect reproduction.
- **Check:** The report identifies which binary, peer, instance, and checkout were actually used.
- **Why:** A previous CLI was tested because an override pointed away from the newly built binary.

### 2. Reproduce with the real peer, not only with a fake

- **Rule:** Use fakes for unit coverage; reproduce a peer-dependent failure against the real CLI, service, server, or IDE using the reported command and data when available. If unavailable, state what other evidence exists and what remains unconfirmed. Post-fix acceptance evidence follows `dotnet-testing`.
- **Check:** The report distinguishes reproduction of the cause from verification that the user's acceptance criteria are met.
- **Why:** A fake accepted a delete request that the real server rejected for a missing field.

### 3. Read the failure before changing code

- **Rule:** Identify the failing run, commit, job, and first relevant log error; read crash stacks to locate the failing layer; and capture HTTP status plus useful response detail. Remove tokens, device codes, personal data, and sensitive query values from logs before sharing or recording them.
- **Check:** Cite the sanitized evidence or state which log could not be retrieved.
- **Why:** Logs located a Graph request failure and a crash in a native dependency; a daemon log also exposed a device code.

### 4. Separate what is established from what is a hypothesis

- **Rule:** Call a cause established only when evidence supports it over plausible alternatives. Otherwise state the leading hypothesis, its supporting evidence, and what would confirm or refute it. Test the user's diagnosis before rejecting it.
- **Check:** The report separates facts, hypothesis, and open questions.
- **Why:** An expiring credential was dismissed without evidence and remained a viable cause.

### 5. Change approach after the same failure twice

- **Rule:** After the same failure repeats without new information, stop trying cosmetic variations. Summarize attempts and evidence, then choose a materially different diagnostic step. Ask for user input when the next step requires their environment, authorization, or a choice only they can make.
- **Check:** The next attempt tests a new hypothesis or uses new evidence; it does not repeat the same unsuccessful command shape.
- **Why:** Similar retries consumed time without narrowing the cause.

### 6. Read back state before making a claim about it

- **Rule:** Check repository, PR, resource, or file state before saying it is present, committed, merged, finished, or deployed. A command being issued does not prove its intended result.
- **Check:** The report identifies the observed state and evidence source.
- **Why:** A resource was reported deployed when it did not exist, and a PR with queued checks was called finished.

### 7. Confirm cancellation actually stops work

- **Rule:** For a stop or cancellation fix, verify from the peer or operation log that work ended, not only that the UI changed.
- **Check:** Report the event or state that shows the operation stopped.
- **Why:** A button changed while its operation continued.

### 8. Preserve evidence from intermittent failures

- **Rule:** Keep the initial failure and rerun only an affected job or test when useful and authorized. Distinguish transient download problems, timeouts, startup failures, and assertion failures. A successful rerun alone does not establish a cause.
- **Check:** Report initial and rerun outcomes and leave unidentified causes open.
- **Why:** A failed container restarted and failed again, so the failure was not transient.
