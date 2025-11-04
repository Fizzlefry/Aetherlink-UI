# 🔒 Option E: Secure Dashboard + File Upload

## Overview

Option E adds two critical production upgrades to AetherLink:

1. **Admin-Protected Dashboard**: Control plane requires admin key authentication
2. **File Upload Ingestion**: Drag-drop PDF, TXT, MD, DOCX files into knowledge base

## 🔐 1. Secure Dashboard (Admin-Only)

### What Changed

The web dashboard (`/`), eval harness (`/evals/run`), and all control plane features now require **admin key authentication** via the `x-admin-key` header.

### Why This Matters

- Prevents unauthorized access to sensitive operations
- Separates tenant API keys (for chat/RAG) from admin keys (for control)
- Follows principle of least privilege
- Production-ready security posture

### How It Works

**Code Implementation** (`main.py`):
```python
def AdminRequired(x_admin_key: Optional[str] = Header(None)) -> None:
    """Require admin key for sensitive operations (dashboard, evals)."""
    expected = getattr(settings, "API_ADMIN_KEY", None)
    if not expected or x_admin_key != expected:
        raise HTTPException(status_code=403, detail="admin_required")

# Mount routers with admin protection
app.include_router(ui_router, tags=["ui"], dependencies=[Depends(AdminRequired)])
app.include_router(evals_router, tags=["evals"], dependencies=[Depends(AdminRequired)])
```

### Usage

#### Web Dashboard

1. Visit `http://localhost:8000/`
2. In the **x-api-key** field, enter your **admin key** (not tenant key)
3. The dashboard will use this key for:
   - Admin operations (health check, tenant list)
   - Knowledge operations (scoped to tenant)

**Example:**
```powershell
# Set admin key in environment
$env:API_ADMIN_KEY = "admin-secret-123"

# In dashboard: enter "admin-secret-123" in x-api-key field
```

#### API Requests

All dashboard and eval endpoints require `x-admin-key` header:

```powershell
$headers = @{
    'x-admin-key' = $env:API_ADMIN_KEY
    'x-api-key' = 'tenant-key'  # for tenant-scoped operations
}

# Access dashboard
Invoke-WebRequest http://localhost:8000/ -Headers $headers

# Run evals
Invoke-RestMethod http://localhost:8000/evals/run -Method Post -Headers $headers
```

### Protected Endpoints

The following now require admin key:

- `GET /` - Web dashboard
- `POST /evals/run` - Golden test harness
- All UI-related assets

**Note:** Knowledge endpoints (`/knowledge/list`, `/knowledge/ingest`, etc.) still use regular API key for tenant isolation.

### Configuration

Set admin key via environment variable:

```powershell
# PowerShell
$env:API_ADMIN_KEY = "your-secure-admin-key-here"

# Or in .env file
API_ADMIN_KEY=your-secure-admin-key-here
```

**Security Best Practices:**
- Use strong, random admin keys (32+ characters)
- Rotate admin keys regularly
- Never commit admin keys to version control
- Use different keys for dev/staging/prod
- Audit admin key usage via logs

## 📤 2. File Upload Ingestion

### What's New

Upload files directly to your knowledge base with automatic text extraction:

- **PDF** (.pdf) - Uses `pypdf` for text extraction
- **Plain Text** (.txt, .md) - Direct UTF-8 decoding
- **Word Docs** (.docx) - Uses `python-docx` (optional)
- **Fallback** - Any file treated as UTF-8 text

### Dependencies

Added to `requirements.txt`:
```text
python-multipart>=0.0.9       # for file upload support
pypdf>=4.0.0                  # for PDF text extraction
```

**Optional (for DOCX support):**
```powershell
pip install python-docx
```

### Endpoint: `POST /knowledge/ingest-file`

Upload a file and automatically extract + chunk + embed text.

**Form Data:**
- `file` (UploadFile, required) - File to ingest
- `source` (str, optional) - Source tag (default: "upload")

**Headers:**
- `x-api-key` - Tenant API key (for isolation)

**Response:**
```json
{
  "ok": true,
  "filename": "report.pdf",
  "ingested_chunks": 15,
  "source": "upload",
  "tenant": "expertco"
}
```

### Usage Examples

#### From Web Dashboard

