# pods/customer_ops/api/ui.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

DASHBOARD_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AetherLink Control Panel</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root { color-scheme: dark light; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; }
    header { padding: 12px 16px; background: #0f172a; color: #e2e8f0; display:flex; gap:12px; align-items:center; }
    header h1 { font-size: 18px; margin: 0; }
    main { padding: 16px; display: grid; gap: 16px; grid-template-columns: 1fr 1fr; }
    section { border: 1px solid #334155; border-radius: 10px; padding: 12px; background: #0b1220; color: #e2e8f0; }
    h2 { margin: 0 0 8px 0; font-size: 16px; }
    textarea, input, select, button { width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #334155; background:#0d1726; color:#e2e8f0;}
    .row { display: grid; gap: 8px; grid-template-columns: 1fr 120px; align-items: start; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre-wrap; }
    .pill { display:inline-block; padding:2px 8px; border:1px solid #334155; border-radius:999px; font-size:12px; margin-right:6px;}
    .ok{color:#22c55e}.bad{color:#ef4444}
    .small { font-size: 12px; color: #94a3b8; }
  </style>
</head>
<body>
  <header>
    <h1>AetherLink Control Panel</h1>
    <span class="pill" id="health-pill">checking…</span>
    <span class="pill" id="tenants-pill">tenants: ?</span>
    <span class="small" style="margin-left:auto">🔐 Admin key required</span>
  </header>
  <main>
    <section>
      <h2>🔍 Health & Metrics</h2>
      <div class="row">
        <button onclick="checkHealth()">Check Health</button>
        <button onclick="openMetrics()">Open /metrics</button>
      </div>
      <div class="mono small" id="health-out"></div>
    </section>

    <section>
      <h2>🧪 Chat (Streaming)</h2>
      <select id="provider">
        <option value="ollama">ollama</option>
        <option value="openai">openai</option>
        <option value="gemini">gemini</option>
      </select>
      <input id="apiKey" placeholder="x-api-key (tenant)" />
      <textarea id="msg" rows="3" placeholder="Ask anything. The agent will use tools + RAG."></textarea>
      <div class="row">
        <button onclick="chat()">Send (JSON)</button>
        <button onclick="chatStream()">Stream (SSE)</button>
      </div>
      <div class="mono" id="chat-out"></div>
    </section>

    <section>
      <h2>📚 Knowledge Ingest</h2>
      <input id="source" placeholder="source tag (e.g., crm, wiki, pdf)" />
      <textarea id="ingest" rows="2" placeholder="Paste knowledge text to store per-tenant"></textarea>
      <input type="file" id="fileUpload" accept=".pdf,.txt,.md,.docx" style="margin:8px 0" />
      <div class="row">
        <button onclick="ingest()">Ingest Text</button>
        <button onclick="ingestFile()">Upload File</button>
      </div>
      <div class="row">
        <button onclick="listKnowledge()">List</button>
        <button onclick="exportKnowledge()">Export CSV</button>
      </div>
      <div class="mono small" id="ingest-out"></div>
    </section>

    <section>
      <h2>🧠 Embeddings Explorer (2D Preview)</h2>
      <div class="row">
        <button onclick="project()">Compute UMAP</button>
        <button onclick="downloadCSV()">Download CSV</button>
      </div>
      <div class="mono small" id="proj-out"></div>
    </section>
  </main>
<script>
const out = (id, v) => document.getElementById(id).textContent = typeof v==="string"? v : JSON.stringify(v, null, 2);
const val = id => document.getElementById(id).value;

async function checkHealth(){
  try {
    const r = await fetch('/health');
    const j = await r.json();
    out('health-out', j);
    document.getElementById('health-pill').textContent = j.ok ? 'healthy' : 'unhealthy';
    document.getElementById('health-pill').className = 'pill '+(j.ok ? 'ok':'bad');
    // Use apiKey as both tenant key and admin key (user should provide admin key)
    const adminKey = val('apiKey');
    const t = await fetch('/ops/tenants', { headers: { 'x-api-key': adminKey, 'x-admin-key': adminKey }}).then(r=>r.json()).catch(()=>({tenants:[]}));
    document.getElementById('tenants-pill').textContent = 'tenants: '+(t.tenants?.length ?? '?');
  } catch(e){ out('health-out', String(e)); }
}
function openMetrics(){ window.open('/metrics', '_blank'); }

async function chat(){
  out('chat-out', '…');
  const r = await fetch('/chat', {
    method:'POST',
    headers:{'content-type':'application/json','x-api-key':val('apiKey')},
    body: JSON.stringify({ message: val('msg'), provider_override: val('provider') })
  });
  const j = await r.json().catch(()=> ({}));
  out('chat-out', j);
}

async function chatStream(){
  out('chat-out', '');
  const es = new EventSourcePolyfill('/chat/stream', {
    headers: { 'x-api-key': val('apiKey'), 'content-type': 'application/json' },
    payload: JSON.stringify({ message: val('msg'), provider_override: val('provider') })
  });
  es.onmessage = e => { document.getElementById('chat-out').textContent += e.data + "\\n"; };
  es.addEventListener('text', e => { document.getElementById('chat-out').textContent += e.data + "\\n"; });
  es.addEventListener('tool_result', e => { document.getElementById('chat-out').textContent += "\\n[tool] " + e.data + "\\n"; });
  es.addEventListener('error', e => { document.getElementById('chat-out').textContent += "\\n[error] " + e.data + "\\n"; });
  es.addEventListener('done', () => es.close());
}

async function ingest(){
  const r = await fetch('/knowledge/ingest', {
    method:'POST', headers:{'content-type':'application/json','x-api-key':val('apiKey')},
    body: JSON.stringify({ text: val('ingest'), source: val('source') || 'manual' })
  });
  out('ingest-out', await r.json());
}

async function ingestFile(){
  const fileInput = document.getElementById('fileUpload');
  if(!fileInput.files.length){ out('ingest-out','No file selected'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('source', val('source') || 'upload');
  const r = await fetch('/knowledge/ingest-file', {
    method:'POST', headers:{'x-api-key':val('apiKey')},
    body: formData
  });
  out('ingest-out', await r.json());
}

async function listKnowledge(){
  const r = await fetch('/knowledge/list', {
    headers: { 'x-api-key': val('apiKey') }
  });
  out('ingest-out', await r.json());
}

async function exportKnowledge(){
  window.open('/knowledge/export?x-api-key=' + val('apiKey'), '_blank');
}

async function project(){
  const r = await fetch('/embed/project', {
    headers: { 'x-api-key': val('apiKey') }
  });
  out('proj-out', await r.json());
}

function downloadCSV(){
  window.open('/embed/project.csv', '_blank');
}

/* lightweight EventSource polyfill to allow POST body */
class EventSourcePolyfill {
  constructor(url, { headers = {}, payload = "" } = {}){
    const controller = new AbortController();
    this._controller = controller;
    fetch(url, { method:'POST', headers, body: payload, signal: controller.signal })
      .then(async res => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while(true){
          const { value, done } = await reader.read();
          if(done) break;
          buf += decoder.decode(value, {stream:true});
          const parts = buf.split("\\n\\n");
          buf = parts.pop() || "";
          for(const chunk of parts){
            const lines = chunk.split("\\n");
            let event = "message";
            let data = "";
            for(const line of lines){
              if(line.startsWith("event:")) event = line.slice(6).trim();
              else if(line.startsWith("data:")) data += (data? "\\n":"") + line.slice(5).trim();
            }
            (this.onmessage||function(){})({ data });
            const handler = this._handlers?.[event];
            if(handler){ handler({ data }); }
          }
        }
      }).catch(err => (this.onerror||function(){})(err));
    this._handlers = {};
  }
  addEventListener(name, fn){ this._handlers[name] = fn; }
  close(){ this._controller.abort(); }
}
</script>
</body>
</html>
"""

@router.get("/", response_class=HTMLResponse)
async def dashboard(_: Request) -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)
