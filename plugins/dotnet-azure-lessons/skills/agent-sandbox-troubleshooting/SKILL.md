---
name: agent-sandbox-troubleshooting
description: 'Diagnose command failures that may come from the agent session, its permissions, or credentials. Use after an operation is refused or behaves differently in the agent than in the user''s terminal.'
---

# Agent Sandbox Troubleshooting

Check the active session policy and evidence before changing code or blaming credentials. Permission systems differ; a prior workaround is not proof that the same boundary applies now.

## When not to use

- A failure also reproduced in the user's terminal: `dotnet-debugging`.
- Windows argument quoting for native tools: `windows-shell-safety`.
- macOS toolchain differences without a permission problem: `dotnet-macos-development`.

## Rules

### 1. Inspect the active command policy before changing command shape

- **Rule:** Read the current denial and applicable session instructions. If they show prefix-matching exclusions, run the affected program in the required standalone form; otherwise do not treat command shape as the cause without evidence. Separate shell construction errors from an explicit permission denial. Do not rerun a denied operation unless the session policy or a newly granted permission makes that attempt valid.
- **Check:** The diagnosis cites the specific error or active policy that supports the boundary or command-shape explanation.
- **Why:** A command prefix caused repeated permission mismatches in one environment, but prefix rules are session-specific and can change.

### 2. Separate boundary, credential, and application failures

- **Rule:** Classify the evidence: *boundary* (the session refuses a path, executable, network destination, or local port); *credential* (the program starts but cannot use or refresh authentication); or *tool/application* (the same operation fails outside the session). A hang alone does not establish which class applies. Record only the relevant path, host, port, error, and working directory; redact tokens and personal data.
- **Check:** The report distinguishes observed facts from inference and identifies evidence for the classification. If the user runs a comparison, ask them to use the same command and directory.
- **Why:** Sandbox denials were mistaken for product failures, while a restore stall was resolved only after its blocked download host was identified.

### 3. Diagnose GitHub CLI authentication separately from Git credentials

- **Rule:** If `gh` reports an authentication problem, run `gh auth status` and then `gh api user --jq .login` as separate, standalone commands. A successful `gh api rate_limit` does not prove the authenticated user. If status shows an account but the authenticated user call returns 401, check whether `GH_TOKEN` and `GITHUB_TOKEN` are set because environment tokens take precedence; report only whether they are set, never their values. Distinguish 401 authentication, 403 permission/rate-limit, 404 resource visibility, and network failures. A working Git credential helper does not establish that `gh` API authentication works. Do not change credentials unless the user asks.
- **Check:** The report names the status result, authenticated-user result, and token-variable presence without exposing secrets; it does not infer `gh` status from Git operations or anonymous endpoints.
- **Why:** Git transport credentials and `gh` API credentials can differ, and an environment token can override a stored `gh` login. GitHub documents 401 for invalid credentials and 403/404 for insufficient or hidden resources.

### 4. Respect explicit denials and use only supported recovery paths

- **Rule:** Do not substitute another command, credential route, or operation that bypasses a denial or changes the security posture. If the action remains in scope, report the refusal and use the environment's supported permission or escalation mechanism; if permission is unavailable or the user must act locally, provide the exact command and verify the result after they run it. Do not retry a destructive or history-rewriting operation in a different form. An approval request is not a denial.
- **Check:** There is no bypass attempt after an explicit denial; any permitted retry has new authorization or evidence that it is now allowed, and its result is read back.
- **Why:** Replacing a denied rebase with a merge changed the result, and repeating a denied reset left the tree in an intermediate state.

### 5. Treat permission settings and remembered workarounds as changeable

- **Rule:** Describe a settings change only with the exact verified setting and the layer where it applies; leave the change to the user unless they request it. State when it requires a new session only if the active product documents that behavior. Before using a remembered workaround, test the ordinary permitted command and verify the workaround still applies. Do not write secrets or unverified workarounds into memory. Update memory only when the user explicitly asks.
- **Check:** A proposed setting cites the active policy source; a reused workaround is confirmed in the current session.
- **Why:** A permission change appeared ineffective because it applied to a later session, and stale workarounds persisted after the original cause disappeared.

### 6. Attribute the failure to the correct session and checkout

- **Rule:** Before comparing with an earlier success, confirm session, working directory, repository, and relevant remote. Do not state that a command works "outside the session" unless there is evidence from the user's comparison.
- **Check:** The report names the current directory and repository and labels any external comparison as user-reported until verified.
- **Why:** A successful run from a different project session was attributed to the current one.
