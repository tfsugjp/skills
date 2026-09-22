param(
    [Parameter(Mandatory)]
    [string]$MarkdownPath,
    [string[]]$RequireId = @()
)

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
