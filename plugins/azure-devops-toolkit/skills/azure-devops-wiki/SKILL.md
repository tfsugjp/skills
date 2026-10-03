---
name: azure-devops-wiki
description: 'Work with Azure DevOps wikis: read, search, create, and update wiki pages, and publish generated content such as release notes or sprint reports. Use when the user asks to read or write Azure DevOps wiki pages. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (wiki toolset).'
---

# Azure DevOps Wiki

Read, search, and publish wiki content. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Reading or searching wiki pages (project wiki or code wiki)
- Creating or updating pages (`wiki_upsert_page` handles both)
- Publishing generated documents: release notes, sprint reports, runbooks, meeting notes

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `wiki` | `list_wikis`, `get_wiki`, `list_pages`, `get_page` | Discover wikis and read pages (content + metadata) |
| `search_wiki` | — | Full-text wiki search |
| `wiki_upsert_page` | — | Create a page or update it if it exists |

## Work item links in Wiki Markdown

Write a Wiki work item reference as `#1234` for work item 1234. Never use `AB#1234` in a Wiki page: that notation is for linking GitHub content to Azure Boards and does not produce the Wiki work item link. Keep the Azure Repos and GitHub conventions in their own skills; this rule applies to Azure DevOps Wiki content only.

Before every Wiki create or update, validate the exact UTF-8 Markdown file that will be submitted. Use [scripts/validate_work_item_links.py](scripts/validate_work_item_links.py) on Linux/macOS or [scripts/Assert-WikiWorkItemLinks.ps1](scripts/Assert-WikiWorkItemLinks.ps1) in PowerShell 7. Both reject `AB#<id>` in prose while allowing code examples, and `--require-id` / `-RequireId` checks each Work Item ID that the page must link. If a check fails, fix the Markdown and validate again. Apply the same preflight when using `wiki_upsert_page`: prepare a file first, validate it, then submit its exact content.

Read the saved page back after writing. Re-run the validator on the returned content and require the expected `#<id>` references; compare the saved Markdown with the source after normalizing line endings. Do not report the Work Item Wiki registration complete if the required reference is missing or the stored content contains `AB#<id>` in prose.

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis/wiki`. The "List wikis" operation sits directly under this base (`/wikis`); page operations are scoped to a specific wiki (`/wikis/{wikiIdentifier}/pages`). Verify with `microsoft_docs_search("Azure DevOps wiki pages REST API")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| List wikis | `GET /wikis` | `7.1` |
| Get page (+content) | `GET /wikis/{wiki}/pages?path={path}&includeContent=true` | `7.1` |
| Create page | `PUT /wikis/{wiki}/pages?path={path}` (no `If-Match`) | `7.1` |
| Update page | `PUT /wikis/{wiki}/pages?path={path}` with `If-Match: {ETag}` | `7.1` |
| Delete page | `DELETE /wikis/{wiki}/pages?path={path}` | `7.1` |

Updates are **ETag-guarded**: first GET the page and capture the `ETag` response header, then PUT with `If-Match`. A 412 response means someone edited the page in between — re-read and merge, don't blind-overwrite.

```bash
WIKI="https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki}"
page_file="$(mktemp)"
markdown_file="$(mktemp)"
headers_file="$(mktemp)"
saved_file="$(mktemp)"
trap 'rm -f "$page_file" "$markdown_file" "$headers_file" "$saved_file"' EXIT

cat >"$markdown_file" <<'MARKDOWN'
# June 2026 Release

日本語のリリースノートです。

関連 Work Item: #1234
MARKDOWN
python3 "<skill-dir>/scripts/validate_work_item_links.py" "$markdown_file" --require-id 1234 || exit 1
jq -Rs '{content: .}' "$markdown_file" >"$page_file"

# Read and capture ETag from response headers
curl --fail-with-body -sS -D "$headers_file" -o /dev/null -H "Authorization: Bearer ${ADO_TOKEN}" \
  "${WIKI}/pages?path=/Releases/2026-06&includeContent=true&api-version=7.1"
ETAG=$(awk 'tolower($1)=="etag:" {print $2}' "$headers_file" | tr -d '\r')
test -n "$ETAG" || { echo 'Missing Wiki ETag' >&2; exit 1; }

# Update with concurrency guard
curl --fail-with-body -sS -X PUT -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json; charset=utf-8" -H "If-Match: ${ETAG}" \
  "${WIKI}/pages?path=/Releases/2026-06&api-version=7.1" \
  --data-binary "@$page_file"

curl --fail-with-body -sS -H "Authorization: Bearer ${ADO_TOKEN}" \
  "${WIKI}/pages?path=/Releases/2026-06&includeContent=true&api-version=7.1" \
  | jq -j .content >"$saved_file"
python3 "<skill-dir>/scripts/validate_work_item_links.py" "$saved_file" --require-id 1234
python3 - "$markdown_file" "$saved_file" <<'PY'
from pathlib import Path
import sys
source, saved = (Path(path).read_text(encoding="utf-8").replace("\r\n", "\n") for path in sys.argv[1:])
if source != saved:
    raise SystemExit("Wiki readback did not preserve the Markdown content.")
PY
```

