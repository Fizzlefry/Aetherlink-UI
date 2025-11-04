# 🔒 RBAC: Role-Based Access Control

**Status**: ✅ Operational
**Backward Compatible**: Yes (defaults to `viewer` if no `x-role` header)

---

## Overview

AetherLink Customer Ops now supports **three roles** for fine-grained access control:

| Role | Permissions | Use Case |
|------|------------|----------|
| **viewer** | Read-only (list, export, project) | Audit, reporting, analytics |
| **editor** | Read + Write (ingest, delete) | Content managers, data ops |
| **admin** | Full access (dashboard, evals, all ops) | Platform admins, DevOps |

---

## Usage

### Set Role via Header

```bash
# Viewer (read-only)
curl -H "x-api-key: test-key" \
     -H "x-role: viewer" \
     http://localhost:8000/knowledge/list

# Editor (can ingest/delete)
curl -H "x-api-key: test-key" \
     -H "x-role: editor" \
     -H "Content-Type: application/json" \
     -d '{"text":"New knowledge","source":"docs"}' \
     http://localhost:8000/knowledge/ingest

# Admin (full access including dashboard)
curl -H "x-admin-key: admin-secret-123" \
     -H "x-role: admin" \
     http://localhost:8000/
```

### Admin Key Auto-Grants Admin Role

If you provide a valid `x-admin-key`, you automatically get **admin** role (no `x-role` header needed):

```bash
# This works - admin key grants full access
curl -H "x-admin-key: admin-secret-123" \
     http://localhost:8000/
```

---

## Endpoint Protection Matrix

| Endpoint | Viewer | Editor | Admin |
|----------|--------|--------|-------|
| `GET /health` | ✅ | ✅ | ✅ |
| `GET /knowledge/list` | ✅ | ✅ | ✅ |
| `GET /knowledge/export` | ✅ | ✅ | ✅ |
| `GET /embed/project` | ✅ | ✅ | ✅ |
| `POST /knowledge/ingest` | ❌ | ✅ | ✅ |
| `POST /knowledge/ingest-url` | ❌ | ✅ | ✅ |
| `POST /knowledge/ingest-file` | ❌ | ✅ | ✅ |
| `DELETE /knowledge/delete` | ❌ | ✅ | ✅ |
| `GET /` (dashboard) | ❌ | ❌ | ✅ |
| `POST /evals/run` | ❌ | ❌ | ✅ |
| `GET /ops/*` | ❌ | ❌ | ✅ |

---

## Backward Compatibility

**No `x-role` header?** → Defaults to **`viewer`** role.

This ensures existing API clients continue working without modification. They get read-only access by default.

```bash
# These are equivalent
curl -H "x-api-key: test-key" http://localhost:8000/knowledge/list
curl -H "x-api-key: test-key" -H "x-role: viewer" http://localhost:8000/knowledge/list
```

---

## PowerShell Examples

```powershell
# Viewer (read-only)
$viewer = @{'x-api-key'='test-key'; 'x-role'='viewer'}
Invoke-RestMethod http://localhost:8000/knowledge/list -Headers $viewer

# Try to ingest (should fail with 403)
try {
    $json = @{'text'='test'; 'source'='rbac'} | ConvertTo-Json
    Invoke-RestMethod http://localhost:8000/knowledge/ingest `
        -Method Post -Headers $viewer -Body $json -ContentType 'application/json'
} catch {
    "✅ Viewer correctly blocked from writing: $($_.Exception.Message)"
}

# Editor (read + write)
$editor = @{'x-api-key'='test-key'; 'x-role'='editor'; 'Content-Type'='application/json'}
$body = @{'text'='Editor content'; 'source'='rbac_test'} | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/knowledge/ingest -Method Post -Headers $editor -Body $body

# Admin (full access)
$admin = @{'x-admin-key'='admin-secret-123'; 'x-role'='admin'}
Invoke-WebRequest http://localhost:8000/ -Headers $admin  # Dashboard access
```

---

## Testing

Run the comprehensive RBAC test suite:

```bash
python test_rbac.py
```

Expected output:
```
🔒 RBAC Verification Suite
✅ PASS  Viewer (read-only)
✅ PASS  Editor (read+write)
✅ PASS  Admin (full access)
✅ PASS  Admin key auto-role
✅ PASS  Invalid role rejection
✅ PASS  Backward compatibility

Score: 6/6 tests passed
🎉 ALL RBAC TESTS PASSED!
```

---

## Implementation Details

### Auth Flow

1. **Admin Key Check**: If `x-admin-key` matches, grant **admin** role immediately
2. **Role Header**: Parse `x-role` header (default: `viewer`)
3. **Validation**: Ensure role is one of: `admin`, `editor`, `viewer`
4. **Gate Check**: Verify role is in allowed list for endpoint
5. **Request State**: Store role in `request.state.role` for logging/audit

### Code Structure

- **`auth.py`**: New `require_role(*allowed)` dependency factory
- **`main.py`**: Three RBAC gates applied to endpoints:
  - `AdminOnly` → dashboard, evals, ops
  - `EditorOrAdmin` → ingest, delete
  - `AnyRole` → list, export, project (read-only)

---

## Security Best Practices

1. **Use Admin Key**: Always protect control plane with `API_ADMIN_KEY` in production
2. **Least Privilege**: Default to `viewer` for analysts, `editor` for content teams
3. **Audit Trail**: Log `request.state.role` in audit logs (see Option F: Audit Log)
4. **Rate Limiting**: Apply per-role limits if needed (e.g., stricter for editors)

---

## Troubleshooting

### "Access denied. Required role: editor or admin"

- Your `x-role` header is `viewer` (or missing)
- Solution: Add `-H "x-role: editor"` or use admin key

### "Invalid role: hacker"

- You provided an invalid role value
- Valid roles: `admin`, `editor`, `viewer`

### Dashboard returns 403 even with admin key

- Missing `x-admin-key` header or wrong value
- Check `API_ADMIN_KEY` in docker-compose.yml matches your header

---

## Future Enhancements

- **Per-Tenant Roles**: Different roles per tenant (e.g., `tenant1:editor`)
- **Custom Roles**: Define roles in config (e.g., `analyst`, `reviewer`)
- **JWT Tokens**: Replace headers with signed JWT for stateless auth
- **Role Hierarchies**: Auto-grant lower roles (e.g., `admin` includes `editor`)

---

**Next Step**: Option F (Background Ingestion) for async file/URL processing
