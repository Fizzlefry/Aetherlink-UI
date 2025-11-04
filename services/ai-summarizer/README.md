# AetherLink AI Summarizer

AI-powered lead activity summarization using Claude Sonnet.

## What It Does

- **Fetches** lead activity from ApexFlow's unified timeline
- **Builds** deterministic prompts from structured events
- **Sends** to Claude Sonnet (or compatible LLM)
- **Returns** concise, operator-friendly summaries

## Quick Start

### Build and Run

```bash
cd infra/core
docker compose -f docker-compose.core.yml up -d --build ai-summarizer
```

### Test Without Claude API Key (Stub Mode)

```powershell
Invoke-RestMethod -Uri "http://localhost:9108/summaries/lead/1?tenant_id=acme"
```

Returns:
```json
{
  "lead_id": 1,
  "tenant_id": "acme",
  "summary": "{\"summary\": \"No Claude API key configured...\", \"next_action\": \"configure CLAUDE_API_KEY...\"}",
  "confidence": 0.85
}
```

### Test With Real Claude API Key

```bash
# Stop the container
docker stop aether-ai-summarizer
docker rm aether-ai-summarizer

# Run with your API key
docker run -d --name aether-ai-summarizer \
  --network aether-core_aether \
  -e APEXFLOW_BASE=http://apexflow:8080 \
  -e CLAUDE_API_KEY=sk-ant-your-real-key \
  -e CLAUDE_MODEL=claude-3-sonnet-20240229 \
  -p 9108:9108 \
  aetherlink-ai-summarizer
```

Or update `docker-compose.core.yml`:

```yaml
ai-summarizer:
  environment:
    - CLAUDE_API_KEY=sk-ant-api03-xxxxxxxxxxxx
```

Then:
```bash
docker compose -f docker-compose.core.yml up -d ai-summarizer
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `APEXFLOW_BASE` | `http://apexflow:8080` | ApexFlow API base URL |
| `CLAUDE_ENDPOINT` | `https://api.anthropic.com/v1/messages` | Claude API endpoint |
| `CLAUDE_API_KEY` | `""` | Anthropic API key (stub mode if empty) |
| `CLAUDE_MODEL` | `claude-3-sonnet-20240229` | Model to use |

## API Endpoints

### GET /health

Health check.

```bash
curl http://localhost:9108/health
```

Response:
```json
{
  "status": "ok",
  "service": "aetherlink-ai-summarizer"
}
```

### GET /summaries/lead/{lead_id}

Summarize a lead's complete activity timeline.

**Parameters:**
- `lead_id` (path) - Lead ID
- `tenant_id` (query) - Tenant identifier

**Example:**
```bash
curl "http://localhost:9108/summaries/lead/42?tenant_id=acme"
```

**Response:**
```json
{
  "lead_id": 42,
  "tenant_id": "acme",
  "summary": "This lead was created from website form on 2025-11-01. Sarah assigned it to John on 2025-11-02. Status changed from new → contacted → qualified. Most recent activity: John moved lead to qualified status yesterday. Next action: Schedule demo call.",
  "confidence": 0.85,
  "raw_tokens": 287
}
```

## How It Works

### 1. Fetch Activity

Calls ApexFlow's unified activity endpoint:
```
GET /leads/{id}/activity
Headers: x-tenant-id: {tenant}
```

Returns structured timeline:
```json
[
  {
    "type": "created",
    "actor": null,
    "at": "2025-11-01T10:00:00Z",
    "data": {"source": "website", "name": "Big Corp"},
    "is_system": true
  },
  {
    "type": "note",
    "actor": "sarah@acme.com",
    "at": "2025-11-01T14:30:00Z",
    "text": "Called and left voicemail",
    "is_system": false
  },
  {
    "type": "status_changed",
    "actor": "john@acme.com",
    "at": "2025-11-02T09:15:00Z",
    "data": {"old_status": "new", "new_status": "qualified"},
    "is_system": true
  }
]
```

### 2. Build Prompt

Converts activity into LLM-friendly format:

```
You are an assistant for an event-driven CRM called AetherLink.
You will be given the full activity history for a single lead.
Return a short, operator-friendly summary that answers:
1) what's going on with this lead,
2) what changed most recently,
3) what the next action should be (if obvious).

Lead ID: 42
Tenant: acme

Activity (newest first):
- [2025-11-02T09:15:00Z] STATUS by john@acme.com: new → qualified
- [2025-11-01T14:30:00Z] NOTE by sarah@acme.com: Called and left voicemail
- [2025-11-01T10:00:00Z] CREATED by system from website

Return JSON with keys: summary, next_action.
```

### 3. Call Claude

Sends to Anthropic API with:
- Model: claude-3-sonnet-20240229
- Max tokens: 400
- Temperature: 0.4 (focused, consistent)

### 4. Return Summary

Parses Claude's response and returns structured JSON.

## Prompt Engineering

The prompt is **deterministic and version-controlled** - perfect for iterating with Claude!

### Current Prompt Style

**Goal:** 3-5 sentence business summary with clear next action

**Tone:** Professional, concise, action-oriented

**Format:** JSON with `summary` and `next_action` keys

### Customize Prompt