For an existing UTF-8 Markdown file on Windows, use PowerShell 7 and keep the JSON envelope in a temporary file. This avoids console encoding and quoting conversions:

```powershell
$markdownPath = 'C:\path\to\release-notes.md'
$requiredWorkItemId = '1234'
$pagePath = [IO.Path]::GetTempFileName()
$headers = @{ Authorization = "Bearer $env:ADO_TOKEN" }
$uri = "$env:ADO_WIKI_URL/pages?path=/Releases/2026-06&api-version=7.1"
try {
    & '<skill-dir>/scripts/Assert-WikiWorkItemLinks.ps1' -MarkdownPath $markdownPath -RequireId $requiredWorkItemId
    $existing = Invoke-WebRequest -Method Get -Uri "$uri&includeContent=true" -Headers $headers
    $etag = @($existing.Headers.ETag)[0] # PowerShell 7 returns header values as string[]
    $markdown = Get-Content -LiteralPath $markdownPath -Raw -Encoding utf8
    $json = ConvertTo-Json -InputObject @{ content = $markdown } -Depth 10 -Compress
    [IO.File]::WriteAllText($pagePath, $json, [Text.UTF8Encoding]::new($false))
    Invoke-RestMethod -Method Put -Uri $uri -Headers (@{ Authorization = "Bearer $env:ADO_TOKEN"; 'If-Match' = $etag }) `
        -ContentType 'application/json; charset=utf-8' -InFile $pagePath | Out-Null
    $readBack = Invoke-RestMethod -Method Get -Uri "$uri&includeContent=true" -Headers $headers
    $readBackPath = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($readBackPath, [string]$readBack.content, [Text.UTF8Encoding]::new($false))
        & '<skill-dir>/scripts/Assert-WikiWorkItemLinks.ps1' -MarkdownPath $readBackPath -RequireId $requiredWorkItemId
    }
    finally {
        Remove-Item -LiteralPath $readBackPath -Force -ErrorAction SilentlyContinue
    }
    if (($readBack.content -replace "`r`n", "`n") -cne ($markdown -replace "`r`n", "`n")) {
        throw 'Wiki readback did not preserve the Markdown content.'
    }
}
finally {
    Remove-Item -LiteralPath $pagePath -Force -ErrorAction SilentlyContinue
}
```

The Azure CLI equivalent also reads the Markdown file directly: `az devops wiki page update --wiki {wiki} --path /Releases/2026-06 --file-path .\release-notes.md --encoding utf-8 --version {etag-from-get}`. The CLI requires the current page ETag for updates; read the page back through REST to verify Japanese content.

## Common workflows

### Publish release notes
1. Gather inputs: completed work items for the iteration ([azure-devops-boards](../azure-devops-boards/SKILL.md)), merged PRs ([azure-devops-repos](../azure-devops-repos/SKILL.md)), deployed build ([azure-devops-pipelines](../azure-devops-pipelines/SKILL.md)).
2. Compose Markdown grouped by Features / Fixes / Known issues. Use `#<id>` for Wiki work item links; use appropriate links for PRs.
3. `wiki_upsert_page` under a dated path such as `/Releases/{version}`; show the user the draft before publishing if the wiki is broadly visible.

### Sprint report
1. Pull iteration work items and their states; compute done/carry-over.
2. Upsert `/Sprints/{iteration}` with summary table, highlights, and impediments.

## Guardrails

- Wiki pages are visible to everyone with project access — treat publishing as an outward-facing action and confirm content with the user before the first publish of a new page.
- Always use the ETag flow for updates; overwriting concurrent human edits destroys work.
- Page paths are hierarchical (`/Parent/Child`); creating a child requires the parent to exist.
- Code wikis are backed by a Git repo — large reorganizations may be easier as a Git commit than page-by-page API calls.

## Learn more

- `microsoft_docs_search("Azure DevOps wiki pages REST API create update")`
- `microsoft_docs_search("provisioned wiki vs published code wiki")`
- `microsoft_docs_search("Azure DevOps wiki Markdown syntax")`
