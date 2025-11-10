# AccuLynx Integration Guide

This guide shows how to run AetherLink CRM alongside your existing AccuLynx system for testing and evaluation.

## Overview

AetherLink CRM can mirror data from AccuLynx without disrupting your current workflow. This allows you to:

- Test the new CRM interface with real data
- Compare user experience side-by-side
- Evaluate automations and AI features
- Keep AccuLynx as your authoritative system

## Quick Start

### 1. Export Sample Data from AccuLynx

Export some jobs, contacts, and files from AccuLynx as JSON/CSV. Transform it into this format:

```json
{
  "vertical": "peakpro",
  "jobs": [
    {
      "JobId": "ALX-1001",
      "JobName": "Roof Inspection - Downtown Office",
      "Address": "123 Main St",
      "Status": "Active",
      "SalesRep": "John Smith",
      "NextAction": "Schedule site visit",
      "CreatedDate": "2025-11-01T10:00:00Z"
    }
  ],
  "contacts": [
    {
      "ContactId": "C-001",
      "Name": "John Smith",
      "Email": "john.smith@acculynx.com",
      "Phone": "(555) 123-4567"
    }
  ],
  "files": [
    {
      "FileId": "F-001",
      "Name": "Site_Photos.pdf",
      "Url": "https://acculynx.example.com/files/site_photos.pdf",
      "JobId": "ALX-1001"
    }
  ]
}
```

### 2. Import into AetherLink

```bash
# Run the sample import script
python tools/acculynx_import_sample.py
```

Or POST directly:

```bash
curl -X POST http://localhost:8010/api/crm/import/acculynx \
  -H "Content-Type: application/json" \
  -H "x-tenant: the-expert-co" \
  -d @your_acculynx_export.json
```

### 3. View in CRM

1. Open http://localhost/ (or http://localhost:5173/ in dev)
2. Navigate to "PeakPro CRM"
3. See your AccuLynx jobs with "From AccuLynx" badges
4. Click a job to view attached files

## API Endpoints

### Import Data
```
POST /api/crm/import/acculynx
```
Accepts AccuLynx export data and mirrors it into AetherLink CRM.

**Headers:**
- `x-tenant: the-expert-co`
- `Content-Type: application/json`

**Body:**
```json
{
  "vertical": "peakpro",
  "jobs": [...],
  "contacts": [...],
  "files": [...]
}
```

### Local Command Execution (Development)
```
POST /api/local/run
```
Execute whitelisted commands locally (only from localhost).

**Body:**
```json
{
  "cmd": "python tools/acculynx_sync.py"
}
```

**Allowed Commands:**
- `python acculynx_pull.py`
- `python tools/acculynx_sync.py`
- `docker compose up -d`
- `docker compose down`
- `git pull`
- `git status`
- `npm run build`
- `npm run dev`

## Data Mapping

| AccuLynx Field | AetherLink Field | Notes |
|---|---|---|
| JobId | id | Uses JobId or generates ALX-{timestamp} |
| JobName/Address | title | Falls back to Address if no JobName |
| Status | status | Maps to CRM pipeline stages |
| SalesRep | owner | Assigned team member |
| NextAction | next_action | Next steps |
| CreatedDate | created_at | ISO timestamp |
| ContactId/Email | id | Uses ContactId, Email, or generates CUST-{timestamp} |
| Name/FullName | name | Contact display name |
| Email | email | Contact email |
| Phone | phone | Contact phone |
| FileId/Name | id | File identifier |
| Name | name | Display filename |
| Url | url | Link to file (if accessible) |
| JobId | job_id | Links file to job |

## File Handling

Files are stored as metadata only. If AccuLynx provides public URLs, they can be accessed directly. For private files, you'll need to set up a proxy or file sync process.

## Next Steps

1. **Test with Real Data**: Export a subset of your AccuLynx jobs
2. **Automate Sync**: Set up scheduled imports
3. **File Access**: Configure file proxy if needed
4. **User Testing**: Have team members try the new interface
5. **Feature Comparison**: Evaluate which features work better

## Safety Notes

- AetherLink **never writes back** to AccuLynx
- All imported data is tagged `source: "acculynx"`
- Local execution is restricted to whitelisted commands
- Only accessible from localhost for security

This setup lets you evaluate AetherLink CRM without any risk to your current AccuLynx workflow.
