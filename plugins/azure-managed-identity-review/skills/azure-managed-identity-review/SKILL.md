---
name: azure-managed-identity-review
description: 'Review an Azure managed identity (MSI) before and after it is used for a resource: find every other resource, app setting, code path, and federated identity credential (FIC) that uses the same identity, then check each consumer''s target audience against the identity''s role assignments. Use when adding or changing a user-assigned identity, role assignment, FIC, identity-based connection (__credential, __clientId), Key Vault reference, or customer-managed key; when reviewing Bicep/ARM/Terraform that touches identities; when asked "who else uses this identity", "review MSI permissions", "MSIをレビュー"; or when an app gets 401/403 only after deployment although local E2E passed.'
---

# Azure Managed Identity Review

A user-assigned identity is often created for one resource and then reused by others. Role assignments are granted with the first resource in mind, so:

- **Missing grants**: another consumer reaches a different audience (Service Bus, SQL, Cosmos DB data plane, a custom `api://` app) that nobody granted. Local E2E runs as the developer (`DefaultAzureCredential`, `local.settings.json` without `__credential`), so it only fails after deployment.
- **Leaked grants**: every consumer, and every external workload trusted through a federated identity credential, holds every grant on the identity.

This skill builds a consumer × target × grant matrix for the identity and reports both directions. It is read-only: it never creates role assignments, FICs, or identities. Propose fixes as IaC changes.

Paths below are relative to this skill directory. The script needs Python 3.9+ and nothing else; Bicep files are compiled with the Bicep CLI (`bicep`, or `az bicep`).

## Workflow

1. **Scope.** Identify the resource or identity being changed. If the change touches any identity, grant, FIC, or identity-based app setting, review it — not only the resource in the diff.
2. **Static review** of the repository (IaC, app settings, code):

   ```bash
   python3 scripts/msi_review.py static <repo-or-infra-dir> --resource <resource-name>
   ```

   ```powershell
   python scripts/msi_review.py static <repo-or-infra-dir> --resource <resource-name>
   ```

   `--resource` reviews the identities that resource uses **and every other consumer of them**. Use `--identity <name>` to start from an identity, or omit both to review everything.
3. **Live review** when the user is signed in to Azure (read-only `az` calls; app setting values are masked):

   ```bash
   python3 scripts/msi_review.py live --subscription <subscription-id> --resource <resource-name> --static <infra-dir>
   ```

   `--static` adds drift findings (MIR008): consumers or grants that exist in Azure but not in IaC, such as a role granted in the portal. Ask before running live mode against a subscription the user has not named.
4. **Report** the identity tables and findings (the Markdown output is ready to paste into a review). For each MIR002/MIR005 error, propose the IaC change. For MIR001/MIR003/MIR004, ask whether the sharing is intended; the usual fix is one identity per purpose.
5. **Manual checks** the script cannot see — SQL users, Cosmos DB data-plane roles outside IaC, app roles on custom APIs, post-deployment verification — are in [references/review-checklist.md](references/review-checklist.md).

Exit code 0 means no warnings or errors (info and notes may remain), 1 means warnings or errors, 2 means an input error.

## Options

| Option | Use |
| --- | --- |
| `--identity <name or resource ID>` | Review this identity and all its consumers. Repeatable. |
| `--resource <name>` | Review the identities this resource holds and all their other consumers. Repeatable. |
| `--parameters <file>` | ARM parameters JSON for unresolved Bicep parameters. For `.bicepparam`: `bicep build-params <file>.bicepparam --outfile <out>.json`. |
| `--map <dir>=<resource>` | Attribute source code under `<dir>` to a resource. Without it, code is attributed only when there is exactly one app and one Functions project. |
| `--tf-plan-json <file>` | Output of `terraform show -json <plan>`; resolves module and variable values that `*.tf` parsing cannot. |
| `--no-code`, `--no-bicep-build` | Skip the code scan; read committed ARM JSON (resource group, subscription, management group, or tenant scope) instead of compiling Bicep. |
| `--json` | Machine-readable model and findings. |
| `live --replay <dir>` / `--record <dir>` | Replay or record (masked) `az` output, for tests and offline review. |

## Rules

| Rule | Severity | Finding | Typical fix |
| --- | --- | --- | --- |
| MIR000 | note | A reference could not be resolved statically (parameter without value, module input, `var.*`). | Pass `--parameters` / `--tf-plan-json`, or use live mode. |
| MIR001 | warning | A user-assigned identity is attached to more than one resource; lists what each uses it for. | Confirm each purpose; prefer one identity per purpose. |
| MIR002 | error / warning | A consumer reaches a target with the identity, but no grant for that identity covers it. Error for identity-based connections and platform slots; warning when inferred from a URL or code, or when the only grant is on a child (a container, queue, or secret) of the target. | Grant the least-privileged data role on the target to that identity, in IaC. |
| MIR003 | warning / info | A shared identity holds a broad-scope (resource group, subscription) or privileged grant, or a grant only one consumer needs. Warning when an FIC also exists. | Narrow the scope, or split the identity. |
| MIR004 | warning | A federated credential lets an external workload act as an identity that resources also use; non-standard audience; flexible (expression) subject matching. | Dedicated identity for the external workload. |
| MIR005 | error / warning | An identity-based connection, Key Vault reference, or SDK call names no client ID: the platform uses the system-assigned identity, which is missing (error) or not the intended one (warning). Also a warning when a client ID matches none of the resource's identities. | Set `<prefix>__clientId`, `AZURE_CLIENT_ID`, or `keyVaultReferenceIdentity` to an attached identity. |
| MIR006 | info | The target needs a non-RBAC grant (SQL contained user, Cosmos DB data-plane role, app role on Graph or a custom API). | Verify by hand (checklist). |
| MIR007 | info | Code or `local.settings.json` authenticates as the developer locally, so local E2E cannot reveal MIR002. | Verify after deployment with the deployed identity. |
| MIR008 | warning | Live state differs from IaC (extra consumer, undeclared grant or FIC). | Declare it in IaC or remove it. |

How targets and identities are inferred, and which roles satisfy each audience: [references/audience-role-map.md](references/audience-role-map.md).

## Windows

Run the script with `python` from PowerShell 7. It calls `az` with argument lists and sends Resource Graph queries as a UTF-8 `--body @<file>`, so the `cmd.exe` quoting problems described in the `windows-shell-safety` plugin do not apply. Do not wrap the command in `cmd /c` or a nested `-Command` string.

## Tests

```bash
python3 tests/test_msi_review.py -v
```

Fixtures cover the canonical scenario (storage CMK identity reused by a Function App for Service Bus and trusted by GitHub Actions) in Bicep, compiled ARM, and Terraform; identity selection and non-RBAC targets; a clean configuration; unresolved references; Terraform plan JSON; and recorded live output with drift. The Bicep test is skipped when the standalone `bicep` CLI is not on `PATH`.
