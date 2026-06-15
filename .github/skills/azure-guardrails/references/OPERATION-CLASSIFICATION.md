# Azure Operation Classification Tables

Detailed classification of Azure operations into the four guardrail tiers. Use these tables when the tier of a command is not obvious. **When a command matches multiple tiers, the highest (most restrictive) tier wins.**

Tier summary:

- **Tier 1 — Safe (read-only)**: execute freely
- **Tier 2 — Create (new resources)**: execute, report scope/cost first
- **Tier 3 — Modify/Delete existing**: approval required unless allowlisted
- **Tier 4 — Identity**: always approval, allowlist cannot exempt

---

## 1. Azure CLI (`az`) and Azure Developer CLI (`azd`)

### Tier 1 — Safe

| Pattern | Notes |
|---------|-------|
| `az * list`, `az * show`, `az * get-*` | All read verbs |
| `az account show/list/get-access-token` | |
| `az deployment * what-if`, `az deployment * validate` | Preview only |
| `az group exists`, `az * check-name` | |
| `az graph query` | Resource Graph (read-only KQL) |
| `az monitor * list/show`, `az monitor metrics list` | |
| `az ad user/group/app/sp list`, `az ad * show` | Identity **reads** are Tier 1 |
| `azd provision --preview`, `azd env list`, `azd show`, `azd config show` | |
| `az rest --method get`, `az rest` with no `--method` (defaults to GET) | |
| `az login`, `az account set` | Session state only, no resource changes |

### Tier 2 — Create

| Pattern | Notes |
|---------|-------|
| `az * create` | **Only when the target does not already exist.** Many `create` commands are upserts (e.g., `az webapp config appsettings set`-like behavior, `az deployment group create`) — if the target exists, treat as Tier 3 |
| `az group create` | New resource group |
| `az deployment group/sub/mg/tenant create` | Tier 2 only if what-if shows no Modify/Delete on existing resources; otherwise Tier 3 |
| `azd provision`, `azd up` | Tier 2 for fresh environments; Tier 3 if it modifies existing infrastructure |

### Tier 3 — Modify / Delete existing

| Pattern | Notes |
|---------|-------|
| `az * delete`, `az * purge` | All delete verbs, including soft-delete purge |
| `az * update`, `az * set`, `az * import`, `az * recover`, `az * restore` | |
| `az * start`, `az * stop`, `az * restart`, `az * deallocate` | Service interruption = modification |
| `az * scale`, `az * resize` | |
| `az tag create/update/delete` | Tags on existing resources |
| `az lock create/delete` | |
| `az policy assignment create/delete` | Governance changes |
| `az keyvault secret/key/certificate set/delete/purge/recover` | Data-plane writes |
| `az storage blob/container delete/upload/set-*` | Data-plane writes to existing accounts |
| `az rest --method put/patch/delete/post` | POST to action endpoints (e.g., `/restart`) is Tier 3 |
| `azd down` | Deletes the whole environment |
| `azd deploy` | Replaces running application code |

### Tier 4 — Identity

| Pattern | Notes |
|---------|-------|
| `az ad user create/update/delete` | |
| `az ad group create/update/delete`, `az ad group member add/remove` | |
| `az ad app create/update/delete/permission *`, `az ad app credential *` | |
| `az ad sp create*/update/delete/credential *` | |
| `az role assignment create/delete/update` | |
| `az role definition create/update/delete` | |
| `az keyvault set-policy`, `az keyvault delete-policy` | Access policy = authorization change |
| `az rest` targeting `graph.microsoft.com` with PUT/PATCH/DELETE/POST | |

---

## 2. Azure PowerShell (`Az` module)

Classification follows the **verb** of the cmdlet:

| Verb pattern | Tier | Notes |
|--------------|------|-------|
| `Get-Az*`, `Test-Az*`, `Measure-Az*`, `Find-Az*`, `Search-Az*` | 1 | |
| `Get-AzResourceGroupDeploymentWhatIfResult`, `New-Az*Deployment -WhatIf` | 1 | Preview |
| `Connect-AzAccount`, `Set-AzContext`, `Select-AzSubscription` | 1 | Session only |
| `New-Az*` | 2 | Only when the target is genuinely new; upserts to existing resources are Tier 3 |
| `Set-Az*`, `Update-Az*`, `Remove-Az*`, `Clear-Az*` | 3 | |
| `Start-Az*`, `Stop-Az*`, `Restart-Az*` | 3 | |
| `Move-Az*`, `Import-Az*`, `Restore-Az*`, `Undo-Az*` | 3 | |
| `Invoke-AzRestMethod -Method GET` | 1 | |
| `Invoke-AzRestMethod -Method PUT/PATCH/DELETE/POST` | 3 (4 if Graph identity endpoint) | |
| `New-AzRoleAssignment`, `Remove-AzRoleAssignment`, `New-AzADUser`, `Set-AzADUser`, `Remove-AzADUser`, `*-AzADGroup*`, `*-AzADApp*`, `*-AzADServicePrincipal*` (except `Get-`) | 4 | |

