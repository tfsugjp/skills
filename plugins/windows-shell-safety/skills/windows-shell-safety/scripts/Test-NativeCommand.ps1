#Requires -Version 7.0
<#
.SYNOPSIS
    Lint a command line or script for patterns that break on Windows before running it.

.DESCRIPTION
    Detects command shapes that lose pipes, quotes, or special characters when they pass
    through cmd.exe (az.cmd and other batch shims), nested shell -Command strings, Windows
    PowerShell 5.1, or a non-UTF-8 console. Each finding carries a rule ID, the reason, and
    the safe rewrite. Exit code is 0 when clean, 1 when any finding exists, 2 on bad input.

.EXAMPLE
    pwsh -NoProfile -File Test-NativeCommand.ps1 -Command 'az version --query "keys(@)|[0]"'

.EXAMPLE
    pwsh -NoProfile -File Test-NativeCommand.ps1 -Path ./deploy.ps1 -AsJson
#>
[CmdletBinding(DefaultParameterSetName = 'Command')]
param(
    [Parameter(ParameterSetName = 'Command', Mandatory, Position = 0, ValueFromPipeline)]
    [AllowEmptyString()]
    [string[]]$Command,

    [Parameter(ParameterSetName = 'Path', Mandatory)]
    [string]$Path,

    [switch]$AsJson
)

begin {
    $lines = [System.Collections.Generic.List[string]]::new()
}

process {
    if ($PSCmdlet.ParameterSetName -eq 'Command') {
        foreach ($item in $Command) { $lines.Add($item) }
    }
}

