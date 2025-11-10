// WebSocket helper for live remediation updates
// Auto-reconnects if backend restarts during development
export function makeRemediationWS(onMessage: (msg: any) => void) {
  // @ts-ignore - Vite injects import.meta.env at build time
  const base = (import.meta.env?.VITE_WS_BASE as string | undefined) ?? "ws://localhost:8010";
  const url = base.replace(/\/$/, "") + "/ws/remediations";

  let ws: WebSocket | null = null;
  let closedByUser = false;

  const connect = () => {
    ws = new WebSocket(url);

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch (err) {
        console.error("remediation ws: bad payload", err);
      }
    };

    ws.onclose = () => {
      if (!closedByUser) {
        // retry after 2s if backend restarted
        console.log("remediation ws: disconnected, retrying in 2s...");
        setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      // let onclose handle the retry
      ws?.close();
    };
  };

  connect();

  return () => {
    closedByUser = true;
    ws?.close();
  };
}
