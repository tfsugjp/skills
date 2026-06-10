#!/usr/bin/env pwsh
#Requires -Version 7.0
<#
.SYNOPSIS
    Claude Code PreToolUse hook enforcing Azure guardrails.

.DESCRIPTION
    Reads the PreToolUse hook payload from stdin, classifies the pending
    Azure operation (az / azd / Az PowerShell / Microsoft Graph / Azure MCP
    tools), checks the project's .azure-guardrails.yml allowlist, and emits a
    permission decision:

      deny  - operation matches a `deny` entry (blocked even with approval)
      allow - operation matches an `allow` entry (and is not an identity op)
      ask   - mutating operation with no allowlist match -> user must approve
      (no output) - read-only / non-Azure -> normal permission flow applies

    Identity operations (Entra ID users/groups/apps/SPs, role assignments,
    Graph writes) always result in `ask` (or `deny`); the allowlist cannot
    exempt them.

.NOTES
    Config file: .azure-guardrails.yml / .yaml / .json, searched upward from
    the session cwd. YAML requires the `powershell-yaml` module; without it,
    use the JSON variant. If a YAML config exists but cannot be parsed, the
    hook fails closed (ask) for mutating operations.
#>

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
try {
    $payload = [Console]::In.ReadToEnd() | ConvertFrom-Json
} catch {
    exit 0  # unparseable payload -> no opinion
}

$toolName = [string]$payload.tool_name
$sessionCwd = if ($payload.cwd) { [string]$payload.cwd } else { (Get-Location).Path }

function Emit-Decision {
    param(
        [ValidateSet('allow', 'deny', 'ask')] [string]$Decision,
        [string]$Reason
    )
    @{
        hookSpecificOutput = @{
            hookEventName            = 'PreToolUse'
            permissionDecision       = $Decision
            permissionDecisionReason = "[azure-guardrails] $Reason"
        }
    } | ConvertTo-Json -Depth 5 -Compress | Write-Output
    exit 0
}

# ---------------------------------------------------------------------------
# Config: locate and parse .azure-guardrails.yml / .yaml / .json
# ---------------------------------------------------------------------------
function Find-GuardrailsConfig {
    param([string]$StartDir)
    $dir = $StartDir
    while ($dir) {
        foreach ($name in '.azure-guardrails.yml', '.azure-guardrails.yaml', '.azure-guardrails.json') {
            $candidate = Join-Path $dir $name
            if (Test-Path $candidate -PathType Leaf) { return $candidate }
        }
        $parent = Split-Path $dir -Parent
        if (-not $parent -or $parent -eq $dir) { return $null }
        $dir = $parent
    }
    return $null
}

# Returns @{ Config = <obj|null>; ParseFailed = <bool> }
function Read-GuardrailsConfig {
    param([string]$Path)
    if (-not $Path) { return @{ Config = $null; ParseFailed = $false } }
    try {
        $raw = Get-Content -Path $Path -Raw
        if ($Path -like '*.json') {
            return @{ Config = ($raw | ConvertFrom-Json); ParseFailed = $false }
        }
        if (Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue) {
            return @{ Config = ($raw | ConvertFrom-Yaml); ParseFailed = $false }
        }
        return @{ Config = $null; ParseFailed = $true }  # YAML present, no parser
    } catch {
        return @{ Config = $null; ParseFailed = $true }
    }
}

