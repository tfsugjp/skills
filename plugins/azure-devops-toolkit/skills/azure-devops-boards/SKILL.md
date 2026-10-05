---
name: azure-devops-boards
description: 'Manage Azure Boards work items: create, update fields, add comments, link items, and close them. Use when the user asks to create/update/comment on/close bugs, tasks, user stories, features, or other work items in Azure DevOps. Writes body fields as Markdown (switching the field format, with an HTML fallback), records the root cause and fix approach in a Bug''s Repro Steps, and links work items back to their Wiki pages. Prefer Azure DevOps MCP Server tools, then use Windows-native PowerShell Invoke-RestMethod or az boards on Windows, and fall back to REST/CLI on non-Windows systems. Feature-equivalent work items and Bugs with an approved fix approach require a delegated Azure DevOps Wiki registration before completion.'
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

## Long-text field format

### Body field

The body of a work item is the long-text field its form shows as the main text:

| Work item type | Body field |
|---|---|
| Bug | `Microsoft.VSTS.TCM.ReproSteps` (Repro Steps). The Agile, Scrum, and CMMI Bug forms do not show `System.Description`, so text written there is invisible. |
| Every other type (Feature, Epic, User Story, Product Backlog Item, Requirement, Issue, Task, ...) | `System.Description` |

Confirm with `wit_work_item` `get_type` (or REST `GET .../workitemtypes/{type}`) that the type has the expected field. If a custom process removed it or moved the body to another field, ask instead of guessing.

### Markdown first, HTML fallback

A multiline field is stored as HTML rich text unless its format is switched, and the HTML format takes precedence: Markdown written into an HTML-format field is shown as raw Markdown. Prepare the body in a UTF-8 Markdown source file, reject literal escaped line breaks (backslash-n or backslash-r-backslash-n) in prose and an accidental outer code fence, then write it as follows:

1. **Markdown (preferred).** Submit the Markdown source as the field value and switch the field to Markdown in the same JSON Patch with `{"op":"add","path":"/multilineFieldsFormat/<FieldRef>","value":"Markdown"}`. Encode `<` as `&lt;` and `>` as `&gt;` in the value; the server sanitizes the field as HTML-capable text, and the Azure DevOps MCP Server applies the same encoding. With MCP, set `format: "Markdown"` on the field in `wit_work_item_write` `create` or `update_batch`; these actions add the format operation and the encoding. The single-item `update` action passes operations through unchanged, so either use `update_batch` for the item or add the encoded value and the `/multilineFieldsFormat/<FieldRef>` operation yourself.
2. **Read back** with `GET .../workitems/{id}?api-version=7.1` and require `multilineFieldsFormat.<FieldRef>` to equal `Markdown` (compare case-insensitively) and the stored value to equal the submitted value after normalizing CRLF to LF.
3. **HTML (fallback).** If the server rejects the `/multilineFieldsFormat` operation or the read-back does not report Markdown (Azure DevOps Server does not support Markdown multiline fields), convert the Markdown to HTML and write it without the format operation. On PowerShell 7, use `ConvertFrom-Markdown -InputObject` and submit its Html property; on Linux/macOS, render the file with a Markdown renderer or author valid HTML directly. Then require rich-text structure in the stored value and reject a stored literal escaped newline, raw Markdown heading, or accidental outer code fence. Azure Boards may normalize HTML, so compare decoded text and structure rather than exact HTML bytes.

Never leave raw Markdown in an HTML-format field. When updating an item whose body field is still HTML, switch the format and rewrite the whole field in Markdown instead of appending Markdown to HTML. The [Windows-native execution reference](references/windows-native-execution.md) contains complete examples for both paths.

For custom fields, inspect the field metadata first: use Markdown or HTML only for an HTML/rich-text field and preserve the declared format for other field types. Do not silently turn a plain-text custom field into HTML.

Apply the read-back checks after every create or update, including writes made with MCP tools, and check the Unicode title too. If the stored representation differs, report the created item ID and repair the field before reporting success.

## Bug analysis body

Whenever a Bug is created, or its analysis or fix approach is established or changes, the Repro Steps body must contain these sections in this order:

```markdown
## Repro steps
1. ...

## Expected vs actual
- Expected: ...
- Actual: ...

## Root cause
<the analysis of why the defect happens: the faulty code path, condition, or configuration, with file and function names>

## Fix approach
<the planned change, its scope, and how it will be verified>

## Wiki
- [/<repo>/bug/<id>-<slug>](https://dev.azure.com/{org}/{project}/_wiki/wikis/{wiki}/{pageId}/{page-name})
```

