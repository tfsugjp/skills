param(
    [Parameter(Mandatory)]
    [string]$MarkdownPath,
    [string[]]$RequireId = @(),
    [string[]]$RequirePr = @(),
    [string[]]$RequirePageLink = @()
)

function ConvertTo-WikiPagePath([string]$Value) {
    $path = [Uri]::UnescapeDataString(($Value -split '#', 2)[0].Split('?', 2)[0]).Replace(' ', '-')
    if ($path.EndsWith('.md')) { $path = $path.Substring(0, $path.Length - 3) }
    return '/' + $path.Trim('/')
}

$bytes = [IO.File]::ReadAllBytes($MarkdownPath)
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and
    $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    throw 'Wiki Markdown must be UTF-8 without a BOM.'
}
$markdown = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
$fenceCharacter = $null
$fenceLength = 0
$proseLines = [Collections.Generic.List[string]]::new()
$lineNumber = 0
foreach ($line in ($markdown -split '\r?\n')) {
    $lineNumber++
    $fenceMatch = [regex]::Match($line, '^\s{0,3}(\x60{3,}|~{3,})(.*)$')
    if ($fenceMatch.Success) {
        $marker = $fenceMatch.Groups[1].Value
        if ($null -eq $fenceCharacter) {
            $fenceCharacter = $marker[0]
            $fenceLength = $marker.Length
            continue
        }
        if ($marker[0] -eq $fenceCharacter -and $marker.Length -ge $fenceLength -and
            -not $fenceMatch.Groups[2].Value.Trim()) {
            $fenceCharacter = $null
            continue
        }
    }
    if ($null -ne $fenceCharacter) { continue }
    $prose = $line -replace '(?<!\x60)(\x60+).*?\1', ''
    if ($prose -match '(?i)\bAB#(?:[0-9]+|<[^>]+>|\{[^}]+\})') {
        throw "Line $lineNumber uses AB# for a work item; Azure DevOps Wiki requires # followed by the ID."
    }
    $proseLines.Add($prose)
}
if ($null -ne $fenceCharacter) { throw 'Wiki Markdown has an unclosed code fence.' }

$proseText = $proseLines -join [string][char]10
$referenceText = $proseText -replace '\]\([^)]*\)', ']'
foreach ($id in $RequireId) {
    if ($id -notmatch '^[1-9][0-9]*$') { throw 'RequireId must be a positive decimal work item ID.' }
    $reference = '(?<![A-Za-z0-9#])#' + [regex]::Escape($id) + '(?![0-9])'
    if ($referenceText -notmatch $reference) {
        throw "Wiki Markdown is missing the #$id work item reference."
    }
}

$renderedText = [regex]::Replace($proseText, '(?s)<!--.*?-->', '')
$targets = @([regex]::Matches($renderedText, '(?<!!)\[[^\]]*\]\(\s*(?:<([^>]+)>|([^)\s]+))(?:\s+"[^"]*")?\s*\)') |
    ForEach-Object { if ($_.Groups[1].Success) { $_.Groups[1].Value } else { $_.Groups[2].Value } })
foreach ($id in $RequirePr) {
    if ($id -notmatch '^[1-9][0-9]*$') { throw 'RequirePr must be a positive decimal pull request ID.' }
    $pattern = '/(?:pullrequest|pull)/' + [regex]::Escape($id) + '(?![0-9])'
    if (-not ($targets | Where-Object { $_ -match '^https?://' -and $_ -match $pattern })) {
        throw "Wiki Markdown is missing a link to pull request $id."
    }
}
$linkedPages = @($targets | Where-Object { $_.StartsWith('/') -and -not $_.StartsWith('//') } | ForEach-Object { ConvertTo-WikiPagePath $_ })
foreach ($page in $RequirePageLink) {
    if (-not $page.StartsWith('/') -or $page.StartsWith('//')) { throw 'RequirePageLink must be an absolute wiki page path such as /repo/plan/1234-slug.' }
    $expected = ConvertTo-WikiPagePath $page
    if ($linkedPages -cnotcontains $expected) {
        throw "Wiki Markdown is missing a link to the $expected page."
    }
}
