// PeakPro CRM - Outbox Publisher (Background Service)
// Polls unpublished events → Kafka with at-least-once delivery

using Confluent.Kafka;
using System.Text.Json;

namespace PeakPro.Infrastructure.Outbox;

public class OutboxPublisherService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<OutboxPublisherService> _logger;
    private readonly IConfiguration _config;
    private IProducer<string, string>? _producer;

    public OutboxPublisherService(
        IServiceProvider serviceProvider,
        ILogger<OutboxPublisherService> logger,
        IConfiguration config)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _config = config;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("OutboxPublisherService starting...");

        // Kafka producer config
        var producerConfig = new ProducerConfig
        {
            BootstrapServers = _config["KAFKA_BOOTSTRAP_SERVERS"] ?? "localhost:9092",
            ClientId = $"peakpro-outbox-publisher-{Environment.MachineName}",
            Acks = Acks.All,  // Wait for all replicas (durability)
            EnableIdempotence = true,  // Prevent duplicates on retry
            MaxInFlight = 5,
            MessageSendMaxRetries = 10,
            RetryBackoffMs = 100
        };

        _producer = new ProducerBuilder<string, string>(producerConfig).Build();

        try
        {
            while (!stoppingToken.IsCancellationRequested)
            {
                await PublishBatchAsync(stoppingToken);
                await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);  // Poll every 5s
            }
        }
        catch (OperationCanceledException)
        {
            _logger.LogInformation("OutboxPublisherService stopping...");
        }
        finally
        {
            _producer?.Dispose();
        }
    }

    private async Task PublishBatchAsync(CancellationToken ct)
    {
        using var scope = _serviceProvider.CreateScope();
        var outbox = scope.ServiceProvider.GetRequiredService<IOutboxRepository>();

        var events = await outbox.GetUnpublishedAsync(batchSize: 100, ct);
        if (events.Count == 0) return;

        _logger.LogDebug("Publishing {Count} outbox events", events.Count);

        foreach (var evt in events)
        {
            try
            {
                var topic = $"aetherlink.events.{evt.EventType.ToLowerInvariant()}";
                var message = new Message<string, string>
                {
                    Key = evt.EventId.ToString(),  // Partition by event ID
                    Value = evt.Payload,
                    Headers = new Headers
                    {
                        { "event_id", System.Text.Encoding.UTF8.GetBytes(evt.EventId.ToString()) },
                        { "tenant_id", System.Text.Encoding.UTF8.GetBytes(evt.TenantId.ToString()) },
                        { "event_type", System.Text.Encoding.UTF8.GetBytes(evt.EventType) },
                        { "occurred_at", System.Text.Encoding.UTF8.GetBytes(evt.OccurredAt.ToString("O")) }
                    }
                };

                var result = await _producer!.ProduceAsync(topic, message, ct);

                _logger.LogDebug(
                    "Published event {EventId} ({EventType}) to {Topic} partition {Partition} offset {Offset}",
                    evt.EventId, evt.EventType, topic, result.Partition.Value, result.Offset.Value
                );

                await outbox.MarkAsPublishedAsync(evt.Id, ct);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to publish event {EventId} ({EventType})", evt.EventId, evt.EventType);
                await outbox.MarkAsFailedAsync(evt.Id, ex.Message, ct);
            }
        }
    }

    public override void Dispose()
    {
        _producer?.Dispose();
        base.Dispose();
    }
}

// ============================================================================
// REGISTRATION (Program.cs)
// ============================================================================

/*
// Add Kafka client package:
// dotnet add package Confluent.Kafka

// Register in DI:
builder.Services.AddHostedService<OutboxPublisherService>();

// Environment variables:
// KAFKA_BOOTSTRAP_SERVERS=localhost:9092
*/
