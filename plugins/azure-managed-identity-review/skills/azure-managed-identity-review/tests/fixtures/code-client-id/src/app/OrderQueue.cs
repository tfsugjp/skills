using Azure.Identity;
using Azure.Storage.Queues;

public sealed class OrderQueue
{
    // The identity is chosen in code, not through AZURE_CLIENT_ID.
    private readonly QueueClient _queue = new(
        new Uri("https://stcode001.queue.core.windows.net/orders"),
        new ManagedIdentityCredential(Environment.GetEnvironmentVariable("ORDERS_CLIENT_ID")));
}
