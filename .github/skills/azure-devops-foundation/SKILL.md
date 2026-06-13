---
name: azure-devops-foundation
description: 'Shared foundation for all Azure DevOps skills: how to detect and configure the Azure DevOps MCP Server, and how to fall back to the REST API (Entra ID or PAT authentication) when MCP tools are unavailable. Read this before using any azure-devops-* skill.'
compatibility: 'Azure DevOps Services. Local MCP server requires Node.js 20+. Microsoft Learn MCP Server recommended for documentation lookup.'
---

# Azure DevOps Foundation (MCP-first, REST API fallback)

This skill defines the common access strategy used by every `azure-devops-*` skill in this repository: prefer the **Azure DevOps MCP Server** tools, fall back to the **REST API** when MCP is unavailable, and use the **Microsoft Learn MCP Server** (`microsoft_docs_search` / `microsoft_docs_fetch`) to verify any endpoint before calling it.

## Access strategy (always follow this order)

1. **Azure DevOps MCP Server tools** — if tools such as `core_list_projects`, `wit_work_item`, `repo_pull_request`, or `pipelines_build` are available in the current session, use them. They handle authentication, pagination, and API versioning for you.
2. **REST API** — if MCP tools are not available (server not configured, client not supported, or the operation has no MCP tool), call the REST API directly with `curl` or PowerShell as described below.
3. **Azure CLI (`az devops`)** — as an alternative to raw REST when the CLI is installed and signed in. See the [azure-devops-cli skill](../azure-devops-cli/SKILL.md) for the complete CLI reference.

> Important: Two areas have **no MCP tools at all** and always start at step 2:
> **GitHub Advanced Security** (see [azure-devops-advanced-security](../azure-devops-advanced-security/SKILL.md)) and
> **Azure Artifacts feeds/packages** (see [azure-devops-artifacts](../azure-devops-artifacts/SKILL.md)).

## Detecting MCP availability

- In Claude Code / agent environments, MCP tools appear with a `mcp__<server>__` prefix (for example `mcp__ado__wit_work_item`). In VS Code Copilot agent mode they appear by bare name (`wit_work_item`).
- If a tool call fails with "tool not found" or the server list does not include an Azure DevOps server, do not retry — switch to the REST API fallback.
- Never simulate or fabricate MCP results. If neither MCP nor REST access works, report the configuration problem to the user.

## Configuring the Azure DevOps MCP Server

### Local server (GA — recommended for Claude Code and most clients)

Requires Node.js 20+. Add to `.mcp.json` (Claude Code) or `.vscode/mcp.json` (VS Code):

```json
{
  "servers": {
    "ado": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@azure-devops/mcp", "{organization}"]
    }
  }
}
```

- Authentication: Microsoft Entra ID (interactive/az login) or a PAT via environment variable.
- Restrict surface area with domain flags, for example `"args": ["-y", "@azure-devops/mcp", "{organization}", "-d", "work-items", "repositories"]`.

### Remote server (public preview)

Hosted endpoint, no installation: `https://mcp.dev.azure.com/{organization}` (streamable HTTP, Entra ID OAuth).

```json
{
  "servers": {
    "ado-remote": {
      "url": "https://mcp.dev.azure.com/{organization}",
      "type": "http",
      "headers": { "X-MCP-Toolsets": "repos,wit,pipelines" }
    }
  }
}
```

- Optional headers: `X-MCP-Toolsets` (`repos`, `wit`, `pipelines`, `wiki`, `work`, `testplan`), `X-MCP-Readonly: true`, `X-MCP-Tools` (explicit tool list), `X-MCP-Insiders: true`.
- As of mid-2026 the remote server supports only Visual Studio and VS Code clients; other clients (Claude Code, Cursor, etc.) must use the local server.

## REST API fallback

### Authentication

**Preferred — Microsoft Entra ID token** (works when the user is signed in with Azure CLI; `499b84ac-1321-427f-aa17-267ca6975798` is the fixed Azure DevOps resource ID):

