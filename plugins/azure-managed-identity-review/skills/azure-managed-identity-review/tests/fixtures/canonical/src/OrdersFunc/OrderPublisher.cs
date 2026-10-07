using Azure.Identity;
using Azure.Messaging.ServiceBus;

public sealed class OrderPublisher
{
    // Runs as the developer locally and as the Function App's identity in Azure.
    private readonly ServiceBusClient _client = new("sb-orders.servicebus.windows.net", new DefaultAzureCredential());
}
