// PeakPro CRM - Outbox Pattern Implementation
// Domain Events → Kafka via transactional outbox

using System.Text.Json;

namespace PeakPro.Domain.Events;

// ============================================================================
// DOMAIN EVENTS
// ============================================================================

public abstract record DomainEvent(Guid EventId, Guid TenantId, DateTimeOffset OccurredAt)
{
    public string EventType => GetType().Name;
}

public record ContactCreated(
    Guid EventId,
    Guid TenantId,
    DateTimeOffset OccurredAt,
    Guid ContactId,
    string Name,
    string Email
) : DomainEvent(EventId, TenantId, OccurredAt);

public record JobCreated(
    Guid EventId,
    Guid TenantId,
    DateTimeOffset OccurredAt,
    Guid JobId,
    Guid AccountId,
    string Title,
    string Status
) : DomainEvent(EventId, TenantId, OccurredAt);

public record JobStatusChanged(
    Guid EventId,
    Guid TenantId,
    DateTimeOffset OccurredAt,
    Guid JobId,
    string OldStatus,
    string NewStatus,
    string? ChangedBy
) : DomainEvent(EventId, TenantId, OccurredAt);

public record AccountCreated(
    Guid EventId,
    Guid TenantId,
    DateTimeOffset OccurredAt,
    Guid AccountId,
    string Name,
    string? Industry
) : DomainEvent(EventId, TenantId, OccurredAt);

// ============================================================================
// OUTBOX ENTITY
// ============================================================================

public class OutboxEvent
{
    public long Id { get; set; }
    public Guid EventId { get; set; }
    public Guid TenantId { get; set; }
    public string EventType { get; set; } = default!;
    public string Payload { get; set; } = default!;
    public DateTimeOffset OccurredAt { get; set; }
    public DateTimeOffset? PublishedAt { get; set; }
    public int RetryCount { get; set; }
    public string? LastError { get; set; }
}

// ============================================================================
// OUTBOX REPOSITORY
// ============================================================================

public interface IOutboxRepository
{
    Task AddAsync(OutboxEvent outboxEvent, CancellationToken ct = default);
    Task<List<OutboxEvent>> GetUnpublishedAsync(int batchSize = 100, CancellationToken ct = default);
    Task MarkAsPublishedAsync(long outboxEventId, CancellationToken ct = default);
    Task MarkAsFailedAsync(long outboxEventId, string error, CancellationToken ct = default);
}

public class OutboxRepository : IOutboxRepository
{
    private readonly AppDbContext _db;

    public OutboxRepository(AppDbContext db)
    {
        _db = db;
    }

    public async Task AddAsync(OutboxEvent outboxEvent, CancellationToken ct = default)
    {
        await _db.OutboxEvents.AddAsync(outboxEvent, ct);
        // Note: Caller must SaveChangesAsync() in same transaction
    }

    public async Task<List<OutboxEvent>> GetUnpublishedAsync(int batchSize = 100, CancellationToken ct = default)
    {
        return await _db.OutboxEvents
            .Where(e => e.PublishedAt == null && e.RetryCount < 5)
            .OrderBy(e => e.OccurredAt)
            .Take(batchSize)
            .ToListAsync(ct);
    }

    public async Task MarkAsPublishedAsync(long outboxEventId, CancellationToken ct = default)
    {
        var evt = await _db.OutboxEvents.FindAsync(new object[] { outboxEventId }, ct);
        if (evt != null)
        {
            evt.PublishedAt = DateTimeOffset.UtcNow;
            await _db.SaveChangesAsync(ct);
        }
    }

    public async Task MarkAsFailedAsync(long outboxEventId, string error, CancellationToken ct = default)
    {
        var evt = await _db.OutboxEvents.FindAsync(new object[] { outboxEventId }, ct);
        if (evt != null)
        {
            evt.RetryCount++;
            evt.LastError = error;
            await _db.SaveChangesAsync(ct);
        }
    }
}

