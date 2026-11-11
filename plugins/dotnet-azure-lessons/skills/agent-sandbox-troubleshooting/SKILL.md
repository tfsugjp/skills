---
name: agent-sandbox-troubleshooting
description: 'Diagnose commands that fail because of the agent session itself, not the code. Use when a command in an agent session fails with "Operation not permitted", "operation not permitted: gh", a permission prompt or denial, a credential-helper or Keychain error, a `dotnet restore` or test run that hangs, or a write that is refused; when `gh`, `git push`, `az`, `dotnet`, or a container CLI works in the user''s terminal but not for the agent; before retrying a denied command, proposing a sandbox or allow-list change, or recording a workaround in memory.'
---

# Agent Sandbox Troubleshooting

In a sandboxed agent session (macOS Seatbelt, Linux bubblewrap, or a permission allow-list), most "broken tool" reports were the agent's own command shape or a boundary the user set on purpose. Classify the failure before touching code, settings, or credentials.

## When not to use

- A failure that also happens in the user's terminal: `dotnet-debugging`.
- Windows argument quoting for `az`, `gh`, or `.cmd` shims: `windows-shell-safety`.
- macOS toolchain differences that are not permission problems: `dotnet-macos-development`.

## Rules

### 1. Check the command shape before blaming the configuration

- **Rule:** Allow rules and sandbox exclusions match the start of the command line. Run each authenticated or excluded program (`gh`, `git push`, `git fetch`, `git pull`, `git clone`, `az`, a container CLI) as one command that starts with the bare program name. Anything in front or around it changes the match: `cd … &&`, `export …;`, `VAR=… cmd`, `echo …; cmd`, a pipe into `head` or `grep`, `git -C <dir> push`, or an absolute path to the binary. Pass absolute paths as arguments, write output to a file under the session's temporary directory when it must be filtered, and move multi-step logic into a script file.
- **Check:** The failing command is rerun alone, starting with the program name, before any other diagnosis is reported.
- **Why:** The user had to point out more than once that "the setting is there" and "it is failing again because the command is not standalone"; the agent had blamed the configuration, the Keychain, and TLS for what a prefix caused.

### 2. Classify the failure: boundary, credentials, or tool

- **Rule:** Decide which of these applies and say so in the report.
  - *Boundary:* `Operation not permitted` on a path or executable, a refused write, a blocked local port (a test host that never starts), or a network host that is not allowed (a restore that hangs on a download). The same command succeeds outside the session.
  - *Credentials:* the program starts but cannot read its token, session file, or Keychain item, or the token expired.
  - *Tool:* the failure reproduces in the user's terminal with the same command.
- **Check:** The report names the class, the exact path, host, or port that was refused, and the evidence (the error line, or a rerun outside the session by the user).
- **Why:** Sandbox denials were debugged as product failures in more than a dozen sessions, and a restore that "hung" passed in seconds once its download host was allowed.

### 3. Stop at a denial; do not change the outcome to get around it

- **Rule:** After a denial, do not repeat the same operation and do not substitute a different one that changes the result or the security posture: a merge because a rebase was denied, a token placed in a `curl` command or clone URL because `gh` was denied, a credential path read another way. Give the user the exact command to run in their terminal, wait, then verify the result yourself (`git status`, `git log`, `gh pr view`). Before a multi-step operation that includes a step you expect to be denied (history rewrite, branch deletion, writes to workflow files), ask first so the working tree is not left half-changed.
- **Check:** Each denied operation appears once in the transcript, followed by a hand-off command and a read-back of the result.
- **Why:** A denied rebase was replaced with a merge without asking, a `git reset --hard` was retried three times and left the tree in an intermediate state, and a token-in-URL workaround was written into notes.

### 4. Treat settings as the user's decision

- **Rule:** Propose a settings change with the exact entry and the layer it belongs in (a deny in the user layer is not undone by an allow in the repository layer), and let the user make it. Assume the change applies to new sessions, not the running one. Do not describe menus, tabs, or commands you have not verified exist.
- **Check:** The proposal quotes the entry and the file, and says the session must be restarted.
- **Why:** An added allow entry was reported as "ignored" when it only needed a new session, and the agent directed the user to a settings tab that does not exist.

### 5. Re-verify remembered workarounds

- **Rule:** Before reusing a workaround from memory or notes ("run restore in the background", "do not run `dotnet clean`", "use `curl` instead of `gh`"), test whether the plain standalone command now works. Replace the note when it does. Record the cause, not only the workaround, and never record a workaround that carries a secret.
- **Check:** A reused note has a date and was confirmed in this session.
- **Why:** Several stored workarounds were by-products of the command-shape misdiagnosis above and kept being applied after the cause was fixed.

### 6. Attribute the failure to the right session and directory

- **Rule:** Before saying "it worked earlier", confirm the earlier run was in the same session, working directory, and repository. Report the working directory and remote with the failure.
- **Check:** The failure report states the working directory, the repository remote, and whether the earlier success was in this session.
- **Why:** A failure was attributed to "this session" when the successful run belonged to another project's session.
