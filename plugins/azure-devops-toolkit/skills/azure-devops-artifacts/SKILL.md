---
name: azure-devops-artifacts
description: 'Manage Azure Artifacts: list and create feeds, inspect package versions, promote packages between views, delete/unlist versions, and publish/download Universal Packages. Use when the user asks about Azure DevOps package feeds, NuGet/npm/Maven/Python/Universal packages, or feed views. REST/CLI-based — the Azure DevOps MCP Server has no Artifacts tools.'
compatibility: 'Azure DevOps Services. Universal Packages publish/download requires Azure CLI with the azure-devops extension.'
---

# Azure Artifacts

Manage feeds, packages, and views in Azure Artifacts. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for authentication.

> **No MCP tools exist for Azure Artifacts.** The Azure DevOps MCP Server's `pipelines_artifact` tool handles **build artifacts** only (files attached to a build), not package feeds. For feeds and packages always use the REST API or `az artifacts` CLI below.

## When to use

- Listing/creating feeds, checking feed permissions or upstream sources
- Listing packages and versions in a feed
- Promoting a package version to a view (`@prerelease` → `@release`)
- Deleting, unlisting, or recovering package versions
- Publishing or downloading Universal Packages

## REST API

Two hosts with different roles — verify operations with `microsoft_docs_search("Azure Artifacts REST API <operation>")` before first use:

- **`feeds.dev.azure.com`** — feed management (feeds, views, permissions, package metadata)
- **`pkgs.dev.azure.com`** — package content and per-protocol operations (promote, delete, download)

Project-scoped feeds include `/{project}` in the path; organization-scoped feeds omit it.

| Operation | Method and endpoint | api-version |
|---|---|---|
| List feeds | `GET https://feeds.dev.azure.com/{org}[/{project}]/_apis/packaging/feeds` | `7.1` |
| Create feed | `POST .../packaging/feeds` (`{"name": "...", "hideDeletedPackageVersions": true}`) | `7.1` |
| List packages in feed | `GET .../packaging/feeds/{feedId}/packages?includeAllVersions=true` | `7.1` |
| List views | `GET .../packaging/feeds/{feedId}/views` | `7.1` |
| Promote version to view (NuGet example) | `PATCH https://pkgs.dev.azure.com/{org}[/{project}]/_apis/packaging/feeds/{feedId}/nuget/packages/{name}/versions/{version}` | `7.2-preview.1` |
| Delete version (NuGet example) | `DELETE` same URL as promote | `7.2-preview.1` |

Promote sends a `PackageVersionDetails` object as `application/json` (not a JSON Patch array). Its `views` field holds a single JSON Patch operation that appends the target view to the package version's views:

```bash
# Promote my-lib 1.2.3 to the Release view (org-scoped NuGet feed)
curl -s -X PATCH -H "Authorization: Bearer ${ADO_TOKEN}" -H "Content-Type: application/json" \
  "https://pkgs.dev.azure.com/{org}/_apis/packaging/feeds/{feedId}/nuget/packages/my-lib/versions/1.2.3?api-version=7.2-preview.1" \
  -d '{"views": {"op": "add", "path": "/views/-", "value": "Release"}}'
```

The same URL pattern exists per protocol: `nuget`, `npm` (batch endpoint `npm/packagesbatch`), `maven/groups/{groupId}/artifacts/{artifactId}`, `pypi`, `upack` (Universal), `cargo`.

## Universal Packages (CLI required)

There is **no REST endpoint to download Universal Packages** — use the Azure CLI:

```bash
# Publish
az artifacts universal publish \
  --organization https://dev.azure.com/{org} --project {project} --scope project \
  --feed {feed} --name my-tool --version 1.0.0 --path ./dist \
  --description "CLI tooling bundle"

# Download (supports --file-filter for partial download)
az artifacts universal download \
  --organization https://dev.azure.com/{org} --project {project} --scope project \
  --feed {feed} --name my-tool --version 1.0.0 --path ./download
```

For broader CLI coverage (`az devops`, auth setup), see the [azure-devops-cli skill](../azure-devops-cli/SKILL.md).

## Common workflows

### Release promotion
1. Confirm the version exists: list packages with `includeAllVersions=true`.
2. Confirm quality gates passed (build/test status via [azure-devops-pipelines](../azure-devops-pipelines/SKILL.md)).
3. PATCH-promote to `Release` view; consumers pinned to `feed@Release` pick it up automatically.

### Clean up a bad release
1. Prefer **unlist** (hides from search, existing restores keep working) over delete when consumers may depend on it.
2. Delete moves the version to the recycle bin (recoverable for a limited time), but the version number is permanently reserved — you can never republish `1.2.3`.

## Guardrails

- **Package versions are immutable.** Deleting does not free the version number; plan a new patch version instead of republishing.
- Deleting/unlisting affects every consumer of the feed — confirm with the user and prefer unlist.
- PAT scope for package writes is **Packaging (Read, write, & manage)**.
- Views in feeds of public projects are publicly visible; don't promote internal packages in public projects without checking visibility.
- Upstream-source packages cached in the feed are not yours to delete casually; removing them breaks restore for everyone.

## Learn more

- `microsoft_docs_search("Azure Artifacts Feed Management REST API")`
- `microsoft_docs_search("promote packages feed views REST API")`
- `microsoft_docs_search("Universal Packages publish download Azure CLI")`
- `microsoft_docs_search("Azure Artifacts delete recover packages")`