- Root cause and Fix approach record the AI's own analysis. Write them in full; do not leave them only in the chat, a comment, or the Wiki page. When the analysis has not been done yet, write `Not yet analyzed` under the heading instead of omitting it, and rewrite the section once it is done.
- When the fix approach is approved or changes later, rewrite the whole body so the sections stay current; keep the earlier reasoning in `System.History` or a comment if it matters.
- Add the `## Wiki` section only after the page is registered (see [Wiki link on work items](#wiki-link-on-work-items)).
- On read-back, require each of the `Repro steps`, `Expected vs actual`, `Root cause`, and `Fix approach` headings with non-empty text before reporting success.

## Wiki link on work items

When the plan, bug fix plan, or other content of a work item of any type — Feature-equivalent item, Bug, Task, or another type — is registered in the Azure DevOps Wiki, link the work item back to the page:

1. Take the page URL from the `remoteUrl` that azure-devops-wiki returns after its read-back. Do not build the URL by hand.
2. Add a `## Wiki` section at the end of the body field (replace the section if it already exists) with one list item per registered page: a Markdown link whose text is the page path and whose target is the page `remoteUrl`. Write the whole body again in the format chosen in [Long-text field format](#long-text-field-format).
3. Add a hyperlink relation in the same JSON Patch: `{"op":"add","path":"/relations/-","value":{"rel":"Hyperlink","url":"<remoteUrl>","attributes":{"comment":"Wiki: <page path>"}}}`. Read the item with `$expand=relations` first and skip the relation when a `Hyperlink` with the same URL already exists.
4. Read the item back and verify both the `## Wiki` section and exactly one matching `Hyperlink` relation before reporting the registration as complete.

Page links point into the team's own authenticated organization and are part of the work item's purpose; write them in full.

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

1. Read [azure-devops-wiki](../azure-devops-wiki/SKILL.md) and resolve the Wiki and the repository's page hierarchy (`/<repo>`, `/<repo>/plan`, `/<repo>/bug`) using read operations. The plan page destination is `/<repo>/plan/<id>-<slug>`.
2. Confirm that the Wiki and repository can be determined, and run the Wiki skill's conformance check. If the repository's pages are non-conforming, obtain the user's approval of the migration mapping before creating the Work Item; if the Wiki or repository cannot be determined or the migration is declined, do not create the Work Item. Missing root or index pages and the approved migration are carried out by the Wiki skill's publish sequence; do not create or move Wiki structure from this skill.
3. Create the Work Item hierarchy only after the Wiki preflight succeeds.
4. Explicitly load and run azure-devops-wiki, handing it the Work Item ID, title, approved plan, repository name, and child Task IDs. Require a Wiki reference in `#<id>` form; `AB#<id>` does not create a Wiki work item link. Do not duplicate Wiki page-writing logic in this skill or agent.
5. Read the page back and verify that the registration contains the `#<id>` reference and approved plan, with no `AB#<id>` work item reference in prose, and that the `/<repo>/plan` index lists the page.
6. Link the Work Item back to the page as described in [Wiki link on work items](#wiki-link-on-work-items). Report the Feature operation as successful only after this verification. Child Tasks whose content is registered on their own Wiki pages get the same back-link.
7. When the pull request is created, hand the PR number and any design changes found during implementation back to azure-devops-wiki so it updates the plan page, its index row, and the root page's overall design when the specification changed.

If an unexpected Wiki write fails after the Work Item exists, do not delete the Work Item. Report the created ID as a partial failure and identify Wiki registration as the required retry.

### Bug fix plan Wiki registration

When the fix approach for a Bug is approved, hand the Bug ID, title, related Feature ID (when one exists; otherwise the page records None), repository name, and approved fix approach to azure-devops-wiki, which writes `/<repo>/bug/<id>-<slug>` and its index row. Before the handoff, make sure the Bug's Repro Steps carries the approved Root cause and Fix approach (see [Bug analysis body](#bug-analysis-body)); after the Wiki read-back, link the Bug back to the page as described in [Wiki link on work items](#wiki-link-on-work-items). Creating the Bug Work Item itself is not gated; do not report the fix plan as registered until both read-back verifications succeed. Hand the PR number back after the PR is created, together with any specification change the fix introduces so the root page's overall design is updated.

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

# Create a bug whose Repro Steps (bug-body.md, UTF-8) holds the analysis sections, stored as Markdown
jq -n --arg title "Login fails on Safari" --rawfile repro bug-body.md --arg tags "regression; auth" \
  '[{"op":"add","path":"/fields/System.Title","value":$title},
    {"op":"add","path":"/fields/Microsoft.VSTS.TCM.ReproSteps","value":($repro | gsub("<";"&lt;") | gsub(">";"&gt;"))},
    {"op":"add","path":"/multilineFieldsFormat/Microsoft.VSTS.TCM.ReproSteps","value":"Markdown"},
    {"op":"add","path":"/fields/System.Tags","value":$tags}]' \
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

If the create returns an error for the `/multilineFieldsFormat` operation, or the read-back does not report `Markdown`, follow the HTML fallback in [Long-text field format](#long-text-field-format).

On Windows, use the PowerShell 7 temporary-file pattern in [Windows-native execution reference](references/windows-native-execution.md). It uses `ConvertTo-Json -InputObject` for the top-level patch array, writes UTF-8 without a BOM, sends with `Invoke-RestMethod -InFile` and `charset=utf-8`, and removes the file in `finally`. It covers the Markdown path, the HTML fallback, and the Wiki back-link. Read the work item back with REST and verify non-ASCII fields after every write.

Linking via REST is also a PATCH on `/relations/-`, e.g. relation type `System.LinkTypes.Hierarchy-Reverse` (parent), `ArtifactLink` with a `vstfs:///Git/PullRequestId/...` URL for PRs, and `Hyperlink` for a Wiki page.

## Common workflows

### Create → assign → track
1. `wit_work_item` `get_type` to confirm required fields and the body field for the chosen type.
2. `wit_work_item_write` `create` with title, the body field with `format: "Markdown"` (Repro Steps with the analysis sections for a Bug), area/iteration. Read it back and apply the format checks.
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
