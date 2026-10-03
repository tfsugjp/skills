---
name: azure-devops-wiki
description: 'Work with Azure DevOps wikis: read, search, create, and update wiki pages; publish plans and bug fix plans into the repository-rooted hierarchy (/<repo> overall design, /<repo>/plan and /<repo>/bug indexes with Work Item and PR references); and publish generated content such as release notes or sprint reports. Use when the user asks to read or write Azure DevOps wiki pages or register a plan or bug fix in the wiki. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (wiki toolset).'
---

# Azure DevOps Wiki

Read, search, and publish wiki content. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Reading or searching wiki pages (project wiki or code wiki)
- Creating or updating pages (`wiki_upsert_page` handles both)
- Registering an approved plan or bug fix plan for a repository (see [Repository page hierarchy](#repository-page-hierarchy))
- Updating a repository's overall design after a specification change
- Publishing generated documents: release notes, sprint reports, runbooks, meeting notes

## Repository page hierarchy

Plans and bug fix plans live under one root page per repository. The layout is fixed:

```text
/<repo>                        Root: repository overview table + overall design
/<repo>/plan                   Index of plan pages
/<repo>/plan/<id>-<slug>       Plan for Work Item <id>
/<repo>/bug                    Index of bug fix plan pages
/<repo>/bug/<id>-<slug>        Bug fix plan for Work Item <id>
```

- `<repo>` is the repository name exactly as Azure Repos or GitHub shows it, with no suffix such as `-plan`.
- `<id>` is the Work Item ID of the Feature-equivalent item (plan) or the Bug (bug). `<slug>` is a short lowercase, hyphen-separated description. A page path never changes after creation; the Work Item ID keeps it unique.
- Write page prose and headings in the language the existing wiki already uses (read the sibling pages first). The templates are English skeletons; translate their headings, keep their structure, and remove the leading HTML comment before publishing.
- Link wiki pages with standard Markdown links to the absolute page path, for example link text `Plans` with the target `/<repo>/plan`. Do not use `[[/path]]`: the wiki's move and rename dialog finds and repairs only standard Markdown links.

### Root page `/<repo>`

Start from [templates/root-page.md](templates/root-page.md). The root page is the single, current, final-form design of the whole repository, not a log.

1. An overview table with these rows, each linked where a target exists: **Repository** (link to the repository), **Default branch**, **Infrastructure** (CLIs, Azure PaaS services and plans, IaC entry point), **Build outputs** (packages, binaries, sites, or images the build produces), **CI/CD** (Azure Pipelines or GitHub Actions, with links to each definition file), and **Design documents** (links to the design files in the repository). Use "None" for a row that does not apply; do not drop rows.
2. A child page table linking `/<repo>/plan` and `/<repo>/bug`.
3. An **Overall design** section: purpose and scope, architecture (a Mermaid `graph` is welcome), components and responsibilities, data and state, integrations, deployment, and constraints.

Whenever a plan or bug fix changes the specification, behavior, infrastructure, build outputs, or CI/CD, update the root page in the same publish as the child page. Rewrite the affected sections into their new final form; do not append change notes. If nothing in the root changes, say so explicitly in the report instead of silently skipping it.

### Index pages `/<repo>/plan` and `/<repo>/bug`

Start from [templates/index-page.md](templates/index-page.md). Each index lists **every** child page that exists under it, newest Work Item first, in one table:

| Column | Contents |
|---|---|
| Work Item | `#<id>` |
| Page | Link whose text is the child page title and whose target is `/<repo>/<plan or bug>/<id>-<slug>` |
| PR | Pull request link (see below), several separated by `<br>`, or "Not yet created" |
| Status | Current state: Planned, In progress, or Completed for plans; Investigating, Fix planned, Fixed, or Verified for bugs; or the remaining open point |
| Summary | One sentence describing what the child page covers |

Whenever a child page is created or its PR or status changes, update its index row in the same publish. Get the authoritative child list from the wiki (`list_pages`, or `GET .../pages?path=/<repo>/plan&recursionLevel=oneLevel`) and validate the index with one `--require-page-link` per child, so pages created outside this skill are also listed.

### Plan and bug pages

- Plan pages start from [templates/plan-page.md](templates/plan-page.md): metadata table (Work Item, Repository, Branch, PR, Status), Related Work Items table (the Feature-equivalent item and its child Tasks), then purpose, current state, design, implementation steps, acceptance criteria, and constraints found during implementation.
- Bug pages start from [templates/bug-page.md](templates/bug-page.md): metadata table (Work Item, Related feature, Repository, Branch, PR, Status), then symptoms, root cause, **fix approach**, fix steps, acceptance criteria, and verification. Create the bug page when the fix approach for a Bug Work Item is approved, before implementation.
- Both page types must contain the Work Item reference `#<id>` and the pull request link. Before the PR exists, write "Not yet created" in the PR row; after the PR is created, update the page and its index row, then validate with `--require-pr`.
- When implementation reveals constraints or design changes, record them on the child page and update the root page's overall design in the same publish, including at the PR update.

### Pull request links

`#<n>` is a Work Item reference in Wiki Markdown, so never write a pull request as `#<n>`. Write a Markdown link whose text starts with `!` for Azure Repos:

- Azure Repos: `[!322](https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/322)`
- GitHub: `[{owner}/{repo}#45](https://github.com/{owner}/{repo}/pull/45)`

Repository, pipeline-definition, design-document, and pull request links point into the team's own authenticated organization and are part of the page's purpose; write them in full. Keep the placeholder rule for every other internal URL, IP address, and secret.

### Publish sequence

1. **Discover.** Resolve the wiki, then read `/<repo>`, `/<repo>/plan`, and `/<repo>/bug` with their child lists. Read the repository's design documents, pipeline definitions, and IaC entry point to fill or check the root overview.
2. **Check conformance.** If the repository's pages live elsewhere or use another layout, follow [Migrating non-conforming pages](#migrating-non-conforming-pages) before writing.
3. **Create missing structure.** Create a missing root page, then missing index pages, from the templates. Show the user the drafts and get confirmation before the first publish of each new page.
4. **Write the child page** from the plan or bug template.
5. **Update the index row** and, when the specification changed, **the root page's overall design**.
6. **Validate every page you write** with the scripts below, write it with the ETag flow, and read it back.

| Page | Validation arguments |
|---|---|
| Root | `--require-page-link /<repo>/plan --require-page-link /<repo>/bug` |
| Index | `--require-id <id>` for each listed Work Item, `--require-page-link <child path>` for each child, `--require-pr <n>` for each listed PR |
| Plan or bug | `--require-id <id>` and, once the PR exists, `--require-pr <n>` |

### Migrating non-conforming pages

Existing wikis may hold a repository's design and plans in other shapes, such as `/<repo>-plan` with plans directly beneath it, `/<repo>/Plans`, a plan index without a PR column, or an index that misses child pages. When you work on such a repository:

1. List the current pages and propose a mapping to the fixed layout: which page becomes the root (and which content becomes the overall design), which children move to `plan` or `bug`, and which index rows must be added or repaired.
2. Get explicit user approval for the mapping. Moving pages changes URLs that people use, so never move without approval, and never delete a page as part of a migration. If the user declines, stop: do not write the new page elsewhere, and report that the registration (and any Work Item creation waiting on it) is blocked on the layout decision.
3. Move each approved page with the page move API (`POST /wikis/{wiki}/pagemoves`), which keeps the page history. The API does not rewrite links on other pages, so search the wiki for links to each old path and update them. Create missing root and index pages from the templates when no source page exists.
4. Fix the moved pages' content to match the templates (for example, a PR written as `#<n>` becomes a pull request link) and rebuild the affected index and root pages.
5. Read every moved and rebuilt page back and validate it as in the publish sequence.

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `wiki` | `list_wikis`, `get_wiki`, `list_pages`, `get_page` | Discover wikis and read pages (content + metadata) |
| `search_wiki` | — | Full-text wiki search |
| `wiki_upsert_page` | — | Create a page or update it if it exists |

## Work item links in Wiki Markdown

Write a Wiki work item reference as `#1234` for work item 1234. Never use `AB#1234` in a Wiki page: that notation is for linking GitHub content to Azure Boards and does not produce the Wiki work item link. Keep the Azure Repos and GitHub conventions in their own skills; this rule applies to Azure DevOps Wiki content only.

Before every Wiki create or update, validate the exact UTF-8 Markdown file that will be submitted. Use [scripts/validate_work_item_links.py](scripts/validate_work_item_links.py) on Linux/macOS or [scripts/Assert-WikiWorkItemLinks.ps1](scripts/Assert-WikiWorkItemLinks.ps1) in PowerShell 7. Both reject `AB#<id>` in prose while allowing code examples. `--require-id` / `-RequireId` checks each Work Item ID that the page must link, `--require-pr` / `-RequirePr` checks for a pull request link (`/pullrequest/<n>` or `/pull/<n>`), and `--require-page-link` / `-RequirePageLink` checks for a Markdown link to an absolute wiki page path. Repeat the Python options once per value; pass PowerShell arrays such as `-RequirePageLink '/repo/plan/1234-slug','/repo/plan/1300-slug'`. If a check fails, fix the Markdown and validate again. Apply the same preflight when using `wiki_upsert_page`: prepare a file first, validate it, then submit its exact content.

Read the saved page back after writing. Re-run the validator on the returned content and require the expected `#<id>` references; compare the saved Markdown with the source after normalizing line endings. Do not report the Work Item Wiki registration complete if the required reference is missing or the stored content contains `AB#<id>` in prose.

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis/wiki`. The "List wikis" operation sits directly under this base (`/wikis`); page operations are scoped to a specific wiki (`/wikis/{wikiIdentifier}/pages`). Verify with `microsoft_docs_search("Azure DevOps wiki pages REST API")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| List wikis | `GET /wikis` | `7.1` |
| Get page (+content) | `GET /wikis/{wiki}/pages?path={path}&includeContent=true` | `7.1` |
| Create page | `PUT /wikis/{wiki}/pages?path={path}` (no `If-Match`) | `7.1` |
| Update page | `PUT /wikis/{wiki}/pages?path={path}` with `If-Match: {ETag}` | `7.1` |
| List child pages | `GET /wikis/{wiki}/pages?path={path}&recursionLevel=oneLevel` | `7.1` |
| Move page | `POST /wikis/{wiki}/pagemoves` with `{ "path": "{old}", "newPath": "{new}" }` | `7.1` |
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
- Page paths are hierarchical (`/Parent/Child`); creating a child requires the parent to exist, so create `/<repo>`, then `/<repo>/plan`, then the plan page.
- Never leave an index or root stale: a child page missing from its index, or a root page whose overall design no longer matches the implemented specification, is an incomplete publish.
- Code wikis are backed by a Git repo — large reorganizations may be easier as a Git commit than page-by-page API calls.

## Learn more

- `microsoft_docs_search("Azure DevOps wiki pages REST API create update")`
- `microsoft_docs_search("provisioned wiki vs published code wiki")`
- `microsoft_docs_search("Azure DevOps wiki Markdown syntax")`
