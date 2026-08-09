---
name: azure-devops-repos
description: 'Work with Azure Repos pull requests: create PRs, review and vote, manage comment threads, resolve comments, and complete or abandon PRs. Use when the user asks to create, review, comment on, or merge pull requests in Azure DevOps. Prefers Azure DevOps MCP Server tools and falls back to the REST API.'
compatibility: 'Azure DevOps Services. MCP tools require the Azure DevOps MCP Server (repos toolset).'
---

# Azure Repos Pull Requests

Create, review, comment on, and complete pull requests in Azure Repos. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for the MCP-first/REST-fallback strategy and authentication.

## When to use

- Creating a pull request (including draft PRs and autocomplete)
- Reviewing: adding reviewers, voting (approve / approve with suggestions / wait for author / reject)
- Creating comment threads, replying, and resolving/closing threads
- Completing, abandoning, or reactivating PRs
- Inspecting branches, files at a commit, or searching code

## MCP tools (preferred)

| Tool | Action | Purpose |
|---|---|---|
| `repo_repository` | `get`, `list` | Repository lookup |
| `repo_branch` | `get`, `list`, `list_mine` | Branch inspection |
| `repo_create_branch` | — | Create a branch |
| `repo_pull_request` | `get`, `list`, `list_by_commits` | Read PRs |
| `repo_pull_request_write` | `create`, `update`, `update_reviewers`, `vote` | Create PR, set title/description/draft/autocomplete, complete or abandon (via `update` status), manage reviewers, cast votes |
| `repo_pull_request_thread` | `list`, `list_comments` | Read comment threads |
| `repo_pull_request_thread_write` | `create`, `reply`, `update_status` | New thread, reply, resolve/close threads |
| `repo_file` | `get_content`, `list_directory` | Read repository content |
| `repo_search_commits` / `search_code` | — | Commit and code search |

Vote values: `10` approve, `5` approve with suggestions, `0` no vote, `-5` wait for author, `-10` reject.
Thread statuses: `active`, `fixed` (resolved), `wontFix`, `closed`, `pending`.

## REST API fallback

Base: `https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repositoryId}` — verify with `microsoft_docs_search("Azure DevOps REST API pull requests <operation>")` before calling.

| Operation | Method and endpoint | api-version |
|---|---|---|
| Create PR | `POST .../pullrequests` | `7.1` |
| Get / list PRs | `GET .../pullrequests[/{prId}]` (`searchCriteria.status=active` etc.) | `7.1` |
| Update PR (complete/abandon/title) | `PATCH .../pullrequests/{prId}` | `7.1` |
| Add reviewer / vote | `PUT .../pullrequests/{prId}/reviewers/{reviewerId}` | `7.1` |
| List / create threads | `GET/POST .../pullRequests/{prId}/threads` | `7.1` |
| Reply to thread | `POST .../pullRequests/{prId}/threads/{threadId}/comments` | `7.1` |
| Resolve thread | `PATCH .../pullRequests/{prId}/threads/{threadId}` (`{"status": "fixed"}`) | `7.1` |

```bash
# Create a pull request
curl -s -X POST -H "Authorization: Bearer ${ADO_TOKEN}" -H "Content-Type: application/json" \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests?api-version=7.1" \
  -d '{
    "sourceRefName": "refs/heads/feature/login-fix",
    "targetRefName": "refs/heads/main",
    "title": "Fix Safari login failure",
    "description": "Fixes AB#1234.",
    "isDraft": false
  }'

# Complete a PR with squash merge and source-branch deletion
curl -s -X PATCH -H "Authorization: Bearer ${ADO_TOKEN}" -H "Content-Type: application/json" \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests/{prId}?api-version=7.1" \
  -d '{
    "status": "completed",
    "lastMergeSourceCommit": {"commitId": "<latest source commit SHA>"},
    "completionOptions": {"mergeStrategy": "squash", "deleteSourceBranch": true}
  }'
```

## Common workflows

### Create a PR with work item linkage
1. `repo_create_branch` (or confirm the source branch exists with `repo_branch` `get`).
2. `repo_pull_request_write` `create` with a clear title and a description that references the work item (`AB#<id>` auto-links on Azure Repos).
3. `wit_work_item_link_write` `link_to_pull_request` (see [azure-devops-boards](../azure-devops-boards/SKILL.md)) for explicit linking.
4. `repo_pull_request_write` `update_reviewers` to add required reviewers, optionally `update` to enable autocomplete.

### Review a PR
1. `repo_pull_request` `get` for metadata; `repo_file` `get_content` / iteration changes for the diff context.
2. `repo_pull_request_thread_write` `create` for each finding — anchor file path and line via thread context so comments land on the diff.
3. `repo_pull_request_write` `vote` with the appropriate value. Reserve `-10` (reject) for cases the user confirmed.

### Resolve review comments
1. `repo_pull_request_thread` `list` and filter `status == "active"`.
2. After addressing each finding, `repo_pull_request_thread_write` `reply` explaining the fix (commit reference), then `update_status` to `fixed`.
3. Do not mark threads `fixed` that you did not actually address; use `wontFix` only with the user's agreement.

## Guardrails

- Completing or abandoning a PR is hard to reverse — confirm with the user first unless they explicitly asked for it.
- Never bypass branch policies (`bypassPolicy` options) unless the user explicitly instructs and has the permission.
- When voting on behalf of the user, state clearly in the thread that the review was AI-assisted, if the team requires it.
- `sourceRefName`/`targetRefName` need the full `refs/heads/` prefix; bare branch names fail.
- Branch deletion on completion is irreversible for unmerged extra commits — check `deleteSourceBranch` intent.

## Learn more

- `microsoft_docs_search("Azure DevOps REST API pull requests create")`
- `microsoft_docs_search("Azure DevOps REST API pull request threads comments")`
- `microsoft_docs_search("Azure Repos branch policies pull request completion")`
- `microsoft_docs_search("link work items to pull requests AB# syntax")`
