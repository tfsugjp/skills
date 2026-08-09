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

# Read (capture ETag from headers)
curl -si -H "Authorization: Bearer ${ADO_TOKEN}" \
  "${WIKI}/pages?path=/Releases/2026-06&includeContent=true&api-version=7.1"

# Update with concurrency guard
curl -s -X PUT -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json" -H "If-Match: ${ETAG}" \
  "${WIKI}/pages?path=/Releases/2026-06&api-version=7.1" \
  -d '{"content": "# June 2026 Release\n\n..."}'
```

## Common workflows

### Publish release notes
1. Gather inputs: completed work items for the iteration ([azure-devops-boards](../azure-devops-boards/SKILL.md)), merged PRs ([azure-devops-repos](../azure-devops-repos/SKILL.md)), deployed build ([azure-devops-pipelines](../azure-devops-pipelines/SKILL.md)).
2. Compose Markdown grouped by Features / Fixes / Known issues, linking work item and PR URLs.
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
