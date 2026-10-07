# Windows-Native Azure DevOps Execution

Use this reference whenever Azure Boards work is executed from Windows, especially on a non-English Windows installation.

## Required shell selection

1. Use Azure DevOps MCP tools when available.
2. Otherwise run PowerShell 7 (pwsh) and prefer Invoke-RestMethod.
3. Use the native az boards command from PowerShell only for ASCII-only fields when REST is impractical. For non-ASCII text, restore the REST path instead of sending it as CLI arguments.

Never use MSYS2, Git Bash, WSL, bash, or sh for Azure DevOps work on Windows. Do not use MSYS_NO_PATHCONV as a workaround; that variable addresses path conversion in a prohibited shell and does not make the shell an approved execution path.

Before running az or other native commands with JSON, `--query`, or pipes, apply the `windows-shell-safety` skill (plugin `windows-shell-safety`) and lint the command with its `Test-NativeCommand.ps1`.

## UTF-8 REST writes

Keep the organization URL, project, and credential in environment variables. In the PowerShell example below, `ADO_TOKEN` must be an Entra ID access token because it is sent as a Bearer token. A PAT is not a Bearer token; use an `Authorization: Basic` header with the PAT instead, following the authentication guidance in the foundation skill. Never print credentials.

The helper functions below implement the Markdown-first write with the HTML fallback described in the Boards skill. Define them once per session:

    $orgUrl = $env:ADO_ORG_URL.TrimEnd('/')
    $project = [Uri]::EscapeDataString($env:ADO_PROJECT)
    $apiBase = "$orgUrl/$project/_apis/wit"
    $headers = @{ Authorization = "Bearer $env:ADO_TOKEN" }
    $bugSections = 'Repro steps', 'Expected vs actual', 'Root cause', 'Fix approach'

    function Get-BodyField([string]$WorkItemType) {
        # Bug forms show Repro Steps as the body; other types show Description.
        if ($WorkItemType -eq 'Bug') { 'Microsoft.VSTS.TCM.ReproSteps' } else { 'System.Description' }
    }

    function Read-MarkdownSource([string]$Path) {
        $bytes = [IO.File]::ReadAllBytes($Path)
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            throw 'The Markdown source must be UTF-8 without a BOM.'
        }
        [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
    }

    function Assert-MarkdownSource([string]$Markdown) {
        if (-not $Markdown.Trim()) { throw 'The work item body is empty.' }
        # Reject escaped line breaks in prose and a body that is only a code fence.
        $fenceCharacter = $null
        $fenceLength = 0
        $proseLines = @()
        foreach ($line in ($Markdown -split "`r?`n")) {
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
                    throw 'The body contains a literal escaped newline outside a code fence.'
                }
            }
        }
        if ($null -ne $fenceCharacter -or -not ($proseLines -join '').Trim()) {
            throw 'The body has an unclosed fence or contains only a code fence.'
        }
    }

    function Assert-BugSections([string]$Markdown) {
        $previousIndex = -1
        foreach ($heading in $bugSections) {
            $pattern = "(?ms)^##[ \t]+$([regex]::Escape($heading))[ \t]*\r?\n(.*?)(?=^##[ \t]|\z)"
            $section = [regex]::Match($Markdown, $pattern)
            if (-not $section.Success -or -not $section.Groups[1].Value.Trim()) {
                throw "The Bug body has no '$heading' section with content."
            }
            if ($section.Index -le $previousIndex) {
                throw "The Bug body sections must be in this order: $($bugSections -join ', ')."
            }
            $previousIndex = $section.Index
        }
    }

    # Applies $Prose to text outside code and $Code to code spans and fenced code lines.
    function Convert-MarkdownText([string]$Markdown, [scriptblock]$Prose, [scriptblock]$Code) {
        $fence = $null
        $lines = foreach ($line in $Markdown.Split("`n")) {
            $fenceMatch = [regex]::Match($line, '^ {0,3}(`{3,}|~{3,})')
            $marker = $fenceMatch.Groups[1].Value
            if ($fenceMatch.Success -and ($null -eq $fence -or
                    ($marker[0] -eq $fence[0] -and $marker.Length -ge $fence.Length))) {
                $fence = if ($null -eq $fence) { $marker } else { $null }
                $line
            }
            elseif ($null -ne $fence) { & $Code $line }
            else {
                [regex]::Replace($line, '(`+)(.+?)(?<!`)\1(?!`)|[^`]+|`+', {
                        param($match)
                        if ($match.Groups[2].Success) { & $Code $match.Value } else { & $Prose $match.Value }
                    })
            }
        }
        $lines -join "`n"
    }

    function ConvertTo-MarkdownFieldValue([string]$Markdown) {
        # The server strips anything shaped like an HTML tag, and the Markdown preview decodes
        # the stored value once before rendering. Encode < twice in prose so it renders as a
        # literal <, and once inside code, which shows entities as text. Leave > and & as they are.
        Convert-MarkdownText $Markdown { param($text) $text.Replace('<', '&amp;lt;') } { param($text) $text.Replace('<', '&lt;') }
    }

    function ConvertTo-UpperPercentEncoding([string]$Value) {
        # Azure Boards lowercases percent-encodings (%2F -> %2f) in Markdown links.
        [regex]::Replace($Value, '%[0-9a-fA-F]{2}', { param($match) $match.Value.ToUpperInvariant() })
    }

    function ConvertFrom-MarkdownFieldValue([string]$Value) {
        # Undo the server escaping (&amp;, &gt;, and &#NNNN; for emoji), then the prose encoding.
        Convert-MarkdownText ([Net.WebUtility]::HtmlDecode($Value)) { param($text) $text.Replace('&lt;', '<') } { param($text) $text }
    }

    function ConvertTo-HtmlFieldValue([string]$Markdown) {
        $html = (ConvertFrom-Markdown -InputObject $Markdown).Html
        if ($html -notmatch '<(?:h[1-6]|p|ul|ol|blockquote|pre)\b') {
            throw 'Markdown did not produce a rich-text body.'
        }
        $html
    }

    function Assert-HtmlBody([string]$Stored, [string]$Expected) {
        $storedProse = $Stored -replace '(?is)<pre\b[^>]*>.*?</pre>', ''
        $storedProse = $storedProse -replace '(?is)<code\b[^>]*>.*?</code>', ''
        if ($storedProse -match '(?<!\\)\\r\\n|(?<!\\)\\n(?=$|[\s\\#>*+|<-]|\d+[.)]\s)|(?<=[.!?。！？])\\n' -or
            $storedProse -match '(?i)<(?:p|div|h[1-6])[^>]*>\s*#{1,6}\s' -or
            $Stored -notmatch '<(?:h[1-6]|p|ul|ol|blockquote|pre)\b') {
            throw 'Work item readback is not valid rich-text body content.'
        }
        $plainText = {
            param([string]$html)
            [Net.WebUtility]::HtmlDecode(($html -replace '<[^>]+>', ' ')) -replace '\s+', ' '
        }
        if ((& $plainText $Stored).Trim() -cne (& $plainText $Expected).Trim()) {
            throw 'Work item readback did not preserve the body text.'
        }
    }

    function Invoke-WorkItemPatch([string]$Method, [string]$Uri, [object[]]$Patch) {
        # Keep the request body in a UTF-8 (without BOM) temporary file. This avoids
        # PowerShell/native console encoding conversions for Japanese and emoji.
        $jsonPath = [IO.Path]::GetTempFileName()
        try {
            $json = ConvertTo-Json -InputObject $Patch -Depth 10 -Compress
            [IO.File]::WriteAllText($jsonPath, $json, [Text.UTF8Encoding]::new($false))
            Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers `
                -ContentType 'application/json-patch+json; charset=utf-8' -InFile $jsonPath
        }
        finally {
            Remove-Item -LiteralPath $jsonPath -Force -ErrorAction SilentlyContinue
        }
    }

    function Get-WorkItem([int]$Id) {
        Invoke-RestMethod -Method Get -Headers $headers `
            -Uri "$apiBase/workitems/$($Id)?`$expand=relations&api-version=7.1"
    }

    function Write-WorkItemBody {
        # Creates the work item when -Id is 0; otherwise rewrites the body of -Id.
        param(
            [int]$Id,
            [Parameter(Mandatory)][string]$WorkItemType,
            [string]$Title,
            [Parameter(Mandatory)][string]$Markdown,
            [object[]]$ExtraOperations = @()
        )
        Assert-MarkdownSource $Markdown
        if ($WorkItemType -eq 'Bug') { Assert-BugSections $Markdown }
        $field = Get-BodyField $WorkItemType
        $titleOperations = @()
        if ($Title) { $titleOperations += @{ op = 'add'; path = '/fields/System.Title'; value = $Title } }
        if ($Id) {
            $method = 'Patch'
            $uri = "$apiBase/workitems/$($Id)?api-version=7.1"
        }
        else {
            $method = 'Post'
            $uri = "$apiBase/workitems/`$$([Uri]::EscapeDataString($WorkItemType))?api-version=7.1"
        }
        $htmlOperation = { @{ op = 'add'; path = "/fields/$field"; value = (ConvertTo-HtmlFieldValue $Markdown) } }

        # 1. Markdown: the field value and the format switch go in the same patch.
        $markdownPatch = $titleOperations + @(
            @{ op = 'add'; path = "/fields/$field"; value = (ConvertTo-MarkdownFieldValue $Markdown) },
            @{ op = 'add'; path = "/multilineFieldsFormat/$field"; value = 'Markdown' }
        ) + $ExtraOperations
        $sentMarkdown = $true
        try {
            $written = Invoke-WorkItemPatch $method $uri $markdownPatch
        }
        catch {
            # 400 means the server rejected the format operation (for example Azure DevOps
            # Server); the patch is atomic, so resend it with an HTML value instead.
            if ([int]$_.Exception.Response.StatusCode -ne 400) { throw }
            $sentMarkdown = $false
            $written = Invoke-WorkItemPatch $method $uri ($titleOperations + @(& $htmlOperation) + $ExtraOperations)
        }

        # 2. Read back and verify the stored format.
        $item = Get-WorkItem $written.id
        if ($Title -and $item.fields.'System.Title' -cne $Title) {
            throw "Work item $($written.id) readback did not preserve the title."
        }
        $stored = [string]$item.fields.$field
        if ([string]$item.multilineFieldsFormat.$field -eq 'Markdown') {
            $normalize = {
                param([string]$value)
                # The server escapes & and >, and stores emoji as &#NNNN;: compare decoded text.
                (ConvertTo-UpperPercentEncoding ([Net.WebUtility]::HtmlDecode($value))).Replace("`r`n", "`n").Trim()
            }
            if ((& $normalize $stored) -cne (& $normalize (ConvertTo-MarkdownFieldValue $Markdown))) {
                throw "Work item $($written.id) readback did not preserve the Markdown body."
            }
            return $item
        }

        # 3. HTML fallback: never leave raw Markdown in an HTML-format field.
        $html = (& $htmlOperation).value
        if ($sentMarkdown) {
            $null = Invoke-WorkItemPatch 'Patch' "$apiBase/workitems/$($written.id)?api-version=7.1" @(& $htmlOperation)
            $item = Get-WorkItem $written.id
            $stored = [string]$item.fields.$field
        }
        Assert-HtmlBody $stored $html
        $item
    }

Create a work item from a UTF-8 Markdown source file. For a Bug, the file must contain the `Repro steps`, `Expected vs actual`, `Root cause`, and `Fix approach` sections; `Write-WorkItemBody` rejects the body otherwise:

    $type = $env:ADO_WORK_ITEM_TYPE
    $markdown = Read-MarkdownSource $env:ADO_WORK_ITEM_BODY_FILE
    $created = Write-WorkItemBody -WorkItemType $type -Title $env:ADO_WORK_ITEM_TITLE -Markdown $markdown
    $created.id
    $created.multilineFieldsFormat

Rewrite the body of an existing item (for example after the fix approach of a Bug is approved) with the same function and `-Id`. The function switches an HTML field to Markdown and rewrites it as a whole:

    $updated = Write-WorkItemBody -Id $env:ADO_WORK_ITEM_ID -WorkItemType 'Bug' -Markdown $markdown

Use `ConvertTo-Json -InputObject` for every patch so a top-level patch array remains an array, and keep the file cleanup in `finally`. The source Markdown file is user content and is not deleted by this request-file cleanup. Apply the same body checks when MCP tools create or update a work item.

### Wiki back-link

After azure-devops-wiki has registered and read back the page, pass its `remoteUrl` and path. The function replaces or appends the `## Wiki` section, adds the `Hyperlink` relation only when it is missing, and verifies both:

    function Set-WikiSection([string]$Markdown, [string[]]$Lines) {
        $section = "## Wiki`n`n" + ($Lines -join "`n") + "`n"
        $pattern = '(?ms)^##[ \t]+Wiki[ \t]*\r?\n.*?(?=^##[ \t]|\z)'
        if ([regex]::IsMatch($Markdown, $pattern)) {
            return [regex]::Replace($Markdown, $pattern, { param($match) $section + "`n" }).TrimEnd() + "`n"
        }
        $Markdown.TrimEnd() + "`n`n" + $section
    }

    function Add-WikiBackLink([int]$Id, [string]$PagePath, [string]$PageUrl, [string]$MarkdownPath) {
        $PageUrl = ConvertTo-UpperPercentEncoding $PageUrl
        $item = Get-WorkItem $Id
        $type = $item.fields.'System.WorkItemType'
        $field = Get-BodyField $type
        if ([string]$item.multilineFieldsFormat.$field -eq 'Markdown') {
            $markdown = ConvertFrom-MarkdownFieldValue ([string]$item.fields.$field)
        }
        else {
            # An HTML body cannot be edited as Markdown; start from the Markdown source file.
            $markdown = Read-MarkdownSource $MarkdownPath
        }
        $lines = @("- [$PagePath]($PageUrl)")
        $existing = [regex]::Match($markdown, '(?ms)^##[ \t]+Wiki[ \t]*\r?\n(.*?)(?=^##[ \t]|\z)')
        if ($existing.Success) {
            $lines = @($existing.Groups[1].Value -split "`r?`n" |
                Where-Object { $_.Trim() -and -not (ConvertTo-UpperPercentEncoding $_).Contains("]($PageUrl)") }) + $lines
        }
        $markdown = Set-WikiSection $markdown $lines

        $isLinked = {
            param($relation)
            $relation.rel -eq 'Hyperlink' -and (ConvertTo-UpperPercentEncoding $relation.url) -ceq $PageUrl
        }
        $relationOperations = @()
        if (-not @($item.relations | Where-Object { & $isLinked $_ })) {
            $relationOperations += @{ op = 'add'; path = '/relations/-'; value = @{
                    rel = 'Hyperlink'; url = $PageUrl; attributes = @{ comment = "Wiki: $PagePath" } } }
        }
        $updated = Write-WorkItemBody -Id $Id -WorkItemType $type -Markdown $markdown -ExtraOperations $relationOperations
        if (@($updated.relations | Where-Object { & $isLinked $_ }).Count -ne 1) {
            throw "Work item $Id does not have exactly one Hyperlink to the Wiki page."
        }
        $updated
    }

    $linked = Add-WikiBackLink -Id $env:ADO_WORK_ITEM_ID -PagePath $env:ADO_WIKI_PAGE_PATH `
        -PageUrl $env:ADO_WIKI_PAGE_URL -MarkdownPath $env:ADO_WORK_ITEM_BODY_FILE

The page URL is the `remoteUrl` returned by the Wiki page API (`GET .../wiki/wikis/{wiki}/pages?path=<page path>&api-version=7.1`). For a Bug whose stored body lacks the analysis sections, `Write-WorkItemBody` rejects the back-link until the Root cause and Fix approach are written.

## Native az boards fallback

Use az boards directly from PowerShell only when all submitted fields are ASCII, and retrieve only an ASCII ID when possible. Create the item without a body, then write the body with `Write-WorkItemBody`:

    if ($env:ADO_WORK_ITEM_TYPE -match '[^\x00-\x7F]' -or
        $env:ADO_WORK_ITEM_TITLE -match '[^\x00-\x7F]') {
        throw 'Use the UTF-8 REST file flow for non-ASCII work item text.'
    }
    $createdId = az boards work-item create --type $env:ADO_WORK_ITEM_TYPE --title $env:ADO_WORK_ITEM_TITLE --query id -o tsv
    $markdown = Read-MarkdownSource $env:ADO_WORK_ITEM_BODY_FILE
    $created = Write-WorkItemBody -Id $createdId -WorkItemType $env:ADO_WORK_ITEM_TYPE -Markdown $markdown

Verify fields with Invoke-RestMethod rather than trusting captured human-readable az output. Azure CLI's MSI launcher uses Python isolated mode, which ignores PYTHONIOENCODING; redirected output can therefore use the Windows ANSI code page. chcp 65001 changes the console code page and does not repair redirected output. Neither behavior means that the server received corrupted data.

az boards writes `--description` to `System.Description` as HTML and cannot switch a field to Markdown, so do not pass a body to it. This also keeps a Bug's analysis out of the Description field, which the Bug form does not show.

If az emits an encoding warning, preserve the original title and body, read the Work Item through REST, and compare the returned fields. Never translate content to English as an encoding workaround.

## Linux/macOS comparison

The following patterns are for Linux/macOS shells only. They must not be copied into a Windows MSYS2 or Git Bash session. They need `curl`, `jq`, and `python3`.

`ADO_WORK_ITEM_BODY_FILE` is the UTF-8 Markdown source. `ADO_MARKDOWN_TO_HTML` is a Markdown renderer command that reads Markdown on standard input and writes HTML to standard output (for example `pandoc -f gfm -t html`); the HTML fallback runs it on the current source every time, so the HTML never lags behind the source. Define the helpers once per shell:

    base_uri="$ADO_ORG_URL/$ADO_PROJECT/_apis/wit"
    body_file="$ADO_WORK_ITEM_BODY_FILE"
    type_enc=$(jq -rn --arg t "$ADO_WORK_ITEM_TYPE" '$t | @uri')
    field=System.Description
    [ "$ADO_WORK_ITEM_TYPE" = Bug ] && field=Microsoft.VSTS.TCM.ReproSteps
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT
    html_file="$tmp_dir/body.html"

    check_bug_sections() {
      python3 - "$body_file" <<'PY'
    import re, sys
    from pathlib import Path
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    headings = ("Repro steps", "Expected vs actual", "Root cause", "Fix approach")
    previous = -1
    for heading in headings:
        match = re.search(r"(?ms)^##[ \t]+" + re.escape(heading) + r"[ \t]*\r?\n(.*?)(?=^##[ \t]|\Z)", text)
        if not match or not match.group(1).strip():
            raise SystemExit(f"The Bug body has no '{heading}' section with content.")
        if match.start() <= previous:
            raise SystemExit("The Bug body sections must be in this order: " + ", ".join(headings) + ".")
        previous = match.start()
    PY
    }

    # $1: HTML file to check; $2 (optional): HTML whose text $1 must match;
    # $3 (optional): Markdown source whose headings must appear in $1.
    check_html() {
      python3 - "$@" <<'PY'
    from html import unescape
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
        raise SystemExit("The body must contain HTML rich text and no escaped newlines or Markdown headings in prose.")

    def plain_text(html):
        return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()

    stored = plain_text(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if len(sys.argv) > 2 and stored != plain_text(Path(sys.argv[2]).read_text(encoding="utf-8")):
        raise SystemExit("The stored body text differs from the submitted HTML.")
    if len(sys.argv) > 3:
        markdown = Path(sys.argv[3]).read_text(encoding="utf-8")
        markdown = re.sub(r"(?ms)^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1[ \t]*$", "", markdown)
        for heading in re.findall(r"(?m)^ {0,3}#{1,6}[ \t]+(.+?)[ \t#]*$", markdown):
            heading = re.sub(r"\[([^]]*)\]\([^)]*\)", r"\1", heading)
            heading = re.sub(r"\s+", " ", re.sub(r"[`*_]", "", heading)).strip()
            if heading not in re.sub(r"[`*_]", "", stored):
                raise SystemExit(f"The HTML file is stale: heading '{heading}' from the Markdown source is missing.")
    PY
    }

    # $1: encode | decode, $2: input file, $3: output file. encode turns a Markdown source into
    # the field value: the server strips anything shaped like an HTML tag and the Markdown
    # preview decodes the stored value once, so < is encoded twice in prose and once in code.
    # decode turns a stored Markdown value back into the source.
    markdown_codec() {
      python3 - "$@" <<'PY'
    import html, re, sys
    mode, source, target = sys.argv[1:4]
    text = open(source, encoding="utf-8", newline="").read()
    if mode == "decode":
        text = html.unescape(text)
        prose, code = (lambda s: s.replace("&lt;", "<")), (lambda s: s)
    else:
        prose, code = (lambda s: s.replace("<", "&amp;lt;")), (lambda s: s.replace("<", "&lt;"))
    spans = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)|[^`]+|`+")
    fence, lines = None, []
    for line in text.split("\n"):
        marker = re.match(r" {0,3}(`{3,}|~{3,})", line)
        if marker and (fence is None or (marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence))):
            fence = marker.group(1) if fence is None else None
            lines.append(line)
        elif fence is not None:
            lines.append(code(line))
        else:
            lines.append(spans.sub(lambda m: code(m.group(0)) if m.group(2) else prose(m.group(0)), line))
    open(target, "w", encoding="utf-8", newline="").write("\n".join(lines))
    PY
    }

    render_html() { # renders the current Markdown source into $html_file for the HTML fallback
      sh -c "$ADO_MARKDOWN_TO_HTML" <"$body_file" >"$html_file" || return 1
      check_html "$html_file" "$html_file" "$body_file"
    }

    send_patch() { # $1: method, $2: URI, $3: patch file; prints the HTTP status
      curl -sS -o "$tmp_dir/response.json" -w '%{http_code}' -X "$1" \
        -H "Authorization: Bearer $ADO_TOKEN" \
        -H 'Content-Type: application/json-patch+json; charset=utf-8' \
        --data-binary "@$3" "$2"
    }

    read_back() { # $1: work item ID; writes $tmp_dir/item.json
      curl --fail-with-body -sS -H "Authorization: Bearer $ADO_TOKEN" \
        "$base_uri/workitems/$1?\$expand=relations&api-version=7.1" >"$tmp_dir/item.json"
    }

    # $1: work item ID, or empty to create; $2: extra JSON Patch operations (JSON array).
    # Prints the work item ID; $tmp_dir/item.json holds the verified read-back.
    write_body() {
      local id="$1" extra="${2:-[]}" method uri title_ops sent_markdown=1 status
      [ "$ADO_WORK_ITEM_TYPE" = Bug ] && { check_bug_sections || return 1; }
      if [ -n "$id" ]; then
        method=PATCH; uri="$base_uri/workitems/$id?api-version=7.1"; title_ops='[]'
      else
        method=POST; uri="$base_uri/workitems/\$$type_enc?api-version=7.1"
        title_ops=$(jq -n --arg t "$ADO_WORK_ITEM_TITLE" '[{"op":"add","path":"/fields/System.Title","value":$t}]')
      fi
      markdown_codec encode "$body_file" "$tmp_dir/body.value" || return 1
      jq -n --argjson title "$title_ops" --argjson extra "$extra" --arg field "$field" --rawfile body "$tmp_dir/body.value" \
        '$title + [{"op":"add","path":("/fields/" + $field),"value":$body},
                   {"op":"add","path":("/multilineFieldsFormat/" + $field),"value":"Markdown"}] + $extra' \
        >"$tmp_dir/patch.json"
      status=$(send_patch "$method" "$uri" "$tmp_dir/patch.json")
      if [ "$status" = 400 ]; then
        # The server rejected the format operation and wrote nothing; resend with HTML.
        sent_markdown=0
        render_html || return 1
        jq -n --argjson title "$title_ops" --argjson extra "$extra" --arg field "$field" --rawfile html "$html_file" \
          '$title + [{"op":"add","path":("/fields/" + $field),"value":$html}] + $extra' >"$tmp_dir/patch.json"
        status=$(send_patch "$method" "$uri" "$tmp_dir/patch.json")
      fi
      [ "$status" = 200 ] || { cat "$tmp_dir/response.json" >&2; return 1; }
      id=$(jq -r .id "$tmp_dir/response.json")
      read_back "$id" || return 1
      if jq -e --arg field "$field" '((.multilineFieldsFormat[$field] // "") | ascii_downcase) == "markdown"' \
          "$tmp_dir/item.json" >/dev/null; then
        python3 - "$tmp_dir/item.json" "$field" "$tmp_dir/body.value" <<'PY' || return 1
    import html, json, re, sys
    from pathlib import Path
    item = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    def norm(value):
        # The server escapes & and >, stores emoji as &#NNNN;, and lowercases
        # percent-encodings in links (%2F -> %2f): compare decoded text.
        value = re.sub(r"%[0-9a-fA-F]{2}", lambda match: match.group(0).upper(), html.unescape(value))
        return value.replace("\r\n", "\n").strip()
    sent = Path(sys.argv[3]).read_text(encoding="utf-8")
    if norm(item["fields"][sys.argv[2]]) != norm(sent):
        raise SystemExit("The stored Markdown body differs from the submitted body.")
    PY
      else
        if [ "$sent_markdown" = 1 ]; then
          # The field stayed HTML: never leave raw Markdown in it.
          render_html || return 1
          jq -n --arg field "$field" --rawfile html "$html_file" \
            '[{"op":"add","path":("/fields/" + $field),"value":$html}]' >"$tmp_dir/patch.json"
          [ "$(send_patch PATCH "$base_uri/workitems/$id?api-version=7.1" "$tmp_dir/patch.json")" = 200 ] ||
            { cat "$tmp_dir/response.json" >&2; return 1; }
          read_back "$id" || return 1
        fi
        jq -r --arg field "$field" '.fields[$field]' "$tmp_dir/item.json" >"$tmp_dir/stored.html"
        check_html "$tmp_dir/stored.html" "$html_file" || return 1
      fi
      jq -e --arg t "$ADO_WORK_ITEM_TITLE" '$t == "" or .fields["System.Title"] == $t' "$tmp_dir/item.json" >/dev/null ||
        { echo "Work item $id did not preserve the title." >&2; return 1; }
      echo "$id"
    }

