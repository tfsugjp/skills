#Requires -Version 7.0
<#
.SYNOPSIS
    Run native CLIs (az, gh, ...) with JSON bodies and output that survive Windows argument passing.

.DESCRIPTION
    Dot-source this file to get:

    Invoke-NativeJson  Runs a native command with UTF-8 console encoding, sends -Body through a
                       UTF-8 (no BOM) temporary file referenced by '@<file>' (or a custom form),
                       parses stdout with ConvertFrom-Json, and throws with stderr on failure.
                       Refuses arguments that cmd.exe would rewrite when the target is a .cmd/.bat.
    Invoke-AzJson      Invoke-NativeJson for az: adds '-o json' and PYTHONIOENCODING=utf-8. Rejects a
                       non-JSON -o/--output unless -Raw is given.
    -EchoArgs          On either function: print the argv the target would receive instead of running it.
    Show-NativeArgs    Prints the argv a child process actually receives, through the same
                       .cmd shim path az.cmd uses on Windows, so argument loss is visible.

.EXAMPLE
    . ./Invoke-NativeJson.ps1
    $groups = Invoke-AzJson -Arguments 'group', 'list'
    $groups | Where-Object location -eq 'japaneast' | Select-Object -ExpandProperty name

.EXAMPLE
    . ./Invoke-NativeJson.ps1
    Invoke-AzJson -Arguments 'rest', '--method', 'post', '--uri', $uri -Body @{ name = 'x' }

.EXAMPLE
    . ./Invoke-NativeJson.ps1
    Invoke-NativeJson -FilePath gh -Arguments 'api', 'repos/{owner}/{repo}/issues', '--method', 'POST' `
        -Body @{ title = 'x' } -BodyParameter '--input' -BodyValueFormat '{0}'
#>

$script:CmdMetaPattern = '[|&<>^"]|%[^%\s]+%'

function Set-Utf8Console {
    $previous = @{ Console = [Console]::OutputEncoding; Output = $global:OutputEncoding }
    $utf8 = [Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $utf8
    $global:OutputEncoding = $utf8
    $previous
}

function Restore-Console($Previous) {
    [Console]::OutputEncoding = $Previous.Console
    $global:OutputEncoding = $Previous.Output
}

function Resolve-NativeTarget([string]$FilePath) {
    $command = Get-Command -Name $FilePath -CommandType Application -ErrorAction Ignore | Select-Object -First 1
    if (-not $command) { throw "Native command not found: $FilePath" }
    $command
}

function Test-BatchFile([string]$Path) {
    $IsWindows -and [IO.Path]::GetExtension($Path) -in '.cmd', '.bat'
}

function Assert-BatchSafeArguments([string[]]$Arguments, [string]$Target) {
    foreach ($argument in $Arguments) {
        if ($argument -match $script:CmdMetaPattern) {
            throw ("Argument '$argument' contains characters that cmd.exe rewrites for $Target. " +
                "Put the value in a UTF-8 file and pass '@<file>', or filter the JSON output in PowerShell.")
        }
    }
}

function Write-Utf8TempFile([string]$Content, [string]$Extension = '.json') {
    $path = Join-Path ([IO.Path]::GetTempPath()) ("wss-" + [guid]::NewGuid().ToString('N') + $Extension)
    [IO.File]::WriteAllText($path, $Content, [Text.UTF8Encoding]::new($false))
    $path
}

function Invoke-NativeJson {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$Arguments = @(),
        [object]$Body,
        [string]$BodyParameter = '--body',
        # Format of the body argument value; {0} is the temporary file path.
        [string]$BodyValueFormat = '@{0}',
        [hashtable]$Environment = @{},
        # Treat the target as a batch file even off Windows (used by tests).
        [switch]$AssumeBatch,
        # Return stdout as text instead of parsing it as JSON.
        [switch]$Raw,
        # Do not run the target; print the argv it would receive (body file included) via Show-NativeArgs.
        [switch]$EchoArgs
    )

    $target = Resolve-NativeTarget $FilePath
    $isBatch = $AssumeBatch -or (Test-BatchFile $target.Source)
    $argumentList = [System.Collections.Generic.List[string]]::new()
    foreach ($argument in $Arguments) { $argumentList.Add($argument) }

    $bodyFile = $null
    $errorFile = Write-Utf8TempFile '' '.err'
    $previousEnv = @{}
    $previousConsole = Set-Utf8Console
    try {
        if ($PSBoundParameters.ContainsKey('Body')) {
            $json = if ($Body -is [string]) { $Body } else { ConvertTo-Json -InputObject $Body -Depth 100 }
            $bodyFile = Write-Utf8TempFile $json
            if ($BodyParameter) { $argumentList.Add($BodyParameter) }
            $argumentList.Add(($BodyValueFormat -f $bodyFile))
        }
        if ($EchoArgs) {
            # Batch targets are echoed through a .cmd shim, so cmd.exe rewriting stays visible.
            return Show-NativeArgs @argumentList
        }
        if ($isBatch) { Assert-BatchSafeArguments $argumentList $target.Name }

        foreach ($name in $Environment.Keys) {
            $previousEnv[$name] = [Environment]::GetEnvironmentVariable($name)
            [Environment]::SetEnvironmentVariable($name, [string]$Environment[$name])
        }

        $stdout = & $target.Source @argumentList 2>$errorFile
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            $stderr = [IO.File]::ReadAllText($errorFile, [Text.Encoding]::UTF8).Trim()
            throw "$($target.Name) exited with $exitCode. $stderr"
        }

        $text = ($stdout | ForEach-Object { [string]$_ }) -join "`n"
        if ($Raw) { return $text }
        if ([string]::IsNullOrWhiteSpace($text)) { return $null }
        ConvertFrom-Json -InputObject $text -Depth 100
    }
    finally {
        foreach ($name in $previousEnv.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previousEnv[$name])
        }
        Restore-Console $previousConsole
        if ($bodyFile) { Remove-Item -LiteralPath $bodyFile -Force -ErrorAction Ignore }
        Remove-Item -LiteralPath $errorFile -Force -ErrorAction Ignore
    }
}

