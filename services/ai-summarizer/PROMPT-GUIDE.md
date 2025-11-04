# Claude Sonnet Prompt Guide

This document contains the exact prompts and patterns used by the AI Summarizer service.

## Master Prompt Template

This is what gets sent to Claude for every lead summary request:

```
You are an assistant for an event-driven CRM called AetherLink.
You will be given the full activity history for a single lead.
Return a short, operator-friendly summary that answers:
1) what's going on with this lead,
2) what changed most recently,
3) what the next action should be (if obvious).

Lead ID: {lead_id}
Tenant: {tenant_id}

Activity (newest first):
- [{timestamp}] CREATED by system from {source}
- [{timestamp}] NOTE by {actor}: {text}
- [{timestamp}] ASSIGNED by {actor} → {assignee}
- [{timestamp}] STATUS by {actor}: {old_status} → {new_status}

Return JSON with keys: summary, next_action.
```

## Activity Format Patterns

The service translates our structured activity into human-readable lines:

### Created Event
```
- [2025-11-01T10:00:00Z] CREATED by system from website
```

**Data available:**
- `source` (website, import, api, manual)
- `name` (lead name)
- `email` (lead email)

### Note Event
```
- [2025-11-01T14:30:00Z] NOTE by sarah@acme.com: Called and left voicemail
```

**Data available:**
- `text` (note body)
- `actor` (who wrote it)

### Assignment Event
```
- [2025-11-02T09:00:00Z] ASSIGNED by manager@acme.com → john@acme.com
```

**Data available:**
- `assigned_to` (new owner)
- `actor` (who did the assignment)

### Status Change Event
```
- [2025-11-02T09:15:00Z] STATUS by john@acme.com: contacted → qualified
```

**Data available:**
- `old_status` (previous status)
- `new_status` (current status)
- `actor` (who changed it)

## Example Request/Response

### Input to Claude

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
- [2025-11-03T15:30:00Z] STATUS by john@acme.com: contacted → qualified
- [2025-11-03T09:00:00Z] NOTE by john@acme.com: Great discovery call. They have budget approved for Q4. Interested in Enterprise plan.
- [2025-11-02T16:45:00Z] ASSIGNED by sarah@acme.com → john@acme.com
- [2025-11-02T14:20:00Z] NOTE by sarah@acme.com: Left voicemail. Will try again tomorrow.
- [2025-11-02T10:00:00Z] STATUS by sarah@acme.com: new → contacted
- [2025-11-01T18:30:00Z] CREATED by system from website

Return JSON with keys: summary, next_action.
```

### Expected Output from Claude

```json
{
  "summary": "This lead came in via website on Nov 1st. Sarah initially contacted them and assigned to John on Nov 2nd. John had a successful discovery call today where they confirmed Q4 budget and interest in Enterprise plan. John moved the lead to qualified status this afternoon. Strong buying signals present.",
  "next_action": "Schedule product demo and prepare Enterprise pricing proposal for Q4 deal."
}
```

## Prompt Refinement Guide

### For Shorter Summaries

Change the instruction to:

```
Return a 2-sentence summary focusing only on current status and next action.
```

### For More Detail

```
Return a detailed paragraph covering:
- Lead source and initial contact date
- All key interactions with names and dates
- Current status and owner
- Recommended next steps with timeline
```

### For Specific Formats

**Bullet points:**
```
Return summary as:
- Current Status: [status]
- Owner: [name]
- Last Activity: [what happened]
- Next Action: [suggestion]
```

**Markdown:**
```
Return summary formatted as:
## Lead Status
[summary]

## Recommended Action
[next step]
```

### For Different Tones

**Urgent/Sales-focused:**
```
Focus on: deal size, timeline, buying signals, urgency.
Use energetic, action-oriented language.
```

**Analytical:**
```
Focus on: engagement metrics, response times, conversion signals.
Use data-driven, objective language.
```

**Customer Success:**
```
Focus on: relationship health, satisfaction signals, risk indicators.
Use empathetic, relationship-focused language.
```

## Advanced Prompt Patterns

### Conditional Logic

```
If status is "won":
  Emphasize success and expansion opportunities.
If status is "lost":
  Focus on lessons learned and re-engagement timing.
If no activity in 7+ days:
  Flag as "at risk" and suggest re-engagement.
```

**Implementation:**
```python
def build_prompt(lead_id, tenant_id, activity):
    # ... activity lines ...

    # Add conditional instructions
    most_recent = activity[0] if activity else None
    days_since_activity = calculate_days(most_recent.at)

    if days_since_activity > 7:
        lines.append("IMPORTANT: No activity in 7+ days. Emphasize re-engagement urgency.")
