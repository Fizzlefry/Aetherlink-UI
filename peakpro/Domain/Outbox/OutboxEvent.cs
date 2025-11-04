namespace PeakPro.Domain.Outbox;

/// <summary>
/// Outbox event for transactional event publishing
/// Events are written to the outbox table in the same transaction as business data
/// Background service polls this table and publishes to Kafka
/// </summary>
public class OutboxEvent
{
    public long Id { get; set; }

    /// <summary>
    /// Tenant identifier for multi-tenant isolation
    /// </summary>
    public Guid TenantId { get; set; }

    /// <summary>
    /// Event type (e.g., "JobCreated", "ContactCreated")
    /// </summary>
    public string Type { get; set; } = string.Empty;

    /// <summary>
    /// JSON payload containing event data
    /// </summary>
    public string Payload { get; set; } = string.Empty;    /// <summary>
                                                           /// When the domain event occurred
                                                           /// </summary>
    public DateTimeOffset OccurredAt { get; set; }

    /// <summary>
    /// When the event was successfully published to Kafka
    /// NULL = not yet published
    /// </summary>
    public DateTimeOffset? PublishedAt { get; set; }

    /// <summary>
    /// Number of times publication was attempted
    /// </summary>
    public int RetryCount { get; set; }

    /// <summary>
    /// Last error message if publication failed
    /// </summary>
    public string? LastError { get; set; }
}
