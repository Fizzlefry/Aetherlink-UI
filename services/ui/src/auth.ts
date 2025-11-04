/**
 * Extract tenant_id from JWT access token.
 * Performs lightweight client-side decode (no verification needed in browser).
 */
export function getTenantFromToken(token: string | undefined): string | null {
    if (!token) return null;

    try {
        const [, payloadBase64] = token.split(".");
        if (!payloadBase64) return null;

        const payload = JSON.parse(atob(payloadBase64));
        return payload["tenant_id"] || payload["tenant"] || null;
    } catch (err) {
        console.error("Failed to decode token:", err);
        return null;
    }
}