### Microsoft Graph PowerShell (`Mg` cmdlets)

| Verb pattern | Tier |
|--------------|------|
| `Get-Mg*` | 1 |
| `New-Mg*`, `Update-Mg*`, `Set-Mg*`, `Remove-Mg*`, `Invoke-Mg*` (write) | 4 — all Graph writes are identity-adjacent; treat as Tier 4 |
| `Invoke-MgGraphRequest -Method GET` | 1 |
| `Invoke-MgGraphRequest` with PUT/PATCH/DELETE/POST | 4 |

---

## 3. Azure MCP Server tools

MCP tools are namespaced `mcp__Azure_MCP_Server__<area>`. Most areas expose multiple operations selected by parameters (`command`, `operation`, `intent`, etc.) — classify by the **operation requested**, not just the tool name.

### Tier 1 — always safe tool areas

`documentation`, `pricing`, `bicepschema`, `azureterraformbestpractices`, `get_azure_bestpractices`, `cloudarchitect`, `wellarchitectedframework`, `marketplace`, `quota` (read), `resourcehealth` (read), `subscription_list`, `group_list`, `group_resource_list`, `advisor`, `applens`, `extension_azqr`, `extension_cli_generate`

### Parameter-dependent tool areas

For areas like `storage`, `keyvault`, `cosmos`, `sql`, `aks`, `appservice`, `containerapps`, `monitor`, `kusto`, `postgres`, `mysql`, `redis`, `servicebus`, `eventhubs`, `eventgrid`, `signalr`, `search`, `functionapp`, `compute`, `acr`, `appconfig`, `fileshares`, `foundry`, `grafana`, `loadtesting`, `workbooks`:

| Operation keyword in parameters | Tier |
|--------------------------------|------|
| `list`, `get`, `show`, `query`, `describe`, `read` | 1 |
| `create` (new resource) | 2 |
| `create-or-update`, `set`, `update`, `delete`, `remove`, `purge`, `start`, `stop`, `restart`, `scale`, `upload`, `import` | 3 |

### Tier 3 — inherently mutating tool areas

`deploy` (deploys/changes infrastructure), `azd` (when invoking `azd down`/`deploy`/`provision` against existing environments), `extension_cli_install` (installs software)

### Tier 4 — identity tool areas

`role` (role assignments/definitions when writing; reads are Tier 1), `keyvault` access-policy operations, any `communication`/`entra` user management operations

---

## 4. Entra ID / Microsoft Graph (raw API)

For raw HTTP calls (curl to `graph.microsoft.com`, `az rest`, SDK calls):

| Endpoint + method | Tier |
|-------------------|------|
| `GET /users`, `GET /groups`, `GET /applications`, `GET /servicePrincipals` | 1 |
| Any `POST/PATCH/PUT/DELETE` on `/users`, `/groups`, `/applications`, `/servicePrincipals`, `/directoryRoles`, `/roleManagement`, `/policies`, `/domains`, `/invitations` | 4 |
| `POST /users/{id}/revokeSignInSessions`, password reset, license assignment | 4 |

---

## Worked Examples

| Command | Tier | Why |
|---------|------|-----|
| `az vm list -o table` | 1 | Read-only |
| `az storage account create -n newacct -g rg-dev` | 2 | New resource (after confirming `newacct` doesn't exist) |
| `az webapp config appsettings set -g rg-prod -n app1 --settings K=V` | 3 | Modifies an existing app |
| `az group delete -n rg-old` | 3 | Deletes existing resources |
| `azd down --purge` | 3 | Deletes environment + purges soft-deleted resources |
| `Get-AzADUser -Filter "..."` | 1 | Identity read |
| `az ad user update --id x --account-enabled false` | 4 | Disables a user account |
| `az role assignment create --assignee x --role Contributor` | 4 | Grants privileges |
| `az deployment group create -f main.bicep` (what-if shows 2 Modify) | 3 | Touches existing resources |
