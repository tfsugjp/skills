---
name: powershell-scripting
description: 'Rules for writing PowerShell 7 scripts, learned from review findings and failed runs. Use while writing or changing a .ps1 script or module that filters with Where-Object and then uses .Count or [0], writes checksum or other text files with Out-File or Set-Content for other operating systems, locates executables such as python or dotnet through PATH, mise, or pyenv shims, or composes agent shell commands that must match permission allow rules. For quoting, JSON, pipes, and encoding when calling az, gh, or other native commands on Windows, use windows-shell-safety instead.'
---

# PowerShell Scripting

These rules cover PowerShell behavior that differs from what the code appears to say. Native command argument passing on Windows is covered by `windows-shell-safety`; follow that skill whenever the script calls `az`, `gh`, `npm`, or another native tool with JSON, `--query`, or pipes.

## When not to use

- `az`, `gh`, or `.cmd` argument quoting, inline JSON, `cmd.exe` metacharacters, and console encoding: use `windows-shell-safety`.
- Azure DevOps REST writes: use the `azure-devops-foundation` skill.
- Scripts and executable examples in documentation: delegate to the `script-author` agent when it is available.

## Rules

### 1. Wrap the whole pipeline in @() before using Count or an index

- **Rule:** Write `$items = @(Get-Thing | Where-Object { ... })`. Wrapping only the input (`@($a) | Where-Object`) does not help: a single result is unwrapped to a scalar, so `.Count` and `[0]` change meaning (a string's `[0]` is its first character).
- **Check:** A test runs the function with zero, one, and two matching items.
- **Why:** Candidate selection collapsed to a string when exactly one path existed.

### 2. Write LF text for files other systems read

- **Rule:** Files consumed on Linux or macOS (checksum lists such as `SHA256SUMS`, shell scripts, generated YAML) are written with LF and UTF-8 without BOM: `[IO.File]::WriteAllText($path, ($lines -join "`n") + "`n", [Text.UTF8Encoding]::new($false))`. `Out-File` and `Set-Content` use CRLF on Windows.
- **Check:** The generated file has no `\r` bytes; when it is a checksum list, `sha256sum -c` passes on Linux.
- **Why:** A checksum list written with `Out-File` had CRLF line endings that break verification on Linux.

### 3. Keep names consistent in verification snippets

- **Rule:** In a download-and-verify snippet, the file name the snippet saves to and the name it looks up in the checksum list are the same string, including version and architecture.
- **Check:** Run the snippet against a real release asset.
- **Why:** A README snippet saved a generic file name but searched for the versioned name, so the verification never matched.

### 4. Resolve shims to the real executable

- **Rule:** When a script needs the real path of a tool installed through mise, pyenv, or a similar manager, resolve it with the manager (`mise which python`) or by asking the tool (`python -c "import sys; print(sys.executable)"`), and fail with a clear message when it cannot be resolved. Do not reject or accept a path only because it is a shim.
- **Check:** The script works on a machine where the tool is installed only through the manager.
- **Why:** An install script stopped with "not a mise shim" on a machine where Python was provided only by mise, and a global setting pointing at the wrong interpreter had to be fixed as well.

### 5. Shape agent shell commands to match permission rules

- **Rule:** Permission allow rules match the beginning of a command. Start each command with the program name and absolute paths; do not put variable assignments, `cd`, or another command in front of it, and keep authenticated `git` and `gh` calls as separate commands. Move multi-step logic into a script file.
- **Check:** The command's first word is the program that the allow rule names.
- **Why:** Commands that started with a variable assignment did not match the allow rules, which interrupted unattended work.

### 6. Fail on native command errors

- **Rule:** After calling a native program, check `$LASTEXITCODE` and throw on failure, or set `$PSNativeCommandUseErrorActionPreference = $true` with `$ErrorActionPreference = 'Stop'`.
- **Check:** A forced failure of the native call stops the script with a message.
- **Why:** Scripts that ignored exit codes reported success after a failed step.

## Done checklist

- [ ] Filtered results used with `.Count` or `[0]` are wrapped in `@()` and tested with one item.
- [ ] Cross-platform text files are LF and UTF-8 without BOM.
- [ ] Snippet file names match the names they verify.
- [ ] Tool discovery works through version-manager shims.
- [ ] Agent commands start with the program and use absolute paths.
- [ ] Native exit codes are checked.
- [ ] Native calls with JSON, queries, or pipes follow `windows-shell-safety`.
