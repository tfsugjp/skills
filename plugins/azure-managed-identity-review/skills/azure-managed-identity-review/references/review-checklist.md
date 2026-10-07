# Review checklist

What to check by hand after `msi_review.py` has run, and how to confirm grants after deployment. Replace `<...>` placeholders with your values.

## 1. Decide on every shared identity (MIR001, MIR003, MIR004)

For each identity with more than one consumer or a federated credential, write down in the pull request:

- each consumer and what it uses the identity for (the "Uses it for" column);
- which grants each consumer needs (the "Needed by" column); a grant needed by one consumer is still usable by all of them;
- each federated credential's issuer and subject, and whether that external workload may hold **every** grant on the identity.

Sharing is acceptable when the consumers are one workload (for example an app and its deployment slots) and need the same rights. Otherwise split the identity: one identity per purpose costs nothing and keeps each grant's audience obvious.

## 2. Close every MIR002 and MIR005 in IaC

- Grant the least-privileged **data** role on the target resource (not the resource group). Owner and Contributor do not grant data access.
- Grant it to the identity the consumer actually uses. For Functions connections that is `<PREFIX>__clientId`; without it, the system-assigned identity.
- Set the client ID explicitly whenever a resource has more than one identity, including `keyVaultReferenceIdentity` for Key Vault references.

## 3. Check non-RBAC grants (MIR006)

| Target | What to check |
| --- | --- |
| Azure SQL | A contained user exists for the identity (`CREATE USER [<identity-name>] FROM EXTERNAL PROVIDER`) with the needed database roles. Check `sys.database_principals` for type `E` (external user). |
| Cosmos DB (NoSQL) | A data-plane role assignment exists for the identity's principal ID: `az cosmosdb sql role assignment list --account-name <account> --resource-group <rg>`. Azure RBAC roles such as Contributor do not grant data access. |
| Microsoft Graph, custom APIs | The identity's service principal has the app role assignment the code needs (an admin grants it in Entra ID). Delegated (OBO) flows need the app registration's consent instead. |
| Key Vault with access policies | The vault's access policy lists the identity's principal ID with the needed secret/key permissions. |

## 4. Verify after deployment (MIR007)

Local runs authenticate as the developer, so a passing local E2E proves nothing about the deployed identity. Do not widen the developer's own rights to make local runs pass.

1. Deploy to a test environment with the same identities and grants as production.
2. Exercise every target of every consumer (one smoke call per target is enough). Watch for 401/403 such as `AuthorizationPermissionMismatch` (Storage) or `Unauthorized access` (Service Bus) in the app's logs.
3. Run the live review against the test subscription and compare it with IaC:

   ```bash
   python3 scripts/msi_review.py live --subscription <subscription-id> --resource <resource-name> --static <infra-dir>
   ```

   MIR008 findings show grants or attachments someone added by hand to make it work.
4. Role assignments can take several minutes to apply; retry once before treating a 403 as a missing grant.
