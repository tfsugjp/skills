# Audiences, identities, and grants

How `msi_review.py` decides what each consumer reaches, which identity it uses, and which grant satisfies it. Role names and IDs were checked against `az role definition list` (built-in roles).

## Which identity a consumer uses

| Where | Identity used | Source |
| --- | --- | --- |
| Functions identity-based connection `<PREFIX>__credential=managedidentity` | `<PREFIX>__clientId` or `<PREFIX>__managedIdentityResourceId`; **system-assigned when neither is set** | [Functions connections](https://learn.microsoft.com/azure/azure-functions/functions-reference#configure-an-identity-based-connection) |
| Connection settings without `__credential` (for example `AzureWebJobsStorage__accountName`) | System-assigned in Azure; the developer's identity locally | same |
| SDK code with `DefaultAzureCredential` | `AZURE_CLIENT_ID` if set, otherwise system-assigned in Azure; the developer locally | [Azure Identity](https://learn.microsoft.com/dotnet/api/overview/azure/identity-readme) |
| `ManagedIdentityCredential()` with no client ID | System-assigned | same |
| `ManagedIdentityCredential(<client ID>)`, `ManagedIdentityClientId`, `managed_identity_client_id`, `FromUserAssignedClientId(...)` in code | The identity whose client ID the code passes; a value read from an environment variable or configuration key is resolved through that app setting | same |
| App Service / Functions Key Vault reference (`@Microsoft.KeyVault(...)`) | `keyVaultReferenceIdentity` (`key_vault_reference_identity_id`); system-assigned by default | [Key Vault references](https://learn.microsoft.com/azure/app-service/app-service-key-vault-references) |
| Container Apps Key Vault secret | `configuration.secrets[].identity` (`secret.identity`) | |
| Storage customer-managed key | `encryption.identity.userAssignedIdentity` (`customer_managed_key.user_assigned_identity_id`) | |
| Image pull | `siteConfig.acrUserManagedIdentityID`, `configuration.registries[].identity`, AKS kubelet identity | |
| Federated identity credential | The external workload whose issuer and subject match acts as the identity | [FIC considerations](https://learn.microsoft.com/entra/workload-id/workload-identity-federation-considerations) |

A consumer is any resource whose `identity.userAssignedIdentities` (`identity_ids`) lists the identity, or that references it in another property (the slots above). Any other property that references the identity is reported as a consumer slot with its property path.

## Which target a consumer reaches

| Evidence | Example | Service |
| --- | --- | --- |
| Connection property | `__blobServiceUri`, `__queueServiceUri`, `__tableServiceUri`, `__accountName` | Storage (blob / queue / table / any) |
| | `__fullyQualifiedNamespace` | Service Bus (Event Hubs when the prefix contains `eventhub`) |
| | `__accountEndpoint` | Cosmos DB |
| | `__endpoint`, `__serviceUri` | From the host name |
| Setting value that references a resource in IaC | `storage.properties.primaryEndpoints.blob`, `azurerm_storage_account.x.primary_blob_endpoint` | From the resource type |
| Host name in a value or in code | `*.blob.*`, `*.vault.azure.net`, `*.servicebus.windows.net`, `*.documents.azure.com`, `*.database.windows.net`, `*.azconfig.io`, `*.openai.azure.com`, `*.azurecr.io`, `*.search.windows.net` | By host |
| Token scope in code | `https://storage.azure.com/.default`, `https://vault.azure.net/.default`, `https://servicebus.azure.net/.default`, `https://eventhubs.azure.net/.default`, `https://database.windows.net/.default`, `https://cosmos.azure.com/.default`, `https://cognitiveservices.azure.com/.default`, `https://graph.microsoft.com/.default`, `api://<app>/.default` | By scope |

Targets found only from a URL or from code are marked as inferred: the app might use a key or SAS instead of Entra ID, so MIR002 is a warning, not an error.

## Which grant satisfies a target

| Service | Grants that count | Notes |
| --- | --- | --- |
| Blob Storage | Storage Blob Data Owner / Contributor / Reader | Functions host storage also needs queue and table roles for some triggers. |
| Queue Storage | Storage Queue Data Contributor / Reader / Message Sender / Message Processor | |
| Table Storage | Storage Table Data Contributor / Reader | |
| Azure Files | Storage File Data Privileged Contributor / Reader, SMB Share Contributor / Reader | |
| Key Vault secrets (Key Vault references, Container Apps secrets) | Key Vault Administrator, Secrets Officer, Secrets User, Certificate User; or an access policy when the vault does not use RBAC | Key Vault Reader and the crypto roles cannot read secrets. |
| Key Vault keys (customer-managed keys) | Key Vault Administrator, Crypto Officer, Crypto User, Crypto Service Encryption User; or an access policy | Secrets roles cannot wrap or unwrap keys. |
| Key Vault (endpoint or token scope in code) | Any of the roles above | The operation is unknown, so any Key Vault data role counts. |
| Service Bus | Azure Service Bus Data Owner / Sender / Receiver | |
| Event Hubs | Azure Event Hubs Data Owner / Sender / Receiver | |
| App Configuration | App Configuration Data Owner / Reader | |
| Azure OpenAI / AI services | Cognitive Services OpenAI User / Contributor, Cognitive Services User, Azure AI Developer, Foundry User | |
| Container Registry | AcrPull, AcrPush, Container Registry Repository Reader / Writer | |
| Azure AI Search | Search Index Data Reader / Contributor | |
| SignalR | SignalR App Server, SignalR Service Owner | |
| Event Grid | EventGrid Data Sender | |
| Cosmos DB | Cosmos DB SQL role assignment (data plane), for example Built-in Data Contributor | Not Azure RBAC. Covered when IaC or live state shows `sqlRoleAssignments` for the identity; otherwise MIR006. |
| Azure SQL | Contained database user and database roles | Always MIR006: not visible in ARM. |
| Microsoft Graph, custom APIs | App role assignment on the API's service principal | Always MIR006. |

Owner, Contributor, and other control-plane roles do not grant data access, so they never satisfy a data target; on a shared identity they are reported by MIR003. A grant covers a target when its scope is the target resource, or a resource group, subscription, or management group. When the resource groups of both the grant and the target are known (Terraform, literal resource IDs, live mode), they must match; otherwise containment cannot be proved, so broader scopes count as covering and are reported by MIR003 instead. A grant whose scope cannot be resolved (for example `var.scope`) never counts and is reported as MIR000. A grant on a child of the target (a blob container, queue, secret, or Service Bus queue) counts only for that child: when it is the only grant, MIR002 reports a warning so the reviewer confirms the consumer uses nothing else.

Target names come from the setting value, the `VaultName=` or `SecretUri=` of a Key Vault reference, a registry's login server, or a customer-managed key's vault. When no name can be found, any grant of the right role counts.
