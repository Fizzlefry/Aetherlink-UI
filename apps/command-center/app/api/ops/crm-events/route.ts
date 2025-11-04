// Stream-proxy for CRM events SSE → avoids CORS & keeps cookies/scopes local
import type { NextRequest } from "next/server";

const TARGET =
    process.env.CRM_EVENTS_URL?.replace(/\/$/, "") ||
    "http://crm-events:9010";

export const runtime = "nodejs"; // ensure Edge doesn't clip streams
export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest) {
    const controller = new AbortController();
    const res = await fetch(`${TARGET}/crm-events`, {
        signal: controller.signal,
        headers: { Accept: "text/event-stream" },
    });

    if (!res.ok || !res.body) {
        controller.abort();
        return new Response(
            JSON.stringify({ ok: false, status: res.status }),
            { status: 502, headers: { "content-type": "application/json" } }
        );
    }

    // Pipe upstream SSE to client
    const { readable, writable } = new TransformStream();
    void (async () => {
        const writer = writable.getWriter();
        const reader = res.body.getReader();
        try {
            for (; ;) {
                const { done, value } = await reader.read();
                if (done) break;
                await writer.write(value);
            }
        } catch {
            // ignore disconnects
        } finally {
            try { await writer.close(); } catch { }
            controller.abort();
        }
    })();

    return new Response(readable, {
        status: 200,
        headers: {
            "content-type": "text/event-stream; charset=utf-8",
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no", // nginx
            connection: "keep-alive",
        },
    });
}
