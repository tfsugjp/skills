---
name: windows-shell-safety
description: 'Run Azure CLI (az), gh, npm, and other native commands on Windows without losing pipes, quotes, JSON, or special characters to cmd.exe, nested PowerShell -Command strings, or console encoding. Use before running az with --query, --body, --parameters, or any inline JSON on Windows; when piping native output into ConvertFrom-Json; when calling PowerShell from Git Bash or cmd; or when a Windows command fails with "is not recognized", "Failed to parse string as JSON", "Invalid jmespath", empty output, or garbled non-ASCII text.'
---

# Windows Shell Safety

On Windows, `az` is `az.cmd`, a batch file. Every argument passes through PowerShell **and then cmd.exe**, so `|`, `&`, `<`, `>`, `^`, and `%VAR%` are consumed and embedded double quotes are stripped (PowerShell 7.3+ keeps legacy argument passing for `.cmd`/`.bat` targets). Nesting `powershell -Command "..."` inside Git Bash or cmd adds yet another parser. Retrying the same command with different escaping wastes time; follow these rules instead.

Paths below are relative to this skill directory.

## Rules

1. **Use `pwsh` (PowerShell 7) only.** Do not route commands through `cmd /c`, `%COMSPEC%`, Windows PowerShell 5.1 (`powershell.exe`), or Git Bash/MSYS (`MSYS_NO_PATHCONV` is a symptom, not a fix).
2. **Never put a script in a `-Command` string.** Write it to a UTF-8 `.ps1` file and run `pwsh -NoProfile -NonInteractive -File <file>`. This is the way to run PowerShell from a Bash tool.
3. **Never put JSON in a command-line argument.** Build a PowerShell object, `ConvertTo-Json -Depth 20`, write it to a UTF-8 (no BOM) temporary file, and pass `'@<file>'` (quoted: a bare `@file` is PowerShell splatting). Delete the file in `finally`.
4. **Keep cmd metacharacters and double quotes out of `az` arguments.** For `--query`, either filter in PowerShell (`-o json | ConvertFrom-Json | Where-Object ...`) or load the expression from a file: `--query '@query.txt'` (az accepts `@<file>` for any argument value). Simple projections such as `--query name -o tsv` are fine.
5. **Set UTF-8 before reading native output:** `[Console]::OutputEncoding = $OutputEncoding = [Text.UTF8Encoding]::new($false)`, and `$env:PYTHONIOENCODING = 'utf-8'` for `az`.
6. **Lint before running** any command or script that calls a native tool with JSON, `--query`, pipes, or nested shells. Fix every finding, then run.
7. **When a native call still fails, inspect what arrived** with `Show-NativeArgs` before changing the escaping. Never retry the same shape twice.

## Lint before running

```powershell
pwsh -NoProfile -File scripts/Test-NativeCommand.ps1 -Command 'az version --query "keys(@)|[0]" -o tsv'
pwsh -NoProfile -File scripts/Test-NativeCommand.ps1 -Path ./deploy.ps1 -AsJson
```

Exit code 0 means clean, 1 means findings (each with `why` and `fix`), 2 means the input file is missing. The lint parses PowerShell, but its line rules also catch `cmd /c`, nested `-Command`, and MSYS workarounds in Bash command lines.

| Rule | Detects | Safe rewrite |
| --- | --- | --- |
| WSS001 | `cmd /c`, `cmd.exe`, `%COMSPEC%` | Call the tool from pwsh directly |
| WSS002 | `pwsh`/`powershell -Command` string with `\|`, `"`, or braces | `.ps1` file + `-File` |
| WSS003 | `\| & < > ^ %VAR%` in an argument to `az` or another `.cmd`/`.bat` | `'@<file>'` or `ConvertFrom-Json` filtering |
| WSS004 | Inline JSON (literal, `ConvertTo-Json` result, or variable) to a `.cmd`/`.bat` | UTF-8 file + `'@<file>'` |
| WSS005 | Double quotes inside an argument to a `.cmd`/`.bat` | `'@<file>'` |
| WSS006 | Windows PowerShell 5.1 (`powershell.exe`) | `pwsh` |
| WSS007 | Native output piped to `ConvertFrom-Json` without UTF-8 console encoding | Rule 5 |
| WSS008 | `MSYS_NO_PATHCONV`, `MSYS2_ARG_CONV_EXCL` | Run from pwsh |
| WSS009 | Unquoted `@file` argument (PowerShell splatting) | `'@file'` |

## Safe execution helper

Dot-source [scripts/Invoke-NativeJson.ps1](scripts/Invoke-NativeJson.ps1):

```powershell
. ./scripts/Invoke-NativeJson.ps1

# az output as objects; filter in PowerShell instead of --query.
$version = Invoke-AzJson -Arguments 'version'
$version.'azure-cli'

# Request body goes through a UTF-8 temp file as --body '@<file>'.
Invoke-AzJson -Arguments 'rest', '--method', 'post', '--uri', $uri -Body @{ name = 'demo'; note = 'a|b "c"' }

# Other CLIs: choose how the file is referenced (gh api reads it with --input <file>).
Invoke-NativeJson -FilePath gh -Arguments 'api', 'repos/{owner}/{repo}/issues', '--method', 'POST' `
    -Body @{ title = 'x' } -BodyParameter '--input' -BodyValueFormat '{0}'

# See the argv a .cmd target actually receives (Windows reproduces az.cmd's %* forwarding).
Show-NativeArgs 'a|b' '{"name":"demo"}'
```

`Invoke-NativeJson` sets UTF-8 encodings for the call, throws with stderr on a non-zero exit code, and refuses (before running) any argument that cmd.exe would rewrite when the target is a `.cmd`/`.bat` file.

## References

- [references/patterns.md](references/patterns.md) — broken command shapes, what cmd.exe does to them, and the safe rewrite for each.
- For Azure DevOps REST writes (work items, Wiki, pull requests), the Azure DevOps foundation skill in the `azure-devops-toolkit` plugin documents the same file-based UTF-8 request pattern with `Invoke-RestMethod -InFile`.

## Tests

```bash
python3 tests/test_native_command_lint.py -v
```

`tests/Invoke-WindowsRepro.ps1` runs in the `windows-latest` CI job: it shows `az.cmd` and a `.cmd` shim losing `|`, `&`, `%VAR%`, and quotes, and verifies that `'@<file>'`, `ConvertFrom-Json` filtering, and the helper's refusal behave as documented.
