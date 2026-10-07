# Broken Patterns and Safe Rewrites

Each section shows a command shape that fails on Windows, why it fails, and the rewrite to use instead. The lint rule ID is in the heading.

## Why az is different (WSS003, WSS004, WSS005)

`Get-Command az` on Windows resolves to `az.cmd`. Windows starts batch files through `cmd.exe`, so an `az` argument is parsed twice: once by PowerShell, once by cmd.exe. Microsoft's Azure CLI documentation states that az receives a symbol only if it survives both rounds of parsing.

- PowerShell 7.3+ defaults to `$PSNativeCommandArgumentPassing = 'Windows'`, which uses **legacy** quoting for `.cmd`/`.bat` targets. An argument is wrapped in quotes only when it contains whitespace, and embedded `"` is not escaped.
- cmd.exe treats an unquoted `|`, `&`, `<`, `>` as operators and `^` as an escape, and expands `%NAME%` everywhere, including inside quotes.
- The receiving program re-splits the command line, so stray quotes regroup arguments.

Executables such as `gh.exe`, `git.exe`, and `curl.exe` do not go through cmd.exe and are safe from pwsh 7.3+. Other common batch shims: `npm`, `npx`, `pnpm`, `yarn`, `code`, `func`, `ng`.

## JMESPath with pipes (WSS003)

Broken: `|` without surrounding spaces is passed unquoted and cmd.exe runs `[0]` as a command.

```powershell
az group list --query "[?location=='japaneast']|[0].name" -o tsv
```

Safe: filter the JSON in PowerShell.

```powershell
[Console]::OutputEncoding = $OutputEncoding = [Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
$groups = az group list -o json | ConvertFrom-Json
$groups | Where-Object location -eq 'japaneast' | Select-Object -First 1 -ExpandProperty name
```

Safe: keep the JMESPath, but load it from a file.

```powershell
$queryFile = New-TemporaryFile
try {
    [IO.File]::WriteAllText($queryFile, "[?location=='japaneast'] | [0].name", [Text.UTF8Encoding]::new($false))
    az group list --query "@$queryFile" -o tsv
}
finally { Remove-Item $queryFile -Force }
```

## JMESPath with double quotes (WSS005)

Broken: `"azure-cli"` reaches az as `azure-cli`, which JMESPath reads as a subtraction.

```powershell
az version --query '"azure-cli"' -o tsv
```

Safe: `(az version -o json | ConvertFrom-Json).'azure-cli'`, or the `@<file>` form above.

## Inline JSON bodies (WSS004)

Broken: the quotes are stripped, so az receives `{name:demo}` and reports `Failed to parse string as JSON`.

```powershell
az rest --method post --uri $uri --body '{"name":"demo"}'
az rest --method post --uri $uri --body ($payload | ConvertTo-Json)
```

Safe:

```powershell
$bodyFile = New-TemporaryFile
try {
    $json = ConvertTo-Json -InputObject @{ name = 'demo' } -Depth 20
    [IO.File]::WriteAllText($bodyFile, $json, [Text.UTF8Encoding]::new($false))
    az rest --method post --uri $uri --body "@$bodyFile"
}
finally { Remove-Item $bodyFile -Force }
```

Or `Invoke-AzJson -Arguments 'rest', '--method', 'post', '--uri', $uri -Body @{ name = 'demo' }`. The same applies to `--parameters`, `--properties`, `--set`, `--settings`, and `--tags` values that contain quotes or metacharacters.

## Unquoted @file (WSS009)

Broken: `@body.json` is PowerShell splatting; az never sees the file reference.

```powershell
az rest --method post --uri $uri --body @body.json
```

Safe: `--body '@body.json'` or `--body "@$bodyFile"`.

## Environment variable syntax (WSS003)

Broken: cmd.exe expands `%USERNAME%` before az runs, even inside quotes.

```powershell
az tag create --resource-id $id --tags "owner=%USERNAME%"
```

Safe: expand in PowerShell (`"owner=$env:USERNAME"`) so cmd.exe receives plain text.

## cmd /c wrappers (WSS001)

Broken: the outer cmd.exe applies `|` and `&` and strips quotes before the inner command runs.

```powershell
cmd /c "az group list -o json | findstr prod"
```

Safe: run the tool from pwsh and use PowerShell pipelines (`az group list -o json | ConvertFrom-Json | Where-Object name -like '*prod*'`).

## -Command strings from Bash or cmd (WSS002, WSS006, WSS008)

Broken: Git Bash expands `$` and consumes quotes, then PowerShell parses what is left.

```bash
pwsh -c "az group list -o json | ConvertFrom-Json | Select-Object name"
powershell -Command "$x = az account show | ConvertFrom-Json; $x.name"
MSYS_NO_PATHCONV=1 az repos show --repository /project/repo
```

Safe: write the script with a quoted here-document (no Bash expansion) and run it with `-File`.

```bash
script_file=$(mktemp "${TMPDIR:-/tmp}/wss-XXXXXX.ps1")
cat >"$script_file" <<'PS1'
[Console]::OutputEncoding = $OutputEncoding = [Text.UTF8Encoding]::new($false)
az group list -o json | ConvertFrom-Json | Select-Object -ExpandProperty name
PS1
pwsh -NoProfile -NonInteractive -File "$script_file"
rm -f "$script_file"
```

Lint the script file before running it: `pwsh -NoProfile -File scripts/Test-NativeCommand.ps1 -Path "$script_file"`.

## Non-ASCII output (WSS007)

Broken: pwsh decodes native stdout with `[Console]::OutputEncoding` (often the OEM code page), and Python-based az writes with the locale code page when redirected, so Japanese text becomes `?` or mojibake before `ConvertFrom-Json` runs.

Safe: set both encodings to UTF-8 and `PYTHONIOENCODING=utf-8` first (Rule 5), or use `Invoke-AzJson`, which does both for the duration of the call.

## Diagnosing a failure

```powershell
. ./scripts/Invoke-NativeJson.ps1
Show-NativeArgs '--query' "[?name=='a']|[0]" '{"k":"v"}'
```

On Windows this runs through a `.cmd` shim that forwards `%*` exactly like `az.cmd` and prints each received argument in brackets. If the output differs from what you passed, change the pattern (file or PowerShell filtering), not the escaping.

A script that ends right after a failing native call (or a lint run with findings) exits with that stale `$LASTEXITCODE` when it is launched with `pwsh -Command`, as the GitHub Actions `pwsh` shell does. End such scripts with an explicit `exit 0` or `exit 1`.
