// server.js
// Minimal MCP-style server that surfaces AetherLink ops data
// Assumes your AI Agent Bridge is running at http://localhost:3001

const BRIDGE_BASE = process.env.AI_BRIDGE_URL || "http://localhost:3001";
const STDIN = process.stdin;
const STDOUT = process.stdout;

STDIN.setEncoding("utf8");

function send(msg) {
  const json = JSON.stringify(msg);
  STDOUT.write(json + "\n");
}

// Fetch helper
async function bridgeFetch(path) {
  const res = await fetch(`${BRIDGE_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`Bridge error ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// Handle MCP-like messages
STDIN.on("data", async (chunk) => {
  const lines = chunk.trim().split("\n");
  for (const line of lines) {
    if (!line.trim()) continue;

    let msg;
    try {
      msg = JSON.parse(line);
    } catch (err) {
      send({
        jsonrpc: "2.0",
        error: { code: -32700, message: "Parse error" }
      });
      continue;
    }

    // Basic JSON-RPC/MCP
    const { id, method, params } = msg;

    // 1) Handshake / initialize
    if (method === "initialize" || method === "server/initialize") {
      send({
        jsonrpc: "2.0",
        id,
        result: {
          serverInfo: {
            name: "aetherlink-mcp",
            version: "1.0.0"
          },
          capabilities: {
            tools: {}
          }
        }
      });
      continue;
    }

    // 2) List tools
    if (method === "tools/list") {
      send({
        jsonrpc: "2.0",
        id,
        result: {
          tools: [
            {
              name: "aetherlink.get_ops_snapshot",
              description: "Get AI-friendly ops snapshot from AetherLink (via bridge)",
              inputSchema: {
                type: "object",
                properties: {
                  min_severity: {
                    type: "string",
                    description: "Optional severity filter: info|warning|critical"
                  }
                },
                required: []
              }
            },
            {
              name: "aetherlink.get_anomalies",
              description: "Get current anomalies from AetherLink",
              inputSchema: { type: "object", properties: {}, required: [] }
            },
            {
              name: "aetherlink.get_deliveries",
              description: "Get recent deliveries from AetherLink",
              inputSchema: {
                type: "object",
                properties: {
                  limit: {
                    type: "number",
                    description: "Max number of deliveries to return",
                    default: 20
                  }
                },
                required: []
              }
            },
            {
              name: "aetherlink.replay_delivery",
              description: "Replay a failed or pending delivery by ID",
              inputSchema: {
                type: "object",
                properties: {
                  delivery_id: {
                    type: "string",
                    description: "The delivery ID to replay (UUID format)"
                  }
                },
                required: ["delivery_id"]
              }
            },
            {
              name: "peakpro.get_snapshot",
              description: "Get CRM snapshot from PeakPro (contacts, deals, notes)",
              inputSchema: { type: "object", properties: {}, required: [] }
            },
            {
              name: "roofwonder.get_snapshot",
              description: "Get roofing jobs snapshot from RoofWonder",
              inputSchema: { type: "object", properties: {}, required: [] }
            },
            {
              name: "policypal.get_snapshot",
              description: "Get insurance policies snapshot from PolicyPal AI",
              inputSchema: { type: "object", properties: {}, required: [] }
            }
          ]
        }
      });
      continue;
    }

    // 3) Tool calls
    if (method === "tools/call") {
      const toolName = params?.name;
      const args = params?.arguments || {};

      try {
        if (toolName === "aetherlink.get_ops_snapshot") {
          const qs = args.min_severity
            ? `?min_severity=${encodeURIComponent(args.min_severity)}`
            : "";
          const data = await bridgeFetch(`/ops/snapshot${qs}`);
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "aetherlink.get_anomalies") {
          const data = await bridgeFetch(`/ops/anomalies`);
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "aetherlink.get_deliveries") {
          const limit = args.limit ?? 20;
          const data = await bridgeFetch(`/ops/deliveries?limit=${limit}`);
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "aetherlink.replay_delivery") {
          const deliveryId = args.delivery_id;
          if (!deliveryId) {
            send({
              jsonrpc: "2.0",
              id,
              error: {
                code: -32602,
                message: "delivery_id parameter is required"
              }
            });
            continue;
          }

          // POST to replay endpoint
          const url = `${BRIDGE_BASE}/ops/replay/${deliveryId}`;
          const res = await fetch(url, { method: 'POST' });

          if (!res.ok) {
            const errorText = await res.text();
            send({
              jsonrpc: "2.0",
              id,
              error: {
                code: -32000,
                message: `Replay failed: ${res.status} ${res.statusText} - ${errorText}`
              }
            });
            continue;
          }

          const data = await res.json();
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "peakpro.get_snapshot") {
          const url = process.env.PEAKPRO_URL || "http://localhost:8021";
          const res = await fetch(`${url}/ai/snapshot`);
          const data = await res.json();
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "roofwonder.get_snapshot") {
          const url = process.env.ROOFWONDER_URL || "http://localhost:8022";
          const res = await fetch(`${url}/ai/snapshot`);
          const data = await res.json();
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        if (toolName === "policypal.get_snapshot") {
          const url = process.env.POLICYPAL_URL || "http://localhost:8023";
          const res = await fetch(`${url}/ai/snapshot`);
          const data = await res.json();
          send({
            jsonrpc: "2.0",
            id,
            result: {
              content: [
                {
                  type: "text",
                  text: JSON.stringify(data, null, 2)
                }
              ]
            }
          });
          continue;
        }

        // Unknown tool
        send({
          jsonrpc: "2.0",
          id,
          error: {
            code: -32601,
            message: `Tool not found: ${toolName}`
          }
        });
      } catch (err) {
        send({
          jsonrpc: "2.0",
          id,
          error: {
            code: -32000,
            message: err.message
          }
        });
      }

      continue;
    }

    // 4) Fallback
    send({
      jsonrpc: "2.0",
      id,
      error: {
        code: -32601,
        message: "Method not found"
      }
    });
  }
});
