---
name: azure-devops-advanced-security
description: 'Work with GitHub Advanced Security for Azure DevOps (GHAzDO): list and triage code/secret/dependency scanning alerts, dismiss (close) alerts, and associate alerts with work items. Use when the user asks about Advanced Security alerts, CodeQL findings, secret scanning, or dependency vulnerabilities in Azure Repos. REST-API-based — the Azure DevOps MCP Server has no Advanced Security tools.'
compatibility: 'Azure DevOps Services with GitHub Advanced Security (or standalone Code/Secret Security) enabled on the repository. API is 7.2-preview.'
---

# GitHub Advanced Security for Azure DevOps (GHAzDO)

Triage, dismiss, and track Advanced Security alerts. Read [azure-devops-foundation](../azure-devops-foundation/SKILL.md) first for authentication.

> **No MCP tools exist for Advanced Security.** Unlike Boards/Repos/Pipelines, the Azure DevOps MCP Server does not expose alert tools — always use the REST API below (host `advsec.dev.azure.com`, not `dev.azure.com`). Combine with MCP work item tools from [azure-devops-boards](../azure-devops-boards/SKILL.md) for work item association.

## When to use

- Listing or filtering security alerts (code scanning/CodeQL, secret scanning, dependency scanning)
- Inspecting a specific alert (location, rule, severity, validity for secrets)
- Dismissing/closing alerts as false positive or accepted risk
- Creating and linking work items to track alert remediation
- Checking which branches have successful Advanced Security analysis

## Prerequisites

| Requirement | Detail |
|---|---|
| Feature enabled | Advanced Security must be enabled on the repository (billable; "Manage settings" permission required to enable) |
| Read alerts | "Advanced Security: read alerts" permission (Contributors have it by default) |
| Dismiss alerts | "Advanced Security: manage and dismiss alerts" permission (Project Administrators by default) |
| Token scope | PATs need the `vso.advsec` / `vso.advsec_manage` scope; Entra tokens use the caller's permissions |

## REST API

Base: `https://advsec.dev.azure.com/{organization}/{project}/_apis/alert/repositories/{repository}` with `api-version=7.2-preview.1`. Verify the current schema with `microsoft_docs_search("Advanced Security alerts REST API")` before first use in a session.

| Operation | Method and endpoint |
|---|---|
| List alerts | `GET .../alerts` |
| Filter | `?criteria.alertType=code|secret|dependency`, `criteria.states=active`, `criteria.severities=critical,high`, `criteria.onlyDefaultBranch=false`, `criteria.alertIds=100,200` |
| Lightweight list | `?expand=minimal` |
| Get one alert | `GET .../alerts/{alertId}` |
| Dismiss / update | `PATCH .../alerts/{alertId}` (see body below) |
| Analyzed branches | `GET .../filters/branches` |
| Analyses (scan submissions) | `GET .../analyses` |

```bash
ADVSEC="https://advsec.dev.azure.com/{org}/{project}/_apis/alert/repositories/{repo}"

# List active critical/high alerts on the default branch
curl -s -H "Authorization: Bearer ${ADO_TOKEN}" \
  "${ADVSEC}/alerts?criteria.states=active&criteria.severities=critical,high&api-version=7.2-preview.1"

# Dismiss an alert as accepted risk (requires manage/dismiss permission)
curl -s -X PATCH -H "Authorization: Bearer ${ADO_TOKEN}" -H "Content-Type: application/json" \
  "${ADVSEC}/alerts/{alertId}?api-version=7.2-preview.1" \
  -d '{
    "state": "dismissed",
    "dismissedReason": "acceptedRisk",
    "dismissedComment": "Mitigated by network isolation; revisit after Q3 migration."
  }'
```

Dismissal reasons are limited to **false positive** and **accepted risk** (plus a free-text comment). Dismissing an alert applies across all branches and auto-resolves the linked PR annotation. Fixed alerts close automatically when a new scan no longer finds the issue — you do not close "fixed" alerts manually.

## Work item association

There is no dedicated link API; associate alerts with work items via the work item side:

1. Create a tracking work item ([azure-devops-boards](../azure-devops-boards/SKILL.md)): title with rule ID + severity, description containing the alert summary and the alert URL (`https://dev.azure.com/{org}/{project}/_git/{repo}/alerts/{alertId}`), tag such as `ghazdo`.
2. Add a hyperlink relation to the alert URL (JSON Patch `add /relations/-` with `"rel": "Hyperlink"`, or MCP `wit_work_item_link_write` `add_artifact_link`).
3. When dismissing or after the fix is merged, comment on the work item with the outcome and close it.

For the full alert-to-resolution flow, use [azure-devops-security-triage](../azure-devops-security-triage/SKILL.md).

## Alert types at a glance

| Type | Source | Notes |
|---|---|---|
| Code scanning | CodeQL pipeline task | Severity from CVSS/CWE; alert per location |
| Secret scanning | Push protection + repo scans (automatic, periodic re-scans) | `validityResult` shows if the secret is still active — prioritize active secrets; rotation, not dismissal, is the fix |
| Dependency scanning | Dependency scanning pipeline task | Returns CVE/advisory IDs in `additionalProperties`; re-run the scan after upgrading |

## Guardrails

- **Dismissing alerts is a security decision.** Never dismiss without explicit user confirmation, a stated reason, and a comment. Prefer fixing over dismissing.
- An exposed secret that is dismissed is still exposed — recommend rotation/revocation regardless of alert state.
- Listing alerts touches sensitive data (secret excerpts, vulnerable paths). Don't paste secret values into chat, commits, or work items; reference the alert URL instead.
- 403 responses usually mean missing Advanced Security permissions or the feature is not enabled — report it; do not retry with other credentials.
- Severity filtering first (`critical,high`) keeps triage tractable on large repos.

## Learn more

- `microsoft_docs_search("Advanced Security alerts REST API list update")`
- `microsoft_docs_search("GitHub Advanced Security Azure DevOps dismiss alerts permissions")`
- `microsoft_docs_search("GitHub Advanced Security secret scanning validity checking")`
- `microsoft_docs_search("GitHub Advanced Security dependency scanning setup")`
