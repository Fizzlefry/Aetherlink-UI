/**
 * Generic WebSocket helper with auto-reconnect support
 * @param path - WebSocket endpoint path (e.g., "/ws/remediations")
 * @param onMessage - Callback for incoming messages
 * @param retryMs - Reconnection delay in milliseconds (default: 2000)
 * @returns Object with teardown function and getSocket accessor
 */
export function makeWS(
  path: string,
  onMessage: (msg: any) => void,
  retryMs = 2000
) {
  // @ts-ignore - Vite injects import.meta.env at build time
  const base = (import.meta.env?.VITE_WS_BASE as string | undefined) ?? "ws://localhost:8010";
  const url = base.replace(/\/$/, "") + path;

  let ws: WebSocket | null = null;
  let closedByUser = false;

  const connect = () => {
    ws = new WebSocket(url);

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        onMessage(parsed);
      } catch (err) {
        console.error(`ws(${path}): bad payload`, err);
      }
    };

    ws.onclose = () => {
      if (!closedByUser) {
        console.log(`ws(${path}): disconnected, retrying in ${retryMs}ms...`);
        setTimeout(connect, retryMs);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  // Phase XX M9: Return object with teardown and socket accessor
  return {
    teardown: () => {
      closedByUser = true;
      ws?.close();
    },
    getSocket: () => ws,
  };
}

/**
 * WebSocket helper for remediation events
 * Phase XX M9: Returns object with teardown and getSocket for heartbeat support
 */
export function makeRemediationWS(onMessage: (msg: any) => void) {
  return makeWS("/ws/remediations", onMessage);
}

/**
 * WebSocket helper for operator activity events
 */
export function makeOperatorActivityWS(onMessage: (msg: any) => void) {
  return makeWS("/ws/operator-activity", onMessage);
}