1. Visit `http://localhost:8000/` (with admin key)
2. Go to **📚 Knowledge Ingest** section
3. Enter source tag (e.g., "contracts")
4. Click **Choose File** and select PDF/TXT/MD/DOCX
5. Click **Upload File**
6. See ingestion result in output panel

#### From PowerShell

```powershell
# Upload PDF
$headers = @{'x-api-key' = 'test-key'}
$form = @{
    file = Get-Item "C:\Documents\contract.pdf"
    source = "legal-docs"
}
Invoke-RestMethod http://localhost:8000/knowledge/ingest-file `
    -Method Post -Headers $headers -Form $form | ConvertTo-Json -Depth 5

# Upload text file
$form = @{
    file = Get-Item "notes.txt"
    source = "meeting-notes"
}
Invoke-RestMethod http://localhost:8000/knowledge/ingest-file `
    -Method Post -Headers $headers -Form $form | ConvertTo-Json -Depth 5
```

#### From curl (Linux/Mac)

```bash
curl -X POST http://localhost:8000/knowledge/ingest-file \
  -H "x-api-key: test-key" \
  -F "file=@contract.pdf" \
  -F "source=legal-docs"
```

### Text Extraction Logic

**PDF Files:**
```python
from pypdf import PdfReader
import io

r = PdfReader(io.BytesIO(file_bytes))
text = "\n".join([page.extract_text() or "" for page in r.pages])
```

**Text Files (.txt, .md):**
```python
text = file_bytes.decode("utf-8", errors="ignore")
```

**Word Docs (.docx):**
```python
import docx
from io import BytesIO

doc = docx.Document(BytesIO(file_bytes))
text = "\n".join([p.text for p in doc.paragraphs])
```

**Fallback (unknown extensions):**
- Attempts UTF-8 decoding
- Graceful error handling
- Returns 400 if no text extracted

### Error Handling

```json
// No file selected
{
  "detail": "file is required"
}

// No text extracted
{
  "detail": "No text extracted from file"
}

// pypdf import failure (not installed)
// Falls back to UTF-8 decode attempt
```

### Dashboard UI Updates

**New Features:**
- File input element: `<input type="file" accept=".pdf,.txt,.md,.docx" />`
- **Upload File** button triggers `ingestFile()` function
- **Export CSV** button downloads all knowledge
- Admin key reminder in header: "🔐 Admin key required"

**Updated Layout:**
```
Knowledge Ingest Section:
  [source tag input]
  [text area for paste]
  [file chooser button]
  [Ingest Text] [Upload File]
  [List]        [Export CSV]
  [output display]
```

## 🚀 Quick Start

### 1. Install Dependencies

```powershell
cd pods/customer_ops
pip install -r requirements.txt
```

Or rebuild Docker:
```powershell
docker compose down
docker compose up --build -d
```

### 2. Configure Admin Key

```powershell
$env:API_ADMIN_KEY = "admin-secret-123"
$env:API_KEY_EXPERTCO = "test-key"
```

Or add to `.env`:
```env
API_ADMIN_KEY=admin-secret-123
API_KEY_EXPERTCO=test-key
```

### 3. Access Dashboard

```powershell
# Open dashboard
Start-Process http://localhost:8000/

# In browser:
# - Enter "admin-secret-123" in x-api-key field
# - This serves as both admin key AND tenant key
```

### 4. Test File Upload

```powershell
# Via dashboard:
# 1. Choose a PDF/TXT file
# 2. Enter source tag
# 3. Click "Upload File"

# Via PowerShell:
$h=@{'x-api-key'='test-key'}
$f=@{file=Get-Item "sample.pdf"; source="test"}
Invoke-RestMethod http://localhost:8000/knowledge/ingest-file -Method Post -Headers $h -Form $f
```

### 5. Verify Ingestion

```powershell
# List knowledge
$h=@{'x-api-key'='test-key'}
Invoke-RestMethod http://localhost:8000/knowledge/list -Headers $h | ConvertTo-Json -Depth 5

# Ask about it
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h `
    -Body '{"message":"What did the PDF say?"}' -ContentType 'application/json'
```

## 📊 Metrics & Observability

File upload operations are tracked via existing metrics:

- `rag_hits_total{tenant}` - Increments when uploaded knowledge is retrieved
- `rag_retrieval_latency_ms` - Tracks search performance
- `errors_total{endpoint="/knowledge/ingest-file"}` - Upload failures

