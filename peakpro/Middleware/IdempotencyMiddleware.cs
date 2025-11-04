// PeakPro CRM - Idempotency Middleware
// Prevents duplicate webhook/command processing via Idempotency-Key header

using System.Security.Cryptography;
using System.Text;
using Microsoft.EntityFrameworkCore;

namespace PeakPro.Middleware;

// ============================================================================
// IDEMPOTENCY KEY ENTITY
// ============================================================================

public class IdempotencyKey
{
    public long Id { get; set; }
    public string Key { get; set; } = default!;
    public Guid TenantId { get; set; }
    public string RequestPath { get; set; } = default!;
    public string RequestMethod { get; set; } = default!;
    public int StatusCode { get; set; }
    public string? ResponseBody { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset ExpiresAt { get; set; }
}

// ============================================================================
// IDEMPOTENCY MIDDLEWARE
// ============================================================================

public class IdempotencyMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<IdempotencyMiddleware> _logger;

    public IdempotencyMiddleware(RequestDelegate next, ILogger<IdempotencyMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }

    public async Task InvokeAsync(HttpContext context, AppDbContext db)
    {
        // Only apply to POST/PUT/PATCH (mutating operations)
        if (context.Request.Method != "POST" &&
            context.Request.Method != "PUT" &&
            context.Request.Method != "PATCH")
        {
            await _next(context);
            return;
        }

        // Check for Idempotency-Key header
        if (!context.Request.Headers.TryGetValue("Idempotency-Key", out var keyValue) ||
            string.IsNullOrWhiteSpace(keyValue))
        {
            await _next(context);
            return;
        }

        var idempotencyKey = keyValue.ToString();
        var tenantId = GetTenantId(context);  // Extract from claims/headers

        // Check if key exists
        var existing = await db.IdempotencyKeys
            .FirstOrDefaultAsync(k =>
                k.Key == idempotencyKey &&
                k.TenantId == tenantId &&
                k.ExpiresAt > DateTimeOffset.UtcNow);

        if (existing != null)
        {
            _logger.LogInformation(
                "Duplicate request detected (Idempotency-Key: {Key}, Tenant: {TenantId})",
                idempotencyKey, tenantId
            );

            // Return cached response
            context.Response.StatusCode = existing.StatusCode;
            if (!string.IsNullOrEmpty(existing.ResponseBody))
            {
                context.Response.ContentType = "application/json";
                await context.Response.WriteAsync(existing.ResponseBody);
            }
            return;
        }

        // Capture response for caching
        var originalBodyStream = context.Response.Body;
        using var responseBody = new MemoryStream();
        context.Response.Body = responseBody;

        try
        {
            await _next(context);

            // Cache successful responses (2xx/3xx)
            if (context.Response.StatusCode >= 200 && context.Response.StatusCode < 400)
            {
                responseBody.Seek(0, SeekOrigin.Begin);
                var responseText = await new StreamReader(responseBody).ReadToEndAsync();

                var keyEntity = new IdempotencyKey
                {
                    Key = idempotencyKey,
                    TenantId = tenantId,
                    RequestPath = context.Request.Path,
                    RequestMethod = context.Request.Method,
                    StatusCode = context.Response.StatusCode,
                    ResponseBody = responseText,
                    CreatedAt = DateTimeOffset.UtcNow,
                    ExpiresAt = DateTimeOffset.UtcNow.AddHours(24)  // 24h TTL
                };

                db.IdempotencyKeys.Add(keyEntity);
                await db.SaveChangesAsync();

                _logger.LogDebug(
                    "Cached response for Idempotency-Key: {Key} (Tenant: {TenantId})",
                    idempotencyKey, tenantId
                );
            }

            // Copy response to original stream
            responseBody.Seek(0, SeekOrigin.Begin);
            await responseBody.CopyToAsync(originalBodyStream);
        }
        finally
        {
            context.Response.Body = originalBodyStream;
        }
    }

    private Guid GetTenantId(HttpContext context)
    {
        // Extract tenant ID from claims, headers, or route
        var tenantClaim = context.User.FindFirst("tenant_id")?.Value;
        if (Guid.TryParse(tenantClaim, out var tenantId))
        {
            return tenantId;
        }

        // Fallback: header
        if (context.Request.Headers.TryGetValue("X-Tenant-Id", out var headerValue) &&
            Guid.TryParse(headerValue, out var headerTenantId))
        {
            return headerTenantId;
        }

        // Default for dev
        return Guid.Empty;
    }
}

// ============================================================================
// EXTENSION METHOD
// ============================================================================

public static class IdempotencyMiddlewareExtensions
{
    public static IApplicationBuilder UseIdempotency(this IApplicationBuilder builder)
    {
        return builder.UseMiddleware<IdempotencyMiddleware>();
    }
}

// ============================================================================
// DB CONTEXT CONFIGURATION
// ============================================================================

public static class IdempotencyDbContextExtensions
{
    public static void ConfigureIdempotency(this ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<IdempotencyKey>(entity =>
        {
            entity.ToTable("idempotency_keys");
            entity.HasKey(e => e.Id);
            entity.HasIndex(e => new { e.Key, e.TenantId }).IsUnique();
            entity.HasIndex(e => e.ExpiresAt);  // For cleanup
            entity.Property(e => e.Key).HasMaxLength(256).IsRequired();
            entity.Property(e => e.RequestPath).HasMaxLength(500);
            entity.Property(e => e.RequestMethod).HasMaxLength(10);
        });
    }
}

// ============================================================================
// CLEANUP HOSTED SERVICE (optional)
// ============================================================================

public class IdempotencyCleanupService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<IdempotencyCleanupService> _logger;

    public IdempotencyCleanupService(
        IServiceProvider serviceProvider,
        ILogger<IdempotencyCleanupService> logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            await Task.Delay(TimeSpan.FromHours(1), stoppingToken);  // Cleanup hourly

            using var scope = _serviceProvider.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            var deleted = await db.IdempotencyKeys
                .Where(k => k.ExpiresAt < DateTimeOffset.UtcNow)
                .ExecuteDeleteAsync(stoppingToken);

            if (deleted > 0)
            {
                _logger.LogInformation("Deleted {Count} expired idempotency keys", deleted);
            }
        }
    }
}

// ============================================================================
// REGISTRATION (Program.cs)
// ============================================================================

/*
// Add to Program.cs:

// Configure DbContext
builder.Services.AddDbContext<AppDbContext>(options =>
{
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection"));
});

// Add middleware
app.UseIdempotency();

// Add cleanup service
builder.Services.AddHostedService<IdempotencyCleanupService>();

// Usage in API:
// POST /api/crm/jobs
// Headers:
//   Idempotency-Key: <uuid>
//   X-Tenant-Id: <tenant-guid>
*/