```

### Multi-Stage Summaries

**Stage 1: Quick Summary** (100 tokens max)
```
Provide a 1-sentence status update.
```

**Stage 2: Detailed Analysis** (400 tokens)
```
Now provide complete analysis with timeline, stakeholders, and recommendations.
```

### Few-Shot Examples

Include examples in the prompt:

```
Example input:
- [2025-11-01] CREATED from website
- [2025-11-01] STATUS: new → contacted

Example output:
{"summary": "New lead from website, contacted same day.", "next_action": "Follow up within 24h"}

Now summarize this lead:
[actual activity]
```

## Model Parameters

Current settings in `app/main.py`:

```python
{
    "model": "claude-3-sonnet-20240229",
    "max_tokens": 400,
    "temperature": 0.4,
    "messages": [...]
}
```

### Temperature Guide

- **0.0-0.3**: Very consistent, factual, predictable
- **0.4-0.6**: Balanced (current setting)
- **0.7-1.0**: Creative, varied, less predictable

**Recommendation:** Keep at 0.4 for business summaries (consistency > creativity)

### Max Tokens Guide

- **100-200**: Quick status updates
- **300-400**: Standard summaries (current)
- **500-800**: Detailed analysis
- **1000+**: Comprehensive reports

## Testing Prompts

### Test Different Activity Patterns

**Brand new lead:**
```
- [today] CREATED from website
```

**Expected:** Focus on initial outreach

**Hot lead (lots of activity):**
```
- [today 3pm] STATUS: qualified → won
- [today 2pm] NOTE: Signed contract!
- [today 10am] NOTE: Final pricing approved
- [yesterday] NOTE: Demo went great
```

**Expected:** Emphasize momentum and success

**Cold lead:**
```
- [30 days ago] NOTE: No response to email
- [45 days ago] STATUS: new → contacted
- [60 days ago] CREATED from import
```

**Expected:** Flag as stale, suggest re-engagement or disqualification

## Debugging Prompts

### View Actual Prompt

Without Claude API key, the service returns:
```json
{
  "summary": "No Claude API key configured. Here is the prompt you would have sent."
}
```

This shows you exactly what Claude would receive!

### Test Prompt Directly

1. Copy the prompt from stub response
2. Go to https://console.anthropic.com/
3. Paste into Workbench
4. Iterate until satisfied
5. Update `build_prompt()` function

## Prompt Versioning

Track prompt changes in Git:

```python
# v1.0 - Basic summary
# v1.1 - Added next_action field
# v1.2 - Added conditional urgency logic
# v1.3 - Improved tone for sales context
def build_prompt(lead_id, tenant_id, activity):
    PROMPT_VERSION = "1.3"
    # ...
```

## Claude Best Practices

### ✅ Do
- Keep instructions clear and specific
- Use consistent formatting
- Include examples when ambiguous
- Request structured output (JSON)
- Version control prompts

### ❌ Don't
- Make prompts overly long (>2000 tokens)
- Use vague language ("be helpful")
- Mix multiple unrelated tasks
- Rely on implied context
- Forget edge cases (empty activity)

## Cost Optimization

### Prompt Compression

**Before:** (verbose)
```
You are a helpful assistant for a CRM system called AetherLink.
Your role is to analyze the complete activity history...
[500 tokens]
```

**After:** (concise)
```
Summarize this CRM lead's activity in 3 sentences.
[100 tokens]
```

**Savings:** 80% reduction in input tokens

### Caching Strategy

Cache summaries with:
```python
cache_key = f"summary:{lead_id}:{activity_hash}"
if cached := cache.get(cache_key):
    return cached
```

Only call Claude when activity changes!

## Alternative Models

### Claude Haiku (Faster/Cheaper)
```yaml
CLAUDE_MODEL: claude-3-haiku-20240307
```
- 5x cheaper
- 3x faster
- Good for simple summaries

### Claude Opus (More Capable)
```yaml
CLAUDE_MODEL: claude-3-opus-20240229
```
- Most sophisticated
- Best for complex analysis
- 3x more expensive

## Production Checklist

- [ ] Prompt tested with 10+ diverse leads
- [ ] Edge cases handled (empty activity, single event, etc.)
- [ ] Output format validated (JSON parseable)
- [ ] Token usage optimized (<500 input + output)
- [ ] Caching implemented for repeated requests
- [ ] Error handling for API failures
- [ ] Logging for prompt debugging
- [ ] A/B test different prompts

## Resources

- [Claude Prompt Engineering Guide](https://docs.anthropic.com/claude/docs/prompt-engineering)
- [Anthropic API Docs](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- [AetherLink Activity Schema](../../services/apexflow/README.md)
