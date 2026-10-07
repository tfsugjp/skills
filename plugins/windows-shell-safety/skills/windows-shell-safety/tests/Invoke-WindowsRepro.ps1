#Requires -Version 7.0
<#
.SYNOPSIS
    Reproduce cmd.exe argument loss on Windows and prove the skill's safe patterns work.
    Runs in the windows-latest CI job; needs az on PATH but no Azure sign-in.
#>
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'This reproduction must run on Windows.' }

$scripts = Join-Path $PSScriptRoot '..' 'scripts'
. (Join-Path $scripts 'Invoke-NativeJson.ps1')
$lint = Join-Path $scripts 'Test-NativeCommand.ps1'
$failures = 0

function Assert-That([bool]$Condition, [string]$Message) {
    if ($Condition) { Write-Host "PASS  $Message" }
    else { Write-Host "FAIL  $Message"; $script:failures++ }
}

function Invoke-Captured([scriptblock]$Block) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $output = & $Block 2>&1 | ForEach-Object { "$_" } }
    finally { $ErrorActionPreference = $previous }
    [pscustomobject]@{ Output = @($output); ExitCode = $LASTEXITCODE }
}

Write-Host "PowerShell $($PSVersionTable.PSVersion), PSNativeCommandArgumentPassing=$PSNativeCommandArgumentPassing"
$azCommand = Get-Command az -CommandType Application | Select-Object -First 1
Write-Host "az resolves to $($azCommand.Source)"
Assert-That ([IO.Path]::GetExtension($azCommand.Source) -eq '.cmd') 'az is a batch file (az.cmd), so cmd.exe parses its arguments'

# 1. A .cmd shim (same %* forwarding as az.cmd) does not receive what PowerShell passed.
$cases = [ordered]@{
    'pipe without spaces'   = 'a|b'
    'ampersand'             = 'a&b'
    'inline JSON'           = '{"name":"demo"}'
    'environment reference' = '%USERNAME%'
}
foreach ($case in $cases.GetEnumerator()) {
    $received = Invoke-Captured { Show-NativeArgs $case.Value }
    Write-Host "      $($case.Key): sent [$($case.Value)] received $($received.Output -join ' ')"
    Assert-That ($received.Output -notcontains "[$($case.Value)]") "cmd.exe rewrites $($case.Key)"
}
$plain = Invoke-Captured { Show-NativeArgs 'plain-value' }
Assert-That ($plain.Output -contains '[plain-value]') 'plain arguments pass through the shim unchanged'

# 2. The same loss hits az itself.
$expected = (Invoke-AzJson -Arguments 'version').'azure-cli'
Assert-That ($expected -match '^\d+\.\d+') "Invoke-AzJson parses az output (azure-cli $expected)"

$broken = Invoke-Captured { az version --query 'keys(@)|[0]' -o tsv }
Assert-That ($broken.ExitCode -ne 0 -or ($broken.Output -join '') -ne 'azure-cli') 'az --query with an unquoted | is broken by cmd.exe'

$quoted = Invoke-Captured { az version --query '"azure-cli"' -o tsv }
Assert-That (($quoted.Output -join '').Trim() -ne $expected) 'az --query with embedded double quotes loses them'

# 3. Safe patterns from the skill.
$queryFile = Join-Path ([IO.Path]::GetTempPath()) "wss-query-$([guid]::NewGuid().ToString('N')).txt"
try {
    [IO.File]::WriteAllText($queryFile, '"azure-cli"', [Text.UTF8Encoding]::new($false))
    $fromFile = Invoke-Captured { az version --query "@$queryFile" -o tsv }
    Assert-That (($fromFile.Output -join '').Trim() -eq $expected) "--query '@<file>' keeps quotes and metacharacters"
}
finally { Remove-Item -LiteralPath $queryFile -Force -ErrorAction Ignore }

$filtered = Invoke-AzJson -Arguments 'version' | Select-Object -ExpandProperty 'azure-cli'
Assert-That ($filtered -eq $expected) 'filtering ConvertFrom-Json output in PowerShell replaces --query'

$refused = $false
try { Invoke-AzJson -Arguments 'version', '--query', 'keys(@)|[0]' | Out-Null }
catch { $refused = $_.Exception.Message -match 'cmd.exe rewrites' }
Assert-That $refused 'Invoke-AzJson refuses cmd metacharacters before calling az.cmd'

# 4. The lint flags every broken form used above.
foreach ($command in "az version --query 'keys(@)|[0]' -o tsv", "az version --query '`"azure-cli`"' -o tsv", 'cmd /c "az version | findstr azure"') {
    $result = Invoke-Captured { & $lint -Command $command -AsJson }
    Assert-That ($result.ExitCode -eq 1) "lint flags: $command"
}

if ($failures -gt 0) {
    Write-Host "$failures check(s) failed."
    exit 1
}
Write-Host 'All Windows reproduction checks passed.'
