# `.azure-guardrails.yml` — Allowlist Configuration Schema

Place this file in the **project root**. Both the agent (via the skill policy) and the PreToolUse hook search upward from the working directory and use the first file found.

The file declares which Tier 3 operations are **pre-approved** (run without per-operation approval) and which operations are **always denied**. If the file is absent, every Tier 3/4 operation requires interactive approval — that is the safe default.

## Schema

```yaml
# Required. Schema version; currently always 1.
version: 1

# Optional. Operations pre-approved to run WITHOUT per-operation approval.
# Tier 4 (identity) operations listed here are IGNORED — identity operations
# always require interactive approval.
allow:
  - operation: "<command prefix>"     # required — case-insensitive prefix match
    scope:                            # optional — restricts where the exemption applies
      resource-groups: ["<glob>"]     # glob patterns; omit = any resource group
      subscriptions: ["<id-or-glob>"] # omit = any subscription
    reason: "<why this is safe>"      # optional but recommended — shown in audit output

# Optional. Operations that are ALWAYS blocked, even if the user approves
# interactively. deny takes precedence over allow.
deny:
  - operation: "<command prefix>"
    scope:
      resource-groups: ["<glob>"]
    reason: "<why this is forbidden>"

# Optional. If present, ALL mutating operations are restricted to these
# subscriptions; operations targeting any other subscription are denied.
subscriptions:
  - "<subscription id or name glob>"
```

## Matching Rules

1. **Precedence: `deny` > `allow` > default (ask).**
2. `operation` is a **prefix match** against the normalized command (whitespace-collapsed, case-insensitive). `az webapp config appsettings set` matches `az  webapp config appsettings set -g rg-dev-app ...` but not `az webapp delete`.
3. For Azure MCP tools, `operation` matches against `mcp:<area> <operation>`, e.g. `mcp:storage delete` or `mcp:keyvault set`.
4. `scope.resource-groups` matches the value of `-g` / `--resource-group` / `--resource-group-name` / `ResourceGroupName` in the command (glob, case-insensitive). If the entry declares a scope but the command's resource group cannot be determined, the entry does **not** match (fail closed).
5. Identity operations (Tier 4 — `az ad`, `az role assignment`, `Mg*` writes, Graph writes) never match `allow`, but **do** match `deny`.

## Examples

### Typical dev-team setup

```yaml
version: 1

allow:
  # Routine app-settings tweaks in dev resource groups
  - operation: "az webapp config appsettings set"
    scope:
      resource-groups: ["rg-dev-*", "rg-sandbox-*"]
    reason: "Dev config churn is routine and recoverable"

  # Restarting dev apps
  - operation: "az webapp restart"
    scope:
      resource-groups: ["rg-dev-*"]

  # Cleaning up old deployment history entries (metadata only)
  - operation: "Remove-AzResourceGroupDeployment"
    reason: "Deletes deployment records, not resources"

deny:
  # Production resource groups must never be deleted by an agent
  - operation: "az group delete"
    scope:
      resource-groups: ["rg-prod-*"]
    reason: "Production deletion is a human-only, change-managed operation"
  - operation: "azd down"
    reason: "Environment teardown must be done manually"

subscriptions:
  - "contoso-dev"
  - "contoso-sandbox"
```

### Minimal (lock everything down explicitly)

```yaml
version: 1
deny:
  - operation: "az group delete"
  - operation: "az ad"
```

## What the allowlist can NOT do

- It cannot exempt **identity operations** (Tier 4). `allow: [{operation: "az ad user delete"}]` is silently ignored by both the skill policy and the hook.
- It cannot authorize the **hard rules** in SKILL.md (bulk subscription-scope deletion, self-deletion of the authenticated principal, confirmation-flag injection).
- An agent must not edit this file to unblock itself. Changes to `.azure-guardrails.yml` should only be made when the user explicitly requests them, and ideally go through code review.
