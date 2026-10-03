# Windows-Native Azure DevOps Execution

Use this reference whenever Azure Boards work is executed from Windows, especially on a non-English Windows installation.

## Required shell selection

1. Use Azure DevOps MCP tools when available.
2. Otherwise run PowerShell 7 (pwsh) and prefer Invoke-RestMethod.
3. Use the native az boards command from PowerShell only for ASCII-only fields when REST is impractical. For non-ASCII text, restore the REST path instead of sending it as CLI arguments.

Never use MSYS2, Git Bash, WSL, bash, or sh for Azure DevOps work on Windows. Do not use MSYS_NO_PATHCONV as a workaround; that variable addresses path conversion in a prohibited shell and does not make the shell an approved execution path.

## UTF-8 REST writes

Keep the organization URL, project, and credential in environment variables. In the PowerShell example below, `ADO_TOKEN` must be an Entra ID access token because it is sent as a Bearer token. A PAT is not a Bearer token; use an `Authorization: Basic` header with the PAT instead, following the authentication guidance in the foundation skill. Never print credentials.

PowerShell example:

    $orgUrl = $env:ADO_ORG_URL.TrimEnd('/')
    $project = [Uri]::EscapeDataString($env:ADO_PROJECT)
    $typeName = [Uri]::EscapeDataString($env:ADO_WORK_ITEM_TYPE)
    $title = $env:ADO_WORK_ITEM_TITLE
    $markdownPath = $env:ADO_WORK_ITEM_DESCRIPTION_FILE
    $markdownBytes = [IO.File]::ReadAllBytes($markdownPath)
    if ($markdownBytes.Length -ge 3 -and $markdownBytes[0] -eq 0xEF -and
        $markdownBytes[1] -eq 0xBB -and $markdownBytes[2] -eq 0xBF) {
        throw 'The Markdown source must be UTF-8 without a BOM.'
    }
    $strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
    $markdown = $strictUtf8.GetString($markdownBytes)
    if (-not $markdown.Trim()) { throw 'The work item description is empty.' }

    # Reject escaped line breaks in prose before Markdown becomes rich-text HTML.
    $fenceCharacter = $null
    $fenceLength = 0
    $proseLines = @()
    foreach ($line in ($markdown -split "`r?`n")) {
        $fenceMatch = [regex]::Match($line, '^\s{0,3}(`{3,}|~{3,})(.*)$')
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
        if ($null -eq $fenceCharacter) {
            $prose = $line -replace '(?<!`)(`+).*?\1', ''
            $proseLines += $prose
            if ($prose -match '(?<!\\)\\r\\n|(?<!\\)\\n(?=$|[\s\\#>*+|<-]|\d+[.)]\s)|(?<=[.!?。！？])\\n') {
                throw 'The description contains a literal escaped newline outside a code fence.'
            }
        }
    }
    if ($null -ne $fenceCharacter -or -not ($proseLines -join '').Trim()) {
        throw 'The description has an unclosed fence or contains only a code fence.'
    }
    $description = (ConvertFrom-Markdown -InputObject $markdown).Html
    if ($description -notmatch '<(?:h[1-6]|p|ul|ol|blockquote|pre)\b') {
        throw 'Markdown did not produce a rich-text description.'
    }

    $patch = @(
        @{ op = 'add'; path = '/fields/System.Title'; value = $title },
        @{ op = 'add'; path = '/fields/System.Description'; value = $description }
    )
    $headers = @{ Authorization = "Bearer $env:ADO_TOKEN" }
    $workItemsSegment = '$' + $typeName
    $uri = "$orgUrl/$project/_apis/wit/workitems/$workItemsSegment?api-version=7.1"

    # Keep the request body in a UTF-8 (without BOM) temporary file. This avoids
    # PowerShell/native console encoding conversions for Japanese and emoji.
    $jsonPath = [IO.Path]::GetTempFileName()
    try {
        $json = ConvertTo-Json -InputObject $patch -Depth 10 -Compress
        $utf8NoBom = [Text.UTF8Encoding]::new($false)
        [IO.File]::WriteAllText($jsonPath, $json, $utf8NoBom)
        $created = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers `
            -ContentType 'application/json-patch+json; charset=utf-8' -InFile $jsonPath
        $created.id
        $readBack = Invoke-RestMethod -Method Get -Uri "$orgUrl/$project/_apis/wit/workitems/$($created.id)?api-version=7.1" -Headers $headers
        if ($readBack.fields.'System.Title' -cne $title) { throw 'Work item readback did not preserve the title.' }
        $storedDescription = [string]$readBack.fields.'System.Description'
        $storedProse = $storedDescription -replace '(?is)<pre\b[^>]*>.*?</pre>', ''
        $storedProse = $storedProse -replace '(?is)<code\b[^>]*>.*?</code>', ''
        if ($storedProse -match '(?<!\\)\\r\\n|(?<!\\)\\n(?=$|[\s\\#>*+|<-]|\d+[.)]\s)|(?<=[.!?。！？])\\n' -or
            $storedProse -match '(?i)<(?:p|div|h[1-6])[^>]*>\s*#{1,6}\s' -or
            $storedDescription -notmatch '<(?:h[1-6]|p|ul|ol|blockquote|pre)\b') {
            throw 'Work item readback is not valid rich-text description content.'
        }
        $plainText = {
            param([string]$html)
            [Net.WebUtility]::HtmlDecode(($html -replace '<[^>]+>', ' ')) -replace '\s+', ' '
        }
        if ((& $plainText $storedDescription).Trim() -cne (& $plainText $description).Trim()) {
            throw 'Work item readback did not preserve the description text.'
        }
    }
    finally {
        Remove-Item -LiteralPath $jsonPath -Force -ErrorAction SilentlyContinue
    }

Use the same preflight, temporary-file pattern, and readback checks for JSON Patch updates. Always use `ConvertTo-Json -InputObject` so a top-level patch array remains an array. Keep the file cleanup in `finally`. The source Markdown file is user content and is not deleted by this request-file cleanup. Azure Boards may normalize HTML tags, so compare decoded text and verify the rich-text structure rather than requiring byte-for-byte HTML equality. Apply the same description checks when MCP tools create or update a work item.

## Native az boards fallback

Use az boards directly from PowerShell only when all submitted fields are ASCII, and retrieve only an ASCII ID when possible:

    if ($env:ADO_WORK_ITEM_TYPE -match '[^\x00-\x7F]' -or
        $env:ADO_WORK_ITEM_TITLE -match '[^\x00-\x7F]' -or
        $env:ADO_WORK_ITEM_DESCRIPTION -match '[^\x00-\x7F]') {
        throw 'Use the UTF-8 REST file flow for non-ASCII work item text.'
    }
    $createdId = az boards work-item create --type $env:ADO_WORK_ITEM_TYPE --title $env:ADO_WORK_ITEM_TITLE --description $env:ADO_WORK_ITEM_DESCRIPTION --query id -o tsv

Verify fields with Invoke-RestMethod rather than trusting captured human-readable az output. Azure CLI's MSI launcher uses Python isolated mode, which ignores PYTHONIOENCODING; redirected output can therefore use the Windows ANSI code page. chcp 65001 changes the console code page and does not repair redirected output. Neither behavior means that the server received corrupted data.

If az emits an encoding warning, preserve the original title and description, read the Work Item through REST, and compare the returned fields. Never translate content to English as an encoding workaround.

## Linux/macOS comparison

The following pattern is for Linux/macOS shells only. It must not be copied into a Windows MSYS2 or Git Bash session.

    base_uri="$ADO_ORG_URL/$ADO_PROJECT"
    json_file="$(mktemp)"
    trap 'rm -f "$json_file"' EXIT
    description_file="$ADO_WORK_ITEM_DESCRIPTION_FILE" # UTF-8 HTML source, not raw Markdown
    python3 - "$description_file" <<'PY' || exit 1
    from html.parser import HTMLParser
    from pathlib import Path
    import re
    import sys

    class DescriptionParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.code_depth = 0
            self.has_rich_text = False
            self.prose = []

        def handle_starttag(self, tag, attrs):
            if tag in ("pre", "code"):
                self.code_depth += 1
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "blockquote", "pre"):
                self.has_rich_text = True
            if tag in ("br", "p", "div", "h1", "h2", "h3", "h4", "h5", "h6"):
                self.prose.append("\n")

        def handle_endtag(self, tag):
            if tag in ("pre", "code"):
                self.code_depth -= 1

        def handle_data(self, data):
            if self.code_depth == 0:
                self.prose.append(data)

    parser = DescriptionParser()
    parser.feed(Path(sys.argv[1]).read_text(encoding="utf-8"))
    prose = "".join(parser.prose)
    if (not parser.has_rich_text or parser.code_depth != 0 or
            re.search(r"(?<!\\)\\r\\n|(?<!\\)\\n(?=$|[\s\\#>*+|<-]|\d+[.)]\s)|(?<=[.!?。！？])\\n", prose) or
            re.search(r"(?m)^\s*#{1,6}\s", prose)):
        raise SystemExit("Description must contain HTML rich text and no escaped newlines or Markdown headings in prose.")
    PY
    jq -n --arg title "$ADO_WORK_ITEM_TITLE" --rawfile description "$description_file" \
      '[{"op":"add","path":"/fields/System.Title","value":$title},{"op":"add","path":"/fields/System.Description","value":$description}]' \
      >"$json_file"
    curl --fail-with-body -sS -X POST \
      -H "Authorization: Bearer $ADO_TOKEN" \
      -H 'Content-Type: application/json-patch+json; charset=utf-8' \
      --data-binary "@$json_file" \
      "$base_uri/_apis/wit/workitems/\$$ADO_WORK_ITEM_TYPE?api-version=7.1"

When a Windows session cannot provide PowerShell 7, stop and request that the user run the operation from a native PowerShell environment. Do not silently switch to MSYS2.
