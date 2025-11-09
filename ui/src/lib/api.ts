// Phase XIV: Configurable API base URL
// Reads from Vite env variable, defaults to localhost for local development
const API_BASE =
  import.meta.env.VITE_COMMAND_CENTER_URL || "http://localhost:8000";

export async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "x-ops": "1",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res;
}