function Invoke-AzJson {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string[]]$Arguments,
        [object]$Body,
        [string]$BodyParameter = '--body',
        # Return stdout as text; required for non-JSON output such as -o tsv.
        [switch]$Raw,
        [switch]$EchoArgs
    )

    $arguments = @($Arguments)
    $output = $null
    for ($i = 0; $i -lt $arguments.Count; $i++) {
        if ($arguments[$i] -in '-o', '--output') {
            $output = if ($i + 1 -lt $arguments.Count) { $arguments[$i + 1] } else { '' }
        }
        elseif ($arguments[$i] -match '^(-o|--output)=(.*)$') {
            $output = $Matches[2]
        }
    }
    if ($null -eq $output) { $arguments += '-o', 'json' }
    elseif ($output -notin 'json', 'jsonc' -and -not $Raw -and -not $EchoArgs) {
        throw "Invoke-AzJson parses JSON, but the arguments request '-o $output'. Pass -Raw for text output, or drop the output option."
    }
    $parameters = @{
        FilePath      = 'az'
        Arguments     = $arguments
        BodyParameter = $BodyParameter
        Environment   = @{ PYTHONIOENCODING = 'utf-8' }
        Raw           = $Raw
        EchoArgs      = $EchoArgs
    }
    if ($PSBoundParameters.ContainsKey('Body')) { $parameters.Body = $Body }
    Invoke-NativeJson @parameters
}

function Show-NativeArgs {
    <#
    .SYNOPSIS
        Show the argv a child process receives. On Windows the call goes through a .cmd shim that
        forwards %* exactly like az.cmd, so cmd.exe rewriting is reproduced.
    #>
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments = @())

    $pwshPath = (Get-Process -Id $PID).Path
    $echoScript = Write-Utf8TempFile 'foreach ($a in $args) { "[$a]" }' '.ps1'
    $shim = $null
    try {
        if ($IsWindows) {
            $shim = Write-Utf8TempFile "@`"$pwshPath`" -NoProfile -NonInteractive -File `"$echoScript`" %*`r`n" '.cmd'
            & $shim @Arguments
        }
        else {
            & $pwshPath -NoProfile -NonInteractive -File $echoScript @Arguments
        }
    }
    finally {
        Remove-Item -LiteralPath $echoScript -Force -ErrorAction Ignore
        if ($shim) { Remove-Item -LiteralPath $shim -Force -ErrorAction Ignore }
    }
}