end {
    if ($PSCmdlet.ParameterSetName -eq 'Path') {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            Write-Error "File not found: $Path"
            exit 2
        }
        $text = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).ProviderPath, [Text.Encoding]::UTF8)
    }
    else {
        $text = $lines -join "`n"
    }

    $rules = @{
        WSS001 = @{
            Severity = 'error'
            Why      = 'cmd.exe re-parses the command line: | & < > ^ and %VAR% are consumed and quotes are reinterpreted.'
            Fix      = 'Run the tool directly from pwsh. Do not wrap it in cmd /c or %COMSPEC%.'
        }
        WSS002 = @{
            Severity = 'error'
            Why      = 'A -Command string is parsed by the outer shell first, which drops or splits pipes, quotes, and braces.'
            Fix      = 'Write the script to a temporary .ps1 file (UTF-8) and run: pwsh -NoProfile -NonInteractive -File <file>.'
        }
        WSS003 = @{
            Severity = 'error'
            Why      = 'az and other .cmd/.bat shims run through cmd.exe, which consumes | & < > ^ and expands %VAR% inside arguments.'
            Fix      = "Load the value from a file ('@query.txt') or drop --query and filter with ConvertFrom-Json | Where-Object / Select-Object."
        }
        WSS004 = @{
            Severity = 'error'
            Why      = 'Inline JSON passed to a .cmd/.bat target loses its double quotes (PowerShell keeps legacy argument passing for batch files).'
            Fix      = "Serialize with ConvertTo-Json into a UTF-8 (no BOM) temporary file and pass '@<file>' (quoted)."
        }
        WSS005 = @{
            Severity = 'error'
            Why      = 'Double quotes inside an argument to a .cmd/.bat target are stripped or re-paired by cmd.exe.'
            Fix      = "Move the value into a UTF-8 file and pass '@<file>', or filter the JSON output in PowerShell instead."
        }
        WSS006 = @{
            Severity = 'error'
            Why      = 'Windows PowerShell 5.1 uses legacy native argument passing and ASCII $OutputEncoding, so quotes and non-ASCII text are lost.'
            Fix      = 'Use pwsh (PowerShell 7).'
        }
        WSS007 = @{
            Severity = 'warning'
            Why      = 'Native output is decoded with [Console]::OutputEncoding; without UTF-8, non-ASCII text becomes ? before ConvertFrom-Json sees it.'
            Fix      = '[Console]::OutputEncoding = $OutputEncoding = [Text.UTF8Encoding]::new($false); for az also set $env:PYTHONIOENCODING = ''utf-8''.'
        }
        WSS008 = @{
            Severity = 'error'
            Why      = 'MSYS path-conversion workarounds mean the command is running in Git Bash/MSYS2, which adds another quoting layer before cmd.exe.'
            Fix      = 'Run the command from pwsh instead of patching MSYS argument conversion.'
        }
        WSS009 = @{
            Severity = 'error'
            Why      = 'An unquoted @name argument is PowerShell splatting, so the @file reference never reaches the tool.'
            Fix      = "Quote the file reference: '@body.json' (or `"@`$file`")."
        }
    }

    $findings = [System.Collections.Generic.List[object]]::new()
    $seen = [System.Collections.Generic.HashSet[string]]::new()
    $sourceLines = $text -split "`r?`n"

    function Add-Finding([string]$RuleId, [int]$Line, [string]$Snippet) {
        $key = "$RuleId|$Line|$Snippet"
        if (-not $seen.Add($key)) { return }
        $rule = $rules[$RuleId]
        $findings.Add([pscustomobject]@{
                RuleId   = $RuleId
                Severity = $rule.Severity
                Line     = $Line
                Snippet  = $Snippet.Trim()
                Why      = $rule.Why
                Fix      = $rule.Fix
            })
    }

    $tokens = $null
    $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$parseErrors)

    # Line rules see the text with comments and message strings blanked out, so prose such as
    # "# never wrap this in cmd /c" or Write-Host 'avoid powershell.exe' is not reported.
    $masked = $text.ToCharArray()
    function Hide-Extent([System.Management.Automation.Language.IScriptExtent]$Extent) {
        for ($c = $Extent.StartOffset; $c -lt $Extent.EndOffset; $c++) {
            if ($masked[$c] -ne "`n" -and $masked[$c] -ne "`r") { $masked[$c] = ' ' }
        }
    }
    foreach ($token in $tokens) {
        if ($token.Kind -eq [System.Management.Automation.Language.TokenKind]::Comment) { Hide-Extent $token.Extent }
    }
    $messageCommands = 'Write-Host', 'Write-Output', 'Write-Error', 'Write-Warning', 'Write-Verbose',
    'Write-Debug', 'Write-Information', 'echo'
    $messageStrings = $ast.FindAll({
            param($n)
            if ($n -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -and
                $n -isnot [System.Management.Automation.Language.ExpandableStringExpressionAst]) { return $false }
            if ($n.Parent -is [System.Management.Automation.Language.CommandAst]) {
                return $n.Parent.CommandElements[0] -ne $n -and $messageCommands -contains $n.Parent.GetCommandName()
            }
            $n.Parent -is [System.Management.Automation.Language.ThrowStatementAst] -or
            ($n.Parent -is [System.Management.Automation.Language.CommandExpressionAst] -and
                $n.Parent.Parent -is [System.Management.Automation.Language.PipelineAst] -and
                $n.Parent.Parent.Parent -is [System.Management.Automation.Language.ThrowStatementAst])
        }, $true)
    foreach ($node in $messageStrings) { Hide-Extent $node.Extent }
    $maskedLines = (-join $masked) -split "`r?`n"

    # Line rules work for PowerShell and for Bash/cmd command lines alike.
    $shellWord = '(?<![\w.$-])'
    for ($i = 0; $i -lt $sourceLines.Count; $i++) {
        $line = $sourceLines[$i]
        $code = $maskedLines[$i]
        if ($code -match "$shellWord(cmd(\.exe)?)[`"']?\s+[/-]{1,2}[ck]\b" -or $code -match '%COMSPEC%|\$env:COMSPEC' -or
            $code -match "(^|[;&|({]|\bexec|\bstart|Start-Process(\s+-FilePath)?)\s*[`"']?cmd(\.exe)?[`"']?(?=\s|$|[;&|)}])") {
            Add-Finding 'WSS001' ($i + 1) $line
        }
        if ($code -match "$shellWord(powershell(\.exe)?)(?=[\s`"']|$)") {
            Add-Finding 'WSS006' ($i + 1) $line
        }
        $commandArg = [regex]::Match($code, "$shellWord(pwsh|powershell)(\.exe)?[`"']?(\s+-\w+)*?\s+-(c|command)\s+(?<rest>.+)$", 'IgnoreCase')
        if ($commandArg.Success -and $commandArg.Groups['rest'].Value -match '[|"{}]') {
            Add-Finding 'WSS002' ($i + 1) $line
        }
        if ($code -match 'MSYS_NO_PATHCONV|MSYS2_ARG_CONV_EXCL') {
            Add-Finding 'WSS008' ($i + 1) $line
        }
    }

    # AST rules: arguments passed to batch-file targets.

    $batchTools = 'az', 'npm', 'npx', 'pnpm', 'yarn', 'code', 'func', 'ng'
    $cmdMeta = '[|&<>^]|%[^%\s]+%'
    $jsonParameters = '--body', '--parameters', '--properties', '--set', '--add', '--settings',
    '--value', '--json', '--headers', '--tags', '--required-resource-accesses', '--policy'

    function Get-TargetName([System.Management.Automation.Language.CommandAst]$Node) {
        $name = $Node.GetCommandName()
        if (-not $name) { return $null }
        [IO.Path]::GetFileName($name).ToLowerInvariant()
    }

    function Test-BatchTarget([string]$Name) {
        if (-not $Name) { return $false }
        if ($Name -match '\.(cmd|bat)$') { return $true }
        $batchTools -contains $Name
    }

    function Test-ConvertToJson([System.Management.Automation.Language.Ast]$Node) {
        [bool]$Node.Find({
                param($n)
                $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'ConvertTo-Json'
            }, $true)
    }

    # Track simple assignments so $query = '...|...'; az --query $query is caught too.
    $stringVariables = @{}
    $jsonVariables = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($assignment in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true)) {
        if ($assignment.Left -isnot [System.Management.Automation.Language.VariableExpressionAst]) { continue }
        $variableName = $assignment.Left.VariablePath.UserPath
        $right = $assignment.Right
        $constant = $right.Find({
                param($n)
                $n -is [System.Management.Automation.Language.StringConstantExpressionAst] -or
                $n -is [System.Management.Automation.Language.ExpandableStringExpressionAst]
            }, $true)
        if ($constant -and $right.Extent.Text.Trim() -eq $constant.Extent.Text.Trim()) {
            $stringVariables[$variableName] = $constant.Value
        }
        if (Test-ConvertToJson $right) { [void]$jsonVariables.Add($variableName) }
    }

    $commands = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($node in $commands) {
        $target = Get-TargetName $node
        if ($target -in 'cmd', 'cmd.exe') {
            Add-Finding 'WSS001' $node.Extent.StartLineNumber $sourceLines[$node.Extent.StartLineNumber - 1]
            continue
        }
        if (-not (Test-BatchTarget $target)) { continue }

        $elements = $node.CommandElements
        for ($e = 1; $e -lt $elements.Count; $e++) {
            $element = $elements[$e]
            $lineNumber = $element.Extent.StartLineNumber
            $snippet = $sourceLines[$lineNumber - 1]
            $previous = if ($e -gt 1 -and $elements[$e - 1] -is [System.Management.Automation.Language.CommandParameterAst]) {
                $elements[$e - 1].Extent.Text.ToLowerInvariant()
            }
            elseif ($e -gt 1 -and $elements[$e - 1] -is [System.Management.Automation.Language.StringConstantExpressionAst]) {
                $elements[$e - 1].Value.ToLowerInvariant()
            }

            # A bare @body or @body.json parses as splatting (or a member access on it), not a string.
            if ($element.Extent.Text -match '^@[\w]' -and
                $element -isnot [System.Management.Automation.Language.StringConstantExpressionAst] -and
                $element -isnot [System.Management.Automation.Language.ExpandableStringExpressionAst]) {
                Add-Finding 'WSS009' $lineNumber $snippet
                continue
            }

            if ($element -is [System.Management.Automation.Language.VariableExpressionAst]) {
                $variableName = $element.VariablePath.UserPath
                if ($jsonVariables.Contains($variableName)) {
                    Add-Finding 'WSS004' $lineNumber $snippet
                    continue
                }
                if ($stringVariables.ContainsKey($variableName)) {
                    $value = [string]$stringVariables[$variableName]
                }
                else {
                    continue
                }
            }
            elseif ($element -is [System.Management.Automation.Language.StringConstantExpressionAst] -or
                $element -is [System.Management.Automation.Language.ExpandableStringExpressionAst]) {
                $value = [string]$element.Value
                if ($element.StringConstantType -eq 'BareWord' -and $value -match '^--?[\w-]+$') { continue }
            }
            elseif ($element -is [System.Management.Automation.Language.ParenExpressionAst] -or
                $element -is [System.Management.Automation.Language.SubExpressionAst]) {
                if (Test-ConvertToJson $element) { Add-Finding 'WSS004' $lineNumber $snippet }
                continue
            }
            else {
                continue
            }

            if ($value.StartsWith('@')) { continue }
            $trimmed = $value.TrimStart()
            $isQuery = $previous -in '--query', '-q'
            $looksJson = -not $isQuery -and (
                ($trimmed.StartsWith('{') -and $trimmed.Contains(':')) -or
                ($trimmed.StartsWith('[') -and $trimmed.Contains('{') -and $trimmed.Contains(':')) -or
                ($jsonParameters -contains $previous -and $trimmed -match '^[\[{]'))
            if ($looksJson) {
                Add-Finding 'WSS004' $lineNumber $snippet
                continue
            }
            if ($value -match $cmdMeta) { Add-Finding 'WSS003' $lineNumber $snippet }
            if ($value.Contains('"')) { Add-Finding 'WSS005' $lineNumber $snippet }
        }
    }

    # Script rule: native output parsed as JSON before a UTF-8 console encoding is in effect.
    # A setting counts only when it runs earlier in the same or an enclosing block of the pipeline,
    # so comments, later assignments, and assignments inside other branches do not suppress it.
    $encodingSettings = @($ast.FindAll({
                param($n)
                $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
                $n.Left.Extent.Text -match '^\[(System\.)?Console\]::OutputEncoding$'
            }, $true))

    function Test-EncodingInEffect([System.Management.Automation.Language.Ast]$Pipeline) {
        foreach ($setting in $encodingSettings) {
            if ($setting.Extent.EndOffset -gt $Pipeline.Extent.StartOffset) { continue }
            $block = $setting.Parent
            while ($block -and $block -isnot [System.Management.Automation.Language.StatementBlockAst] -and
                $block -isnot [System.Management.Automation.Language.NamedBlockAst]) { $block = $block.Parent }
            $ancestor = $Pipeline.Parent
            while ($ancestor) {
                if ($ancestor -eq $block) { return $true }
                $ancestor = $ancestor.Parent
            }
        }
        $false
    }

    foreach ($pipeline in $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.PipelineAst] }, $true)) {
        $parts = $pipeline.PipelineElements
        if ($parts.Count -lt 2 -or $parts[0] -isnot [System.Management.Automation.Language.CommandAst]) { continue }
        $first = $parts[0].GetCommandName()
        if (-not $first -or $first.Contains('-') -or (Get-Alias -Name $first -ErrorAction Ignore)) { continue }
        $parsesJson = $parts | Select-Object -Skip 1 | Where-Object {
            $_ -is [System.Management.Automation.Language.CommandAst] -and $_.GetCommandName() -eq 'ConvertFrom-Json'
        }
        if ($parsesJson -and -not (Test-EncodingInEffect $pipeline)) {
            Add-Finding 'WSS007' $pipeline.Extent.StartLineNumber $sourceLines[$pipeline.Extent.StartLineNumber - 1]
        }
    }

    $ordered = @($findings | Sort-Object Line, RuleId)
    if ($AsJson) {
        ConvertTo-Json -InputObject $ordered -Depth 3
    }
    elseif ($ordered.Count -eq 0) {
        'OK: no Windows shell-safety findings.'
    }
    else {
        foreach ($finding in $ordered) {
            "$($finding.RuleId) [$($finding.Severity)] line $($finding.Line): $($finding.Snippet)"
            "  why: $($finding.Why)"
            "  fix: $($finding.Fix)"
        }
    }
    exit ([int]($ordered.Count -gt 0))
}
