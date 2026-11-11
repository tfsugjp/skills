---
name: powershell-scripting
description: 'Guidance for PowerShell pipelines, file encoding, tool shims, and batch native commands. Use when a script depends on collection shape, writes files consumed by another OS or PowerShell version, resolves tools from version managers, or handles partial native-command failures.'
---

# PowerShell Scripting

Apply these rules where PowerShell behavior or supported versions affect the result.

## When not to use

- `az`, `gh`, or `.cmd` argument quoting and `cmd.exe` behavior: `windows-shell-safety`.
- Azure DevOps REST writes: `azure-devops-foundation`.
- Agent-session permission and sandbox command failures: `agent-sandbox-troubleshooting`.
- Scripts and executable examples in documentation: `script-author` when available.

## Rules

### 1. Wrap the whole pipeline in @() before using Count or an index

- **Rule:** Assign filtered pipeline output as `$items = @(Get-Thing | Where-Object { ... })`. Wrapping only the input does not prevent a single result from becoming a scalar.
- **Check:** Cover zero, one, and multiple results.
- **Why:** A single matching path was unwrapped and its string index was mistaken for an item index.

### 2. Match file encoding to the reader

- **Rule:** Choose line endings and encoding for the actual consumer. Windows PowerShell 5.1 reads BOM-less UTF-8 using the active code page, so a non-ASCII `.ps1` may require a UTF-8 BOM when it must run there or a repository analyzer requires it. Generated cross-platform text commonly needs UTF-8 without BOM and LF; set those explicitly. Do not assume PowerShell versions share defaults.
- **Check:** Read the file back using each supported runtime or inspect its bytes, including non-ASCII content where present.
- **Why:** A PowerShell script containing Japanese text needed a BOM for repository analysis, while generated checksum text needed BOM-less UTF-8 and LF for Unix tools.

### 3. Resolve shims to the real executable

- **Rule:** When behavior depends on which tool runs, resolve it through its version manager (for example `mise which python`) or the tool itself (`python -c "import sys; print(sys.executable)"`). Do not accept or reject a path solely because it is a shim.
- **Check:** Run where the tool is available only through its version manager.
- **Why:** An install script rejected a valid Python command because its path was a mise shim.

### 4. Handle native command failures at the boundary

- **Rule:** Capture `$LASTEXITCODE` immediately after each native call and apply the operation's failure policy. Stop if discovery or source refresh fails and the target set is unreliable; continue after an item failure only when the contract allows it, while preserving failures in the summary and final exit code.
- **Check:** Verify a discovery failure prevents changes and an allowed item failure is reported while subsequent items proceed. Cover partial-success reruns when supported.
- **Why:** A package batch needed to continue past an individual failure but stop when it could not reliably identify targets.