Create a work item, or rewrite the body of an existing one:

    id=$(write_body "") || exit 1
    write_body "$ADO_WORK_ITEM_ID" >/dev/null || exit 1

Wiki back-link. The function rewrites the `## Wiki` section in the Markdown source (taking the stored body when it is already Markdown), adds the `Hyperlink` relation only when it is missing, and verifies both. When the field is still HTML, the fallback in `write_body` renders the updated source:

    add_wiki_back_link() { # $1: work item ID, $2: page path, $3: page remoteUrl
      read_back "$1" || return 1
      if jq -e --arg field "$field" '((.multilineFieldsFormat[$field] // "") | ascii_downcase) == "markdown"' \
          "$tmp_dir/item.json" >/dev/null; then
        # Start from the stored body; an HTML body is edited through the Markdown source file.
        jq -j --arg field "$field" '.fields[$field]' "$tmp_dir/item.json" >"$tmp_dir/stored.value"
        markdown_codec decode "$tmp_dir/stored.value" "$body_file" || return 1
      fi
      python3 - "$body_file" "$2" "$3" <<'PY' || return 1
    import re, sys
    from pathlib import Path
    body_path, page_path, page_url = sys.argv[1:4]
    upper_pct = lambda value: re.sub(r"%[0-9a-fA-F]{2}", lambda match: match.group(0).upper(), value)
    page_url = upper_pct(page_url)
    text = Path(body_path).read_text(encoding="utf-8")
    pattern = re.compile(r"(?ms)^##[ \t]+Wiki[ \t]*\r?\n(.*?)(?=^##[ \t]|\Z)")
    match = pattern.search(text)
    lines = [line for line in (match.group(1).splitlines() if match else [])
             if line.strip() and f"]({page_url})" not in upper_pct(line)]
    lines.append(f"- [{page_path}]({page_url})")
    section = "## Wiki\n\n" + "\n".join(lines) + "\n"
    if match:
        text = pattern.sub(lambda _: section + "\n", text).rstrip() + "\n"
    else:
        text = text.rstrip() + "\n\n" + section
    Path(body_path).write_text(text, encoding="utf-8")
    PY
      local count relation='[]'
      count=$(jq --arg url "$3" '[.relations[]? | select(.rel == "Hyperlink" and (.url | ascii_downcase) == ($url | ascii_downcase))] | length' "$tmp_dir/item.json")
      if [ "$count" = 0 ]; then
        relation=$(jq -n --arg url "$3" --arg path "$2" \
          '[{"op":"add","path":"/relations/-","value":{"rel":"Hyperlink","url":$url,"attributes":{"comment":("Wiki: " + $path)}}}]')
      fi
      write_body "$1" "$relation" >/dev/null || return 1
      count=$(jq --arg url "$3" '[.relations[]? | select(.rel == "Hyperlink" and (.url | ascii_downcase) == ($url | ascii_downcase))] | length' "$tmp_dir/item.json")
      [ "$count" = 1 ] || { echo "Work item $1 does not have exactly one Hyperlink to the Wiki page." >&2; return 1; }
    }

    add_wiki_back_link "$ADO_WORK_ITEM_ID" "$ADO_WIKI_PAGE_PATH" "$ADO_WIKI_PAGE_URL" || exit 1

When a Windows session cannot provide PowerShell 7, stop and request that the user run the operation from a native PowerShell environment. Do not silently switch to MSYS2.