```bash
ADO_TOKEN=$(az account get-access-token \
  --resource 499b84ac-1321-427f-aa17-267ca6975798 \
  --query accessToken -o tsv)

curl -s -H "Authorization: Bearer ${ADO_TOKEN}" \
  "https://dev.azure.com/{organization}/_apis/projects?api-version=7.1"
```

**Alternative — Personal Access Token (PAT)**, e.g. from the `AZURE_DEVOPS_EXT_PAT` environment variable (Basic auth with empty username):

```bash
curl -s -u ":${AZURE_DEVOPS_EXT_PAT}" \
  "https://dev.azure.com/{organization}/_apis/projects?api-version=7.1"
```

Microsoft recommends Entra ID tokens over PATs. Never print tokens to the terminal, never commit them, and never include them in logs or error reports.

### Request conventions

| Convention | Detail |
|---|---|
| Base URL | `https://dev.azure.com/{organization}[/{project}]/_apis/{area}/{resource}` |
| Specialized hosts | `advsec.dev.azure.com` (Advanced Security), `feeds.dev.azure.com` (feed management), `pkgs.dev.azure.com` (package content), `almsearch.dev.azure.com` (search) |
| `api-version` | Required on every call. Use `7.1` (GA) unless the resource is preview-only (e.g. Advanced Security uses `7.2-preview.1`) |
| Work item writes | `Content-Type: application/json-patch+json` with a JSON Patch array |
| Other writes | `Content-Type: application/json` |
| Pagination | Follow `x-ms-continuationtoken` response header / `continuationToken` query parameter |
| Rate limiting | On HTTP 429 or 503, honor the `Retry-After` header and retry with backoff; reduce parallelism |

### Verify before you call

REST endpoints and `api-version` values change. Before constructing a REST call you have not used in this session, verify it with the Microsoft Learn MCP Server:

```text
microsoft_docs_search("Azure DevOps REST API <area> <operation>")
microsoft_docs_fetch("<learn.microsoft.com URL from the search result>")
```

Do not invent endpoints or api-version strings from memory.

## Guardrails

- Confirm with the user before destructive or hard-to-reverse operations: deleting resources, abandoning PRs, dismissing security alerts, bulk state changes.
- Respect least privilege: prefer read-only configuration (`X-MCP-Readonly`) when the task only requires queries.
- Scope writes to the project/repository the user named; never enumerate-and-modify across an organization without explicit instruction.
- Surface permission errors (HTTP 401/403) as configuration findings — do not retry with elevated credentials on your own.

## Related skills

| Skill | Scope |
|---|---|
| [azure-devops-boards](../azure-devops-boards/SKILL.md) | Work items: create, update, comment, close |
| [azure-devops-repos](../azure-devops-repos/SKILL.md) | Pull requests: create, review, comment threads |
| [azure-devops-pipelines](../azure-devops-pipelines/SKILL.md) | Pipelines: create, run, monitor |
| [azure-devops-advanced-security](../azure-devops-advanced-security/SKILL.md) | GHAS alerts: triage, dismiss, work item association |
| [azure-devops-artifacts](../azure-devops-artifacts/SKILL.md) | Feeds and packages |
| [azure-devops-testplans](../azure-devops-testplans/SKILL.md) | Test plans, suites, cases |
| [azure-devops-wiki](../azure-devops-wiki/SKILL.md) | Wiki pages and publishing |
| [azure-devops-security-triage](../azure-devops-security-triage/SKILL.md) | End-to-end GHAS alert remediation workflow |
| [azure-devops-cli](../azure-devops-cli/SKILL.md) | Full `az devops` CLI reference |

## Learn more

- `microsoft_docs_search("Azure DevOps MCP Server overview")`
- `microsoft_docs_search("remote Azure DevOps MCP Server preview")`
- `microsoft_docs_search("Azure DevOps REST API get started authentication Entra")`
- `microsoft_docs_search("Azure DevOps REST API rate limits")`
