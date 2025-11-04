using System.Text.Json;
using Confluent.Kafka;
using Microsoft.EntityFrameworkCore;
using PeakPro.Infrastructure;
using PeakPro.Domain.Outbox;

namespace PeakPro.Infrastructure.Outbox;

/// <summary>
/// Background service that polls outbox_events table and publishes to Kafka
/// Provides at-least-once delivery guarantee with retry logic
/// </summary>
public class OutboxPublisher : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<OutboxPublisher> _logger;
    private readonly IProducer<string, string> _producer;
    private readonly string _topic;
    private readonly int _pollIntervalSeconds;
    private readonly int _batchSize;
    private readonly int _maxRetries;

    public OutboxPublisher(
        IServiceProvider serviceProvider,
        ILogger<OutboxPublisher> logger,
        IConfiguration configuration)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;

        // Kafka configuration
        var brokers = configuration["Kafka:Brokers"] ?? "kafka:9092";
        _topic = configuration["Kafka:OutboxTopic"] ?? "aetherlink.events";
        _pollIntervalSeconds = int.Parse(configuration["Kafka:PollIntervalSeconds"] ?? "5");
        _batchSize = int.Parse(configuration["Kafka:BatchSize"] ?? "100");
        _maxRetries = int.Parse(configuration["Kafka:MaxRetries"] ?? "5");

        // Create Kafka producer with idempotence
        var producerConfig = new ProducerConfig
        {
            BootstrapServers = brokers,
            EnableIdempotence = true,
            Acks = Acks.All,
            MaxInFlight = 5,
            MessageSendMaxRetries = 10,
            RetryBackoffMs = 100,
        };

        _producer = new ProducerBuilder<string, string>(producerConfig).Build();

        _logger.LogInformation(
            "OutboxPublisher initialized: Brokers={Brokers}, Topic={Topic}, PollInterval={PollInterval}s, BatchSize={BatchSize}",
            brokers, _topic, _pollIntervalSeconds, _batchSize);
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("OutboxPublisher started");

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await PublishBatchAsync(stoppingToken);

                // Wait before next poll (shorter if events were published)
                var delay = TimeSpan.FromSeconds(_pollIntervalSeconds);
                await Task.Delay(delay, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                // Expected during shutdown
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in OutboxPublisher loop");
                await Task.Delay(TimeSpan.FromSeconds(10), stoppingToken);
            }
        }

        _logger.LogInformation("OutboxPublisher stopped");
    }

    private async Task PublishBatchAsync(CancellationToken cancellationToken)
    {
        using var scope = _serviceProvider.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<AppDbContext>();

        // Get unpublished events ordered by occurrence time
        var events = await dbContext.OutboxEvents
            .Where(e => e.PublishedAt == null && e.RetryCount < _maxRetries)
            .OrderBy(e => e.OccurredAt)
            .Take(_batchSize)
            .ToListAsync(cancellationToken);

        if (events.Count == 0)
        {
            return;
        }

        _logger.LogDebug("Publishing {Count} outbox events", events.Count);

        foreach (var evt in events)
        {
            try
            {
                // Publish to Kafka
                var message = new Message<string, string>
                {
                    Key = evt.Type,  // Partition by event type
                    Value = evt.Payload,
                    Headers = new Headers
                    {
                        { "event_id", BitConverter.GetBytes(evt.Id) },
                        { "tenant_id", evt.TenantId.ToByteArray() },
                        { "event_type", System.Text.Encoding.UTF8.GetBytes(evt.Type) },
                        { "occurred_at", System.Text.Encoding.UTF8.GetBytes(evt.OccurredAt.ToString("O")) },
                    }
                };

                var result = await _producer.ProduceAsync(_topic, message, cancellationToken);

                _logger.LogDebug(
                    "Published event {EventId} ({EventType}) to {Topic}:{Partition}@{Offset}",
                    evt.Id, evt.Type, result.Topic, result.Partition.Value, result.Offset.Value);

                // Mark as published
                evt.PublishedAt = DateTimeOffset.UtcNow;
                evt.LastError = null;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to publish event {EventId} ({EventType})", evt.Id, evt.Type);

                // Increment retry count and store error
                evt.RetryCount++;
                evt.LastError = ex.Message;

                if (evt.RetryCount >= _maxRetries)
                {
                    _logger.LogWarning(
                        "Event {EventId} ({EventType}) exceeded max retries ({MaxRetries}), marking as failed",
                        evt.Id, evt.Type, _maxRetries);
                }
            }
        }

        // Save changes (mark as published or increment retry count)
        await dbContext.SaveChangesAsync(cancellationToken);

        _logger.LogInformation(
            "Published {PublishedCount}/{TotalCount} outbox events",
            events.Count(e => e.PublishedAt != null),
            events.Count);
    }

    public override void Dispose()
    {
        _producer?.Dispose();
        base.Dispose();
    }
}