// ============================================================================
// DOMAIN EVENT BUS (Transactional publishing)
// ============================================================================

public interface IDomainEventBus
{
    Task PublishAsync<TEvent>(TEvent domainEvent, CancellationToken ct = default) where TEvent : DomainEvent;
}

public class OutboxDomainEventBus : IDomainEventBus
{
    private readonly IOutboxRepository _outbox;

    public OutboxDomainEventBus(IOutboxRepository outbox)
    {
        _outbox = outbox;
    }

    public async Task PublishAsync<TEvent>(TEvent domainEvent, CancellationToken ct = default) where TEvent : DomainEvent
    {
        var outboxEvent = new OutboxEvent
        {
            EventId = domainEvent.EventId,
            TenantId = domainEvent.TenantId,
            EventType = domainEvent.EventType,
            Payload = JsonSerializer.Serialize(domainEvent, new JsonSerializerOptions
            {
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            }),
            OccurredAt = domainEvent.OccurredAt,
            RetryCount = 0
        };

        await _outbox.AddAsync(outboxEvent, ct);
        // Note: Caller must SaveChangesAsync() to commit transaction
    }
}

// ============================================================================
// EXAMPLE USAGE (Service Layer)
// ============================================================================

public class JobService
{
    private readonly AppDbContext _db;
    private readonly IDomainEventBus _eventBus;

    public JobService(AppDbContext db, IDomainEventBus eventBus)
    {
        _db = db;
        _eventBus = eventBus;
    }

    public async Task<Guid> CreateJobAsync(Guid tenantId, Guid accountId, string title, CancellationToken ct = default)
    {
        // 1. Create entity
        var job = new Job
        {
            Id = Guid.NewGuid(),
            TenantId = tenantId,
            AccountId = accountId,
            Title = title,
            Status = "Open",
            CreatedAt = DateTimeOffset.UtcNow
        };

        _db.Jobs.Add(job);

        // 2. Publish domain event (adds to outbox, same transaction)
        var evt = new JobCreated(
            EventId: Guid.NewGuid(),
            TenantId: tenantId,
            OccurredAt: DateTimeOffset.UtcNow,
            JobId: job.Id,
            AccountId: accountId,
            Title: title,
            Status: "Open"
        );

        await _eventBus.PublishAsync(evt, ct);

        // 3. Commit transaction (both job + outbox event atomically)
        await _db.SaveChangesAsync(ct);

        return job.Id;
    }

    public async Task UpdateJobStatusAsync(Guid jobId, string newStatus, string? changedBy, CancellationToken ct = default)
    {
        var job = await _db.Jobs.FindAsync(new object[] { jobId }, ct);
        if (job == null) throw new NotFoundException("Job not found");

        var oldStatus = job.Status;
        job.Status = newStatus;
        job.UpdatedAt = DateTimeOffset.UtcNow;

        var evt = new JobStatusChanged(
            EventId: Guid.NewGuid(),
            TenantId: job.TenantId,
            OccurredAt: DateTimeOffset.UtcNow,
            JobId: jobId,
            OldStatus: oldStatus,
            NewStatus: newStatus,
            ChangedBy: changedBy
        );

        await _eventBus.PublishAsync(evt, ct);
        await _db.SaveChangesAsync(ct);
    }
}

// ============================================================================
// DB CONTEXT CONFIGURATION
// ============================================================================
// NOTE: This AppDbContext is now defined in Infrastructure/AppDbContext.cs
// See that file for the complete DbContext configuration including:
// - OutboxEvents (for transactional event publishing)
// - IdempotencyKeys (for duplicate prevention)
// - Job, Account, Contact entities

// ============================================================================
// DEPENDENCY INJECTION
// ============================================================================

// Add to Program.cs or Startup.cs:
// builder.Services.AddScoped<IOutboxRepository, OutboxRepository>();
// builder.Services.AddScoped<IDomainEventBus, OutboxDomainEventBus>();
// builder.Services.AddHostedService<OutboxPublisherService>();
