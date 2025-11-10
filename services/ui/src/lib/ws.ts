export function makeRemediationWS(onMessage: (msg: any) => void) {
  const base = (import.meta.env.VITE_WS_BASE as string | undefined) ?? "ws://localhost:8010";
  const url = base.replace(/\/$/, "") + "/ws/remediations";

  let ws: WebSocket | null = null;

  try {
    ws = new WebSocket(url);
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch (err) {
        console.error("remediation ws: bad message", err);
      }
    };
  } catch (err) {
    console.warn("remediation ws: failed to connect", err);
  }

  return () => {
    if (ws) {
      ws.close();
    }
  };
}
