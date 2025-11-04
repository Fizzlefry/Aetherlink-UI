namespace PeakPro.Domain.Idempotency;

/// <summary>
/// Idempotency key for preventing duplicate webhook/command processing
/// Each key is associated with a tenant and cached for 24 hours
/// </summary>
public class IdempotencyKey
{
    public long Id { get; set; }

    /// <summary>
    /// Tenant identifier
    /// </summary>
    public Guid TenantId { get; set; }

    /// <summary>
    /// Idempotency key from request header (e.g., UUID)
    /// </summary>
    public string Key { get; set; } = string.Empty;

    /// <summary>
    /// HTTP request path
    /// </summary>
    public string RequestPath { get; set; } = string.Empty;

    /// <summary>
    /// HTTP request method
    /// </summary>
    public string RequestMethod { get; set; } = string.Empty;

    /// <summary>
    /// HTTP response status code
    /// </summary>
    public int StatusCode { get; set; }

    /// <summary>
    /// HTTP response body (cached)
    /// </summary>
    public string? ResponseBody { get; set; }

    /// <summary>
    /// When the key was created
    /// </summary>
    public DateTime CreatedAt { get; set; }

    /// <summary>
    /// When the key expires (CreatedAt + 24h)
    /// </summary>
    public DateTime ExpiresAt { get; set; }
}