# ---------------------------------------------------------------------------
# Command classification
#   Returns $null (no opinion) or @{ Tier = 3|4; What = '<description>' }
# ---------------------------------------------------------------------------
function Get-CommandClassification {
    param([string]$Command)

    if (-not $Command) { return $null }
    $cmd = ($Command -replace '\s+', ' ').Trim()

    # --- Tier 4: identity operations -------------------------------------
    # az ad <object> <verb> where verb is not a read
    if ($cmd -imatch '\baz\s+ad\s+(user|group|app|sp|signed-in-user)\b(?![\w-]*\s+(list|show)\b)') {
        $segment = [regex]::Match($cmd, '\baz\s+ad\s+[^|;&]*', 'IgnoreCase').Value
        if ($segment -inotmatch '\b(list|show|get-member-groups|check-membership)\b') {
            return @{ Tier = 4; What = 'Entra ID object write (az ad)' }
        }
    }
    if ($cmd -imatch '\baz\s+role\s+(assignment|definition)\s+(create|delete|update)\b') {
        return @{ Tier = 4; What = 'RBAC role change (az role)' }
    }
    if ($cmd -imatch '\b(New|Set|Update|Remove)-AzAD\w+') {
        return @{ Tier = 4; What = 'Entra ID object write (Az PowerShell)' }
    }
    if ($cmd -imatch '\b(New|Remove)-AzRoleAssignment\b|\b(New|Set|Remove)-AzRoleDefinition\b') {
        return @{ Tier = 4; What = 'RBAC role change (Az PowerShell)' }
    }
    if ($cmd -imatch '\b(New|Set|Update|Remove|Invoke)-Mg\w+' -and
        $cmd -inotmatch '\bInvoke-MgGraphRequest\b[^|;&]*-Method\s+(''|")?GET\b') {
        return @{ Tier = 4; What = 'Microsoft Graph write (Mg cmdlet)' }
    }
    if ($cmd -imatch 'graph\.microsoft\.com' -and
        $cmd -imatch '(-Method|--method|-X)\s+(''|")?(PUT|PATCH|DELETE|POST)\b') {
        return @{ Tier = 4; What = 'Microsoft Graph write (raw API)' }
    }
    if ($cmd -imatch '\baz\s+keyvault\s+(set-policy|delete-policy)\b') {
        return @{ Tier = 4; What = 'Key Vault access policy change' }
    }

    # --- Tier 1 exclusions before generic mutation matching --------------
    # Session/config-only commands that contain mutation-looking verbs.
    if ($cmd -imatch '^\s*az\s+(account\s+set|config\s+set|configure|login|logout)\b' -and
        $cmd -inotmatch '[|;&]') {
        return $null
    }

    # --- Tier 3: delete --------------------------------------------------
    if ($cmd -imatch '\baz\s+[\w-]+(\s+[\w-]+)*\s+(delete|purge)\b') {
        return @{ Tier = 3; What = 'az delete/purge' }
    }
    if ($cmd -imatch '\bazd\s+down\b') {
        return @{ Tier = 3; What = 'azd down (environment teardown)' }
    }
    if ($cmd -imatch '\b(Remove|Clear)-Az\w+') {
        return @{ Tier = 3; What = 'Az PowerShell Remove/Clear' }
    }

    # --- Tier 3: modify --------------------------------------------------
    if ($cmd -imatch '\baz\s+[\w-]+(\s+[\w-]+)*\s+(update|set|import|restart|stop|start|deallocate|scale|resize|recover|restore|failover)\b') {
        return @{ Tier = 3; What = 'az modify (update/set/start/stop/...)' }
    }
    if ($cmd -imatch '\b(Set|Update|Start|Stop|Restart|Move|Import|Restore|Undo)-Az\w+' -and
        $cmd -inotmatch '^\s*(Set-AzContext|Select-AzSubscription|Set-AzConfig|Set-AzDefault)\b') {
        return @{ Tier = 3; What = 'Az PowerShell modify cmdlet' }
    }
    if ($cmd -imatch '\baz\s+rest\b[^|;&]*--method\s+(''|")?(put|patch|delete|post)\b') {
        return @{ Tier = 3; What = 'az rest with mutating HTTP method' }
    }
    if ($cmd -imatch '\bInvoke-AzRestMethod\b[^|;&]*-Method\s+(''|")?(PUT|PATCH|DELETE|POST)\b') {
        return @{ Tier = 3; What = 'Invoke-AzRestMethod with mutating HTTP method' }
    }
    if ($cmd -imatch '\bazd\s+deploy\b') {
        return @{ Tier = 3; What = 'azd deploy (replaces running code)' }
    }

    return $null
}

# ---------------------------------------------------------------------------
# MCP tool classification
#   Returns $null or @{ Tier; What; MatchString }
# ---------------------------------------------------------------------------
$script:McpSafeAreas = @(
    'documentation', 'pricing', 'bicepschema', 'azureterraformbestpractices',
    'get_azure_bestpractices', 'cloudarchitect', 'wellarchitectedframework',
    'marketplace', 'advisor', 'applens', 'extension_azqr', 'extension_cli_generate',
    'subscription_list', 'group_list', 'group_resource_list', 'resourcehealth',
    'quota', 'applicationinsights', 'workbooks'
)

function Get-McpClassification {
    param([string]$ToolName, $ToolInput)

    if ($ToolName -inotmatch '^mcp__.*azure.*__(?<area>\w+)$') { return $null }
    $area = $Matches['area'].ToLowerInvariant()

    if ($script:McpSafeAreas -contains $area) { return $null }

    # Pull the requested operation out of common parameter names.
    $op = ''
    foreach ($prop in 'command', 'operation', 'intent', 'subcommand', 'method') {
        $val = if ($ToolInput) { $ToolInput.PSObject.Properties[$prop].Value } else { $null }
        if ($val -is [string] -and $val) { $op = $val; break }
    }
    $paramsBlob = ($ToolInput | ConvertTo-Json -Depth 10 -Compress) ?? ''
    $haystack = "$op $paramsBlob"

    $writePattern = '\b(delete|remove|purge|create-or-update|update|set|restart|stop|start|scale|upload|import|failover)\b'

    if ($area -eq 'role' -and $haystack -imatch $writePattern) {
        return @{ Tier = 4; What = 'Azure MCP role (RBAC) write'; MatchString = "mcp:$area $op" }
    }
    if ($area -eq 'deploy') {
        return @{ Tier = 3; What = 'Azure MCP deploy'; MatchString = "mcp:$area $op" }
    }
    if ($haystack -imatch $writePattern) {
        return @{ Tier = 3; What = "Azure MCP $area write operation"; MatchString = "mcp:$area $op" }
    }
    return $null  # read-style call -> no opinion
}

