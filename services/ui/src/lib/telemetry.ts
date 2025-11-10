// services/ui/src/lib/telemetry.ts
// Phase XX M11: Frontend telemetry for timeline degradation events

export async function sendFrontendTelemetry(payload: {
  component: string;
  event: string;
  tenant?: string | null;
}) {
  try {
    await fetch("http://localhost:8000/ops/telemetry/frontend", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        component: payload.component,
        event: payload.event,
        tenant: payload.tenant ?? "unknown",
      }),
    });
  } catch (err) {
    // swallow — telemetry should never break UI
    console.warn("[telemetry] failed to send", err);
  }
}
