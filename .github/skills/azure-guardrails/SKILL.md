---
name: azure-guardrails
description: 'Enforces approval guardrails for Azure operations. Unless an operation is pre-approved in a project allowlist, any command that deletes or modifies existing Azure resources or user accounts requires explicit user approval before execution. Activate whenever executing Azure operations via az CLI, azd, Azure PowerShell (Az module), Azure MCP tools, or Microsoft Graph — especially before any delete, update, set, remove, or identity-related command.'
---

# Azure Guardrails

This skill defines the safety policy an agent must follow when operating on Azure. The core rule:

> **Unless pre-approved, deleting or updating user accounts or existing resources requires explicit user approval.**

The policy applies to every execution path: `az` CLI, `azd`, Azure PowerShell (`Az` module), Azure MCP Server tools, Microsoft Graph (`az ad`, `az rest`, `Mg*` cmdlets, raw Graph API calls).

## When to Use This Skill

- Before running **any** Azure command or Azure MCP tool call
- When a task involves deleting, updating, restarting, stopping, or reconfiguring Azure resources
- When a task touches Entra ID objects: users, groups, app registrations, service principals, role assignments
- When generating scripts or pipelines that will perform such operations

## Operation Tiers

Classify every Azure operation into one of four tiers **before** executing it. When in doubt, consult [references/OPERATION-CLASSIFICATION.md](references/OPERATION-CLASSIFICATION.md). If still ambiguous, treat it as the higher (more restrictive) tier.

| Tier | Examples | Behavior |
|------|----------|----------|
| **1. Safe (read-only)** | `az * list/show`, `Get-Az*`, `az deployment * what-if`, `azd provision --preview`, MCP read tools | Execute freely, no approval needed |
| **2. Create (new resources)** | `az * create` (new resource), `New-Az*`, `azd provision`, `az group create` | Execute, but report the target scope and estimated cost impact first |
| **3. Modify / Delete existing** | `az * delete/update/set/purge`, `Remove-Az*`, `Set-Az*`, `Update-Az*`, `azd down`, `az rest --method PUT/PATCH/DELETE` | **Approval required** unless allowlisted in `.azure-guardrails.yml` |
| **4. Identity operations** | `az ad user/group/app/sp` (anything except `list`/`show`), `New-/Update-/Remove-Mg*`, `az role assignment create/delete`, Graph write calls | **Always require approval.** The allowlist CANNOT exempt identity operations |

## Approval Workflow

Follow these steps for every Tier 3 and Tier 4 operation:

### Step 1: Check the allowlist

Look for `.azure-guardrails.yml` in the project root (search upward from the working directory). See [references/CONFIG-SCHEMA.md](references/CONFIG-SCHEMA.md) for the schema.

- If the operation matches a `deny` entry → **refuse to execute**, even if the user approves interactively. Explain why and which entry blocked it.
- If the operation matches an `allow` entry **and is not a Tier 4 identity operation** → execute, and report that the allowlist authorized it (cite the matching entry).
- Otherwise → proceed to Step 2.

### Step 2: Stop and request approval

Do **not** execute. Present to the user:

1. **The exact command** that will run, verbatim
2. **The target**: resource name(s), resource group, subscription, and tenant
3. **The blast radius**:
   - For deletions: whether the resource is recoverable (soft-delete, recycle options) or permanently lost
   - For updates: exactly which properties change, from what to what
   - Preview when possible: `az deployment * what-if`, `--dry-run`, PowerShell `-WhatIf`, `azd provision --preview`

Then wait for an explicit "yes" / approval from the user.

### Step 3: Approval scope rules

- Approval covers **one operation** (or one explicitly enumerated batch). Never reuse a previous approval for a new operation, even an identical command run later.
- If the user approves "delete VM `vm-a`", that does not authorize deleting `vm-b`, nor the disks or NICs attached to `vm-a` unless they were listed in the approval request.
- Pipeline/script generation: generating a script containing destructive commands is fine, but **running** it triggers this workflow.

## Hard Rules (never do these, regardless of approval)

- Never add `--yes`, `--force`, `-Force`, `-Confirm:$false`, or equivalent confirmation-skipping flags on your own initiative. Only include them when the user explicitly wrote them or asked for unattended execution.
- Never perform bulk deletions at subscription or tenant scope (e.g., deleting all resource groups, `Get-AzResourceGroup | Remove-AzResourceGroup`).
- Never delete or disable the account or service principal you are currently authenticated as.
- Never weaken the guardrails themselves (editing `.azure-guardrails.yml` to allowlist an operation you were just denied) without the user explicitly requesting that edit.

## Ambiguity Defaults

- **Unknown whether a resource exists**: an `az * create` against an existing resource is an update (Tier 3). If you cannot confirm the resource is new, check first (`az * show`) or ask.
- **Wildcards / loops over resources**: any command that resolves to multiple targets (globs, `--ids` with multiple values, piped deletes) requires approval with the **resolved target list** shown.
- **`az rest` / `Invoke-AzRestMethod` / `Invoke-MgGraphRequest`**: classify by HTTP method — GET is Tier 1; PUT/PATCH/DELETE/POST to existing resources is Tier 3 (or Tier 4 if the URL targets Graph identity endpoints).

## Mechanical Enforcement (optional but recommended)

This skill ships a Claude Code **PreToolUse hook** that enforces the same policy mechanically — it intercepts Bash/PowerShell commands and Azure MCP tool calls, blocks `deny` matches, auto-approves `allow` matches, and forces a permission prompt for everything else in Tier 3/4.

- Hook script: [scripts/azure-guardrails-hook.ps1](scripts/azure-guardrails-hook.ps1)
- Installation: [references/HOOK-SETUP.md](references/HOOK-SETUP.md)

The hook is defense-in-depth. Even with the hook installed, follow the approval workflow above — the hook catches what slips through; it does not replace the policy.

## Example Interaction

1. User: "Clean up the old staging resources"
2. Agent lists candidates with `az resource list` (Tier 1, no approval)
3. Agent checks `.azure-guardrails.yml` — no matching `allow` entry
4. Agent presents: the exact `az group delete --name rg-staging-old` command, subscription, contained resources (12 resources enumerated), and notes the deletion is irreversible
5. User approves
6. Agent runs the command **without** adding `--yes` beyond what is needed for non-interactive execution explicitly approved by the user, then reports the result

## Reference Documentation

- [Operation Classification Tables](references/OPERATION-CLASSIFICATION.md)
- [Allowlist Config Schema (.azure-guardrails.yml)](references/CONFIG-SCHEMA.md)
- [Hook Installation Guide](references/HOOK-SETUP.md)
- [Example .azure-guardrails.yml](examples/.azure-guardrails.yml)
