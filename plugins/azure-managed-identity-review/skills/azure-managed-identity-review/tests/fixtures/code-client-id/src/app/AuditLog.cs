using Azure.Identity;
using Azure.Storage.Blobs;

public sealed class AuditLog
{
    private readonly BlobContainerClient _container = new(
        new Uri("https://staudit001.blob.core.windows.net/audit"),
        new DefaultAzureCredential(new DefaultAzureCredentialOptions { ManagedIdentityClientId = Environment.GetEnvironmentVariable("AUDIT_CLIENT_ID") }));
}
