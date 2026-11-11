---
name: powershell-scripting
description: 'Rules for writing PowerShell scripts, learned from review findings and failed runs. Use when a script filters a pipeline and then reads Count or an index, writes text files that Linux or macOS will read (checksums, YAML, shell scripts), locates tools installed through mise, pyenv, or another shim manager, or runs batch changes through WinGet, az, or other native programs and must handle partial failure.'
---

# PowerShell Scripting

These rules cover PowerShell behavior that differs from what the code appears to say.

## When not to use

- `az`, `gh`, or `.cmd` argument quoting, inline JSON, `cmd.exe` metacharacters, and console encoding: `windows-shell-safety`.
- Azure DevOps REST writes: `azure-devops-foundation`.
- The shape of commands an agent runs under permission rules or a sandbox: `agent-sandbox-troubleshooting`.
- Scripts and executable examples in documentation: the `script-author` agent when available; snippet naming is in `dotnet-documentation`.

## Rules

### 1. Wrap the whole pipeline in @() before using Count or an index

- **Rule:** Write `$items = @(Get-Thing | Where-Object { ... })`. Wrapping only the input (`@($a) | Where-Object`) does not help: a single result is unwrapped to a scalar, so `.Count` and `[0]` change meaning (a string's `[0]` is its first character).
- **Check:** A test runs the function with zero, one, and two matching items.
- **Why:** Candidate selection collapsed to a string when exactly one path existed.

### 2. Write LF text for files other systems read

- **Rule:** Files read on Linux or macOS (`SHA256SUMS`, shell scripts, generated YAML) are written with LF and UTF-8 without BOM: `[IO.File]::WriteAllText($path, ($lines -join "`n") + "`n", [Text.UTF8Encoding]::new($false))`. `Out-File` and `Set-Content` write CRLF on Windows, and in Windows PowerShell 5.1 `Out-File` defaults to UTF-16LE and `Set-Content` to the ANSI code page.
- **Check:** The file has no `\r` bytes; `sha256sum -c` (or `shasum -a 256 -c` on macOS) passes for a checksum list.
- **Why:** A checksum list written with `Out-File` had CRLF line endings that broke verification on Linux.

### 3. Resolve shims to the real executable

- **Rule:** Resolve a tool installed through mise, pyenv, or a similar manager with the manager (`mise which python`) or the tool itself (`python -c "import sys; print(sys.executable)"`), and fail clearly when it cannot be resolved. Do not accept or reject a path only because it is a shim.
- **Check:** The script works where the tool is installed only through the manager.
- **Why:** An install script stopped with "not a mise shim" on a machine where Python came only from mise.

### 4. Classify native command failures before continuing

- **Rule:** Capture `$LASTEXITCODE` immediately after a native call and fail on unhandled codes. Resolve the exact package or resource ID and its source before changing anything. Stop when a failed prerequisite (discovery, source refresh) makes the target set unreliable; continue after an individual failure only when the contract allows it, and keep each failure in the summary and exit code.
- **Check:** Mock a failed discovery (no item changes run) and an allowed item failure (the next item runs and the failure is reported). Test a rerun after partial success under each supported PowerShell version, including 5.1 when supported.
- **Why:** A batch had to continue after one package update failed while still stopping when discovery or source refresh failed.

## Before reporting done

Confirm each applicable Check above; native calls with JSON, queries, or pipes also follow `windows-shell-safety`.