# ---------------------------------------------------------------------------
# Allowlist matching
# ---------------------------------------------------------------------------
function Get-ResourceGroupFromCommand {
    param([string]$Command)
    $m = [regex]::Match($Command,
        '(?:(?:-g|--resource-group(?:-name)?|-ResourceGroupName)[\s=]+)(?:"(?<q>[^"]+)"|''(?<q>[^'']+)''|(?<q>[^\s"'']+))',
        'IgnoreCase')
    if ($m.Success) { return $m.Groups['q'].Value }

    # For `az group <verb>` the resource group is identified by -n / --name,
    # not -g. Treat that name as the resource group for scope matching.
    if ($Command -imatch '\baz\s+group\s+(create|delete|update|export|wait|lock)\b') {
        $n = [regex]::Match($Command,
            '(?:(?:-n|--name)[\s=]+)(?:"(?<q>[^"]+)"|''(?<q>[^'']+)''|(?<q>[^\s"'']+))',
            'IgnoreCase')
        if ($n.Success) { return $n.Groups['q'].Value }
    }
    return $null
}

function Test-EntryMatch {
    param($Entry, [string]$NormalizedCommand, [string]$ResourceGroup)

    $opPrefix = ([string]$Entry.operation -replace '\s+', ' ').Trim().ToLowerInvariant()
    if (-not $opPrefix) { return $false }
    if (-not $NormalizedCommand.StartsWith($opPrefix)) { return $false }

    $scope = $Entry.scope
    if ($scope -and $scope.'resource-groups') {
        if (-not $ResourceGroup) { return $false }  # scoped entry, RG unknown -> fail closed
        $rgMatched = $false
        foreach ($glob in @($scope.'resource-groups')) {
            if ($ResourceGroup -ilike $glob) { $rgMatched = $true; break }
        }
        if (-not $rgMatched) { return $false }
    }
    return $true
}

function Resolve-AllowlistDecision {
    param($Config, [string]$MatchString, [string]$ResourceGroup, [int]$Tier)

    $normalized = ($MatchString -replace '\s+', ' ').Trim().ToLowerInvariant()

    foreach ($entry in @($Config.deny)) {
        if ($entry -and (Test-EntryMatch -Entry $entry -NormalizedCommand $normalized -ResourceGroup $ResourceGroup)) {
            return @{ Decision = 'deny'; Entry = $entry }
        }
    }
    if ($Tier -lt 4) {
        foreach ($entry in @($Config.allow)) {
            if ($entry -and (Test-EntryMatch -Entry $entry -NormalizedCommand $normalized -ResourceGroup $ResourceGroup)) {
                return @{ Decision = 'allow'; Entry = $entry }
            }
        }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
$classification = $null
$matchString = $null
$resourceGroup = $null

if ($toolName -in @('Bash', 'PowerShell')) {
    $command = [string]$payload.tool_input.command
    $classification = Get-CommandClassification -Command $command
    if ($classification) {
        $matchString = $command
        $resourceGroup = Get-ResourceGroupFromCommand -Command $command
    }
} elseif ($toolName -like 'mcp__*') {
    $mcp = Get-McpClassification -ToolName $toolName -ToolInput $payload.tool_input
    if ($mcp) {
        $classification = $mcp
        $matchString = $mcp.MatchString
    }
}

if (-not $classification) { exit 0 }  # read-only / non-Azure -> no opinion

$configPath = Find-GuardrailsConfig -StartDir $sessionCwd
$configResult = Read-GuardrailsConfig -Path $configPath

if ($configResult.ParseFailed) {
    Emit-Decision -Decision 'ask' -Reason ("Mutating Azure operation detected ($($classification.What)) and the guardrails config '$configPath' could not be parsed " +
        '(install the powershell-yaml module or use .azure-guardrails.json). Failing closed: user approval required.')
}

if ($configResult.Config) {
    $resolved = Resolve-AllowlistDecision -Config $configResult.Config -MatchString $matchString `
        -ResourceGroup $resourceGroup -Tier $classification.Tier
    if ($resolved) {
        $entryOp = $resolved.Entry.operation
        $entryReason = if ($resolved.Entry.reason) { " Reason: $($resolved.Entry.reason)" } else { '' }
        if ($resolved.Decision -eq 'deny') {
            Emit-Decision -Decision 'deny' -Reason "Blocked by deny entry '$entryOp' in $configPath.$entryReason"
        }
        Emit-Decision -Decision 'allow' -Reason "Pre-approved by allow entry '$entryOp' in $configPath.$entryReason"
    }
}

if ($classification.Tier -eq 4) {
    Emit-Decision -Decision 'ask' -Reason ("Identity operation detected ($($classification.What)). " +
        'Identity operations ALWAYS require explicit user approval; the allowlist cannot exempt them. ' +
        'Present the exact command, target principal, and impact before proceeding.')
}

Emit-Decision -Decision 'ask' -Reason ("Mutating Azure operation detected ($($classification.What)) with no allowlist match. " +
    'Per azure-guardrails policy, present the exact command, target resources, and blast radius, then wait for explicit user approval.')