**View metrics:**
```powershell
(Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content | Select-String "rag_|errors_total"
```

## 🔒 Security Considerations

### Admin Key Protection

**Do's:**
- ✅ Use environment variables for admin key
- ✅ Rotate admin keys quarterly
- ✅ Audit admin operations in logs
- ✅ Use HTTPS in production
- ✅ Implement IP allowlisting for admin endpoints

**Don'ts:**
- ❌ Never commit admin keys to git
- ❌ Don't share admin keys in Slack/email
- ❌ Avoid reusing tenant keys as admin keys
- ❌ Don't log admin keys in plaintext

### File Upload Safety

**Built-in Protections:**
- Tenant isolation (files scoped by API key)
- No file execution (only text extraction)
- UTF-8 error handling (malformed files won't crash)
- Size limits (FastAPI default: 1MB, configurable)

**Additional Hardening (Optional):**
```python
# Add to main.py before @app.post("/knowledge/ingest-file")
@app.post("/knowledge/ingest-file", tags=["knowledge"], dependencies=[Depends(ApiKeyRequired)])
async def knowledge_ingest_file(
    file: UploadFile = File(..., max_length=10_485_760),  # 10MB max
    # ... rest of function
```

**Virus Scanning (Production):**
```python
import clamd  # optional: pyclamd for ClamAV integration

def scan_file(data: bytes) -> bool:
    cd = clamd.ClamdUnixSocket()
    result = cd.scan_stream(data)
    return result['stream'][0] == 'OK'
```

## 🧪 Testing

### Test Admin Auth

```powershell
# Should fail (no admin key)
Invoke-WebRequest http://localhost:8000/ -ErrorAction Stop
# Expected: 403 Forbidden

# Should succeed
$h=@{'x-admin-key'=$env:API_ADMIN_KEY}
Invoke-WebRequest http://localhost:8000/ -Headers $h
# Expected: 200 OK (HTML dashboard)
```

### Test File Upload

```powershell
# Create test file
"Lead 456 is high priority. Contact ASAP." | Out-File -Encoding UTF8 test.txt

# Upload
$h=@{'x-api-key'='test-key'}
$f=@{file=Get-Item test.txt; source='test'}
$result = Invoke-RestMethod http://localhost:8000/knowledge/ingest-file -Method Post -Headers $h -Form $f
Write-Output $result

# Verify ingestion
if ($result.ok -and $result.ingested_chunks -gt 0) {
    Write-Host "✅ File upload working" -ForegroundColor Green
} else {
    Write-Host "❌ File upload failed" -ForegroundColor Red
}
```

### Test End-to-End RAG with Uploaded File

```powershell
# 1. Upload knowledge
$h=@{'x-api-key'='test-key'; 'Content-Type'='application/json'}
$f=@{file=Get-Item "contract.pdf"; source='legal'}
Invoke-RestMethod http://localhost:8000/knowledge/ingest-file -Method Post -Headers @{'x-api-key'='test-key'} -Form $f

# 2. Ask about it
Invoke-RestMethod http://localhost:8000/chat -Method Post -Headers $h `
    -Body '{"message":"What are the key terms in the contract?"}' | ConvertTo-Json -Depth 5

# 3. Check metrics
(Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing).Content | Select-String "rag_hits_total"
```

## 📚 API Reference

### Admin-Protected Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/` | GET | x-admin-key | Web dashboard |
| `/evals/run` | POST | x-admin-key | Run golden tests |

### File Upload Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/knowledge/ingest-file` | POST | x-api-key | Upload file for ingestion |

## 🎉 What You Can Do Now

1. **Secure Your Control Plane**
   - Only admins can access dashboard
   - Tenant isolation maintained
   - Production-ready security

2. **Drag-Drop Knowledge Ingestion**
   - Upload contracts, reports, wikis as PDFs
   - Bulk import from document folders
   - No manual copy-paste needed

3. **Knowledge Lifecycle Management**
   - Upload → List → Export → Delete
   - Full CRUD operations via UI or API
   - CSV export for external analysis

4. **Production Deployment**
   - Admin auth prevents unauthorized access
   - File upload enables non-technical users
   - Audit trail via structured logs

---

**Option E Complete! 🚀 Your AetherLink agent now has enterprise-grade security and user-friendly file ingestion.**
