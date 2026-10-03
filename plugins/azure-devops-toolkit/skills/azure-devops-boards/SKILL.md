---
name: azure-devops-boards
description: 'Manage Azure Boards work items: create, update fields, add comments, link items, and close them. Use when the user asks to create/update/comment on/close bugs, tasks, user stories, features, or other work items in Azure DevOps. Prefer Azure DevOps MCP Server tools, then use Windows-native PowerShell Invoke-RestMethod or az boards on Windows, and fall back to REST/CLI on non-Windows systems. Feature-equivalent work items require a delegated Azure DevOps Wiki registration before completion.'
---

# Azure Boards Work Items

Create, update, comment on, link, and close Azure Boards work items. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first strategy and authentication.


## Execution policy

Follow this order for every operation:

1. Use Azure DevOps MCP tools when they are available.
2. When MCP is unavailable on Windows, use PowerShell 7 with Invoke-RestMethod and a UTF-8 request file. Use native az boards from PowerShell only as an ASCII-only fallback; it has no file input for titles or descriptions.
3. On Linux and macOS, use the REST/CLI fallback described below.

On Windows, never invoke Azure DevOps operations through MSYS2, Git Bash, WSL, bash, or sh. If only one of those shells is available, stop and report that a native PowerShell path is required. Read [Windows-native execution reference](references/windows-native-execution.md) for the encoding-safe command patterns.

Do not rewrite Japanese or other non-English content because captured az output looks corrupted. Redirected output can be encoded with the Windows ANSI code page even when the server data is intact. Read the stored value back with Invoke-RestMethod before diagnosing data loss.

## Description format preflight

Treat the standard System.Description field as HTML rich text. Prepare multiline content in a UTF-8 Markdown source file, reject literal escaped line breaks (backslash-n or backslash-r-backslash-n) in prose and an accidental outer code fence, then convert Markdown to HTML before passing the value to MCP or REST. On PowerShell 7, use ConvertFrom-Markdown -InputObject with the source string and submit its Html property. On Linux/macOS, prepare an HTML file with a Markdown renderer or author valid HTML directly; do not submit raw Markdown as System.Description. The Windows reference below contains a complete preflight example.

For custom fields, inspect the field metadata first: use HTML only for an HTML/rich-text field and preserve the declared format for other field types. Do not silently turn a plain-text or Markdown-enabled custom field into HTML.

After creation or update, read the item back and check both the Unicode title and description text. Require rich-text structure in System.Description and reject a stored literal escaped newline, raw Markdown heading, or accidental outer code fence. Azure Boards may normalize HTML, so compare decoded text and structure rather than exact HTML bytes. Apply these checks even when the MCP write tool was used. If the stored representation differs, report the created item ID and repair the field before reporting success.

## When to use

- Creating bugs, tasks, user stories, features, or epics
- Updating fields (title, description, assignee, iteration, area, priority, tags)
- Adding or updating comments on a work item
- Closing or transitioning work items (close = state transition)
- Querying work items (saved queries, backlogs, full-text search)
- Linking work items to each other or to pull requests/commits/builds


## Feature-equivalent Wiki gate

Before creating a requirement-level item, query the project process and backlog metadata. Treat these types as Feature-equivalent and require Wiki registration:

- Feature in Agile, Scrum, or CMMI processes
- Issue in the Basic process, which has no separate Feature type
- A custom type assigned to the same portfolio/backlog level as Feature

Do not trigger this gate for a User Story, Product Backlog Item, Requirement, Task, or Bug unless the project metadata explicitly maps that type to the Feature level. If the mapping is ambiguous, ask instead of guessing.

For a Feature-equivalent item, follow this sequence:

1. Read [azure-devops-wiki](../azure-devops-wiki/SKILL.md) and discover the existing Wiki, parent page, and page path using read operations. Do not create, rename, reorder, or re-index Wiki structure.
2. Confirm that the existing placement can be used and that the approved plan has a concrete page destination. If the Wiki or destination cannot be determined, do not create the Work Item.
3. Create the Work Item hierarchy only after the Wiki preflight succeeds.
4. Explicitly load and run azure-devops-wiki, handing it the Work Item ID, title, approved plan, and existing page path. Require a Wiki reference in `#<id>` form; `AB#<id>` does not create a Wiki work item link. Do not duplicate Wiki page-writing logic in this skill or agent.
5. Read the page back and verify that the registration contains the `#<id>` reference and approved plan, with no `AB#<id>` work item reference in prose. Report the Feature operation as successful only after this verification.

If an unexpected Wiki write fails after the Work Item exists, do not delete the Work Item. Report the created ID as a partial failure and identify Wiki registration as the required retry.

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
patch_file="$(mktemp)"
trap 'rm -f "$patch_file"' EXIT

# Create a bug
jq -n --arg title "Login fails on Safari" --arg repro "1. Open login page..." --arg tags "regression; auth" \
  '[{"op":"add","path":"/fields/System.Title","value":$title},{"op":"add","path":"/fields/Microsoft.VSTS.TCM.ReproSteps","value":$repro},{"op":"add","path":"/fields/System.Tags","value":$tags}]' \
  >"$patch_file"
curl -s -X POST -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json-patch+json; charset=utf-8" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/\$Bug?api-version=7.1" \
  --data-binary "@$patch_file"

# Close a work item (state transition + resolution comment)
jq -n \
  '[{"op":"add","path":"/fields/System.State","value":"Closed"},{"op":"add","path":"/fields/System.History","value":"Fixed by PR !123, verified in build 456."}]' \
  >"$patch_file"
curl -s -X PATCH -H "Authorization: Bearer ${ADO_TOKEN}" \
  -H "Content-Type: application/json-patch+json; charset=utf-8" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?api-version=7.1" \
  --data-binary "@$patch_file"
```

On Windows, use the PowerShell 7 temporary-file pattern in [Windows-native execution reference](references/windows-native-execution.md). It uses `ConvertTo-Json -InputObject` for the top-level patch array, writes UTF-8 without a BOM, sends with `Invoke-RestMethod -InFile` and `charset=utf-8`, and removes the file in `finally`. Read the work item back with REST and verify non-ASCII fields after every write.

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
