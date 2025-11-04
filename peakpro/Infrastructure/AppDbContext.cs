using Microsoft.EntityFrameworkCore;
using PeakPro.Domain.Outbox;
using PeakPro.Domain.Idempotency;

namespace PeakPro.Infrastructure;

/// <summary>
/// Main application database context for PeakPro CRM
/// Includes: Outbox pattern for event publishing, Idempotency for duplicate prevention
/// </summary>
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }

    // Domain entities
    public DbSet<Job> Jobs { get; set; } = default!;
    public DbSet<Account> Accounts { get; set; } = default!;
    public DbSet<Contact> Contacts { get; set; } = default!;

    // Infrastructure entities
    public DbSet<OutboxEvent> OutboxEvents { get; set; } = default!;
    public DbSet<IdempotencyKey> IdempotencyKeys { get; set; } = default!;

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Outbox Events (for transactional event publishing)
        modelBuilder.Entity<OutboxEvent>(entity =>
        {
            entity.ToTable("outbox_events");
            entity.HasKey(e => e.Id);

            // Index for unpublished events (publisher query)
            entity.HasIndex(e => new { e.PublishedAt, e.OccurredAt })
                .HasDatabaseName("IX_outbox_events_published_occurred");

            // Index for tenant filtering
            entity.HasIndex(e => e.TenantId)
                .HasDatabaseName("IX_outbox_events_tenant");

            entity.Property(e => e.Type)
                .HasMaxLength(200)
                .IsRequired();

            entity.Property(e => e.Payload)
                .HasColumnType("jsonb")  // PostgreSQL JSONB
                .IsRequired();

            entity.Property(e => e.OccurredAt)
                .IsRequired();

            entity.Property(e => e.RetryCount)
                .HasDefaultValue(0);
        });

        // Idempotency Keys (for duplicate prevention)
        modelBuilder.Entity<IdempotencyKey>(entity =>
        {
            entity.ToTable("idempotency_keys");
            entity.HasKey(e => e.Id);

            // Unique constraint on tenant + key
            entity.HasIndex(e => new { e.TenantId, e.Key })
                .IsUnique()
                .HasDatabaseName("IX_idempotency_keys_tenant_key");

            // Index for expiration cleanup
            entity.HasIndex(e => e.ExpiresAt)
                .HasDatabaseName("IX_idempotency_keys_expires");

            entity.Property(e => e.Key)
                .HasMaxLength(200)
                .IsRequired();

            entity.Property(e => e.RequestPath)
                .HasMaxLength(500)
                .IsRequired();

            entity.Property(e => e.RequestMethod)
                .HasMaxLength(10)
                .IsRequired();

            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("now()");

            // Automatically set ExpiresAt = CreatedAt + 24h
            // (Can be done via migration trigger or application code)
        });

        base.OnModelCreating(modelBuilder);
    }
}

// Placeholder entity types (replace with actual domain models)
public class Job
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public string Title { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
}

public class Account
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public string Name { get; set; } = string.Empty;
}

public class Contact
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
}