Edit `build_prompt()` in `app/main.py`:

```python
def build_prompt(lead_id: int, tenant_id: str, activity: List[ActivityItem]) -> str:
    lines = [
        "You are helping operators understand a lead in AetherLink CRM.",
        "Provide a 3-sentence summary and suggest next action.",
        # ... customize here ...
    ]
```

### Iterate With Claude

Paste this into Claude to refine the style:

```
You are helping operators of the AetherLink CRM understand a single lead.

You receive:
- lead_id
- tenant_id
- a list of activity items (creation, notes, assignments, status changes), newest first.

Your job:
1. Explain in 3–5 sentences what has happened with the lead.
2. Mention the most recent status.
3. Mention who touched it last (by email/username if available).
4. Suggest the next obvious action.
5. Use plain business English, no markdown unless explicitly asked.

If the activity contains system-generated notes like "📊 Status changed: new → contacted", interpret them as real actions.

Return ONLY text. Do not wrap in JSON.
```

## Integration Examples

### React UI Button

Add to your lead drawer:

```typescript
const [summary, setSummary] = useState<string | null>(null);
const [loadingSummary, setLoadingSummary] = useState(false);

async function fetchSummary() {
  setLoadingSummary(true);
  try {
    const response = await fetch(
      `http://localhost:9108/summaries/lead/${lead.id}?tenant_id=${tenantId}`
    );
    const data = await response.json();
    setSummary(data.summary);
  } catch (error) {
    console.error('Failed to fetch summary:', error);
  } finally {
    setLoadingSummary(false);
  }
}

// In your JSX:
<button onClick={fetchSummary} className="btn-primary">
  {loadingSummary ? 'Generating...' : '✨ AI Summary'}
</button>

{summary && (
  <div className="ai-summary">
    <h4>AI Summary</h4>
    <p>{summary}</p>
  </div>
)}
```

### Slack Bot

```python
@slack_app.command("/lead-summary")
def lead_summary_command(ack, command, client):
    ack()
    lead_id = command['text']
    tenant_id = get_tenant_from_slack_user(command['user_id'])
    
    response = requests.get(
        f"http://aether-ai-summarizer:9108/summaries/lead/{lead_id}",
        params={"tenant_id": tenant_id}
    )
    
    summary_data = response.json()
    
    client.chat_postMessage(
        channel=command['channel_id'],
        text=f"*Lead #{lead_id} Summary*\n{summary_data['summary']}"
    )
```

### CLI Tool

```bash
#!/bin/bash
# lead-summary.sh

LEAD_ID=$1
TENANT_ID=${2:-acme}

curl -s "http://localhost:9108/summaries/lead/${LEAD_ID}?tenant_id=${TENANT_ID}" \
  | jq -r '.summary'
```

Usage:
```bash
./lead-summary.sh 42 acme
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  User Request                                               │
│  GET /summaries/lead/42?tenant_id=acme                      │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│  AI Summarizer (aether-ai-summarizer:9108)                  │
│  1. Fetch activity from ApexFlow                            │
│  2. Build deterministic prompt                              │
│  3. Call Claude Sonnet                                      │
│  4. Return structured summary                               │
└─────────────────────────────────────────────────────────────┘
         ↓                                    ↓
┌──────────────────────────┐   ┌────────────────────────────┐
│  ApexFlow API            │   │  Claude API                │
│  GET /leads/{id}/activity│   │  POST /v1/messages         │
│  Returns timeline        │   │  Returns AI summary        │
└──────────────────────────┘   └────────────────────────────┘
```

## Benefits

### ✅ Clean Separation
- AI service is **stateless** - no database, no mutations
- Only depends on ApexFlow's read-only activity endpoint
- Can be deployed/scaled independently

### ✅ Reuses Existing Data
- Leverages unified activity timeline you already built
- No new data models or storage
- Single source of truth (ApexFlow)

### ✅ Safe to Experiment
- No Claude key? Stub mode works for testing
- Deterministic prompts version-controlled in Git
- Easy to iterate and refine

### ✅ Ready for Production
- Structured logging
- Health checks
- Docker-native
- API-first design

## Future Enhancements

- [ ] **Caching** - Cache summaries for X minutes to reduce API calls
- [ ] **Batch endpoint** - Summarize multiple leads at once
- [ ] **Sentiment analysis** - Add mood/urgency indicators
- [ ] **Action extraction** - Parse next actions into structured tasks
- [ ] **Multi-model** - Support GPT-4, Mistral, etc.
- [ ] **Streaming** - SSE for real-time summary generation
- [ ] **Webhook triggers** - Auto-summarize on status changes

## Cost Considerations

**Claude Sonnet pricing** (as of 2024):
- Input: ~$3 per million tokens
- Output: ~$15 per million tokens

**Typical summary:**
- Input: ~200-500 tokens (activity history)
- Output: ~100-200 tokens (summary)
- Cost per request: ~$0.001-0.003 (< 1 cent)

**Optimization strategies:**
- Cache summaries for 15-60 minutes
- Only summarize when user explicitly requests
- Use activity hash to detect changes
- Batch requests during off-peak hours

## License

Part of AetherLink - Multi-tenant event-driven CRM platform
