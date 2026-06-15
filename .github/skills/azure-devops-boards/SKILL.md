---
name: azure-devops-boards
description: 'Manage Azure Boards work items: create, update fields, add comments, link items, and close them. Use when the user asks to create/update/comment on/close bugs, tasks, user stories, or other work items in Azure DevOps. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (wit toolset).'
---

# Azure Boards Work Items

Create, update, comment on, link, and close Azure Boards work items. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Creating bugs, tasks, user stories, features, or epics
- Updating fields (title, description, assignee, iteration, area, priority, tags)
- Adding or updating comments on a work item
- Closing or transitioning work items (close = state transition)
- Querying work items (saved queries, backlogs, full-text search)
- Linking work items to each other or to pull requests/commits/builds

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `wit_work_item` | `get`, `get_batch`, `my`, `list_comments`, `list_revisions`, `list_for_iteration`, `get_type` | Read work items, comments, history, and type metadata |
| `wit_query` | `get`, `get_results` | Run saved queries |
| `wit_backlog` | `list`, `list_work_items` | Backlog levels and their items |
| `search_workitem` | — | Full-text work item search |
| `wit_work_item_write` | `create`, `update`, `update_batch`, `add_child` | Create and update work items (state changes included) |
| `wit_work_item_comment_write` | `add`, `update` | Add or edit comments |
| `wit_work_item_link_write` | `link`, `unlink`, `link_to_pull_request`, `add_artifact_link` | Link work items to each other, PRs, branches, commits, builds |
| `wit_work_item_attachment` | — | Download attachments |

Closing a work item is `wit_work_item_write` with action `update`, setting `System.State` to the type's terminal state (`Closed` for Bug/Task in Agile, `Done` for PBI in Scrum). Use `wit_work_item` action `get_type` to discover valid states before transitioning.

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis/wit` — verify exact versions with `microsoft_docs_search("Azure DevOps REST API work items <operation>")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| Create work item | `POST .../workitems/${type}` (note the `$` before the type, URL-encode spaces: `$User%20Story`) | `7.1` |
| Get work item | `GET .../workitems/{id}?$expand=all` | `7.1` |
| Update fields / close | `PATCH .../workitems/{id}` | `7.1` |
| Add comment | `POST .../workItems/{id}/comments` | `7.1-preview.4` |
| Run WIQL query | `POST .../wiql` with `{"query": "SELECT [System.Id] FROM WorkItems WHERE ..."}` | `7.1` |
| Batch get | `POST .../workitemsbatch` | `7.1` |

Work item create/update uses **JSON Patch** (`Content-Type: application/json-patch+json`):

```bash
# Create a bug
curl -s -X POST -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/\$Bug?api-version=7.1" \
  -d '[
    {"op": "add", "path": "/fields/System.Title", "value": "Login fails on Safari"},
    {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.ReproSteps", "value": "1. Open login page..."},
    {"op": "add", "path": "/fields/System.Tags", "value": "regression; auth"}
  ]'

# Close a work item (state transition + resolution comment)
curl -s -X PATCH -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?api-version=7.1" \
  -d '[
    {"op": "add", "path": "/fields/System.State", "value": "Closed"},
    {"op": "add", "path": "/fields/System.History", "value": "Fixed by PR !123, verified in build 456."}
  ]'
```

Linking via REST is also a PATCH on `/relations/-`, e.g. relation type `System.LinkTypes.Hierarchy-Reverse` (parent), `ArtifactLink` with a `vstfs:///Git/PullRequestId/...` URL for PRs.

## Common workflows

### Create → assign → track
1. `wit_work_item` `get_type` to confirm required fields for the chosen type.
2. `wit_work_item_write` `create` with title, description, area/iteration.
3. `wit_work_item_write` `update` to set `System.AssignedTo` and priority.
4. `wit_work_item_link_write` `link` to attach parent/related items.

### Close with traceability
1. Verify the fix is merged/deployed (cross-check with [azure-devops-repos](../azure-devops-repos/SKILL.md) / [azure-devops-pipelines](../azure-devops-pipelines/SKILL.md)).
2. `wit_work_item_comment_write` `add` summarizing the resolution with PR/build references.
3. `wit_work_item_write` `update` setting `System.State` to the terminal state.

### Bulk update
Prefer `wit_work_item_write` `update_batch` (or REST `$batch`) over looping single updates; it is atomic per item and far fewer requests.

## Guardrails

- State names are **process-specific** (Agile/Scrum/CMMI/custom). Always check valid states via `get_type` or the project's process before transitioning; never hard-code `Closed`.
- Do not close work items without user confirmation unless the user explicitly asked for closure.
- `System.History` is append-only — use it for audit comments during updates; use the comments API for discussion threads.
- Multi-value tags are a single `; `-separated string, not an array.
- Bulk operations: dry-run first (list the IDs and intended change, get confirmation), then execute.

## Learn more

- `microsoft_docs_search("Azure DevOps REST API work items create update JSON patch")`
- `microsoft_docs_search("Azure DevOps work item comments REST API")`
- `microsoft_docs_search("WIQL syntax work item query language")`
- `microsoft_docs_search("Azure Boards default workflow states process")`
