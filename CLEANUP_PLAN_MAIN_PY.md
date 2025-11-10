# Main.py Deduplication Plan

## Issue
`services/command-center/main.py` contains **4 complete duplicate copies** of the application code (~1100 lines each = 4400 total lines).

## Evidence
```bash
$ grep -n "^app = FastAPI" services/command-center/main.py
1014:app = FastAPI(title="AetherLink Command Center", version="0.2.0", lifespan=lifespan)
2039:app = FastAPI(title="AetherLink Command Center", version="0.2.0", lifespan=lifespan)
3064:app = FastAPI(title="AetherLink Command Center", version="0.2.0", lifespan=lifespan)
4089:app = FastAPI(title="AetherLink Command Center", version="0.2.0", lifespan=lifespan)
```

## Impact

### Current State
- ✅ **Server runs fine** - Python only executes the first `app =` definition
- ✅ **Recovery timeline works** - Our additions are in the first section
- ❌ **Cannot import as module** - Prometheus metrics register 4 times → ValueError
- ❌ **File is 4x larger than needed** - Harder to maintain
- ❌ **Git diffs are confusing** - Changes might affect multiple sections

### What Works
- FastAPI server startup (`uvicorn main:app`)
- All endpoints including `/ops/remediate/history`
- Recovery event logging
- Adaptive auto-responder

### What Doesn't Work
- `python -c "from main import ..."`  (triggers Prometheus duplication error)
- Direct module imports for testing

## Root Cause
Likely from incremental phase development where new versions were appended rather than replacing old sections.

## Cleanup Strategy

### Option 1: Safe Conservative Approach (RECOMMENDED)
**Keep first complete section (lines 1-~1100), remove rest**

**Steps:**
1. **Backup current file**
   ```bash
   cp services/command-center/main.py services/command-center/main.py.backup.$(date +%Y%m%d_%H%M%S)
   ```

2. **Identify end of first complete section**
   - Find where app endpoints end (around line 1100)
   - Look for natural break before second `app = FastAPI`

3. **Create deduplicated version**
   ```bash
   head -n 1100 services/command-center/main.py > services/command-center/main_deduped.py
   ```

4. **Verify completeness**
   - Check that all imports are present
   - Ensure recovery timeline functions exist (lines 23-66)
   - Verify `/ops/remediate/history` endpoint exists (lines 1047-1101)
   - Confirm `_apply_adaptive_action` has recovery logging

5. **Test deduplicated version**
   ```bash
   # Try importing (should work now)
   python -c "from main_deduped import record_remediation_event; print('Import OK')"

   # Start server with deduplicated version
   uvicorn main_deduped:app --reload

   # Test endpoints
   curl http://localhost:8010/test
   curl http://localhost:8010/ops/remediate/history
   ```

6. **If tests pass, swap files**
   ```bash
   mv services/command-center/main.py services/command-center/main_OLD.py
   mv services/command-center/main_deduped.py services/command-center/main.py
   ```

### Option 2: Identify Most Complete Section
**Compare sections to find which has the most features**

Some sections might have newer features than others. Would need to:
1. Compare function counts in each section
2. Check for Phase XXIII, XXIX, XXXI features
3. Identify which section has all recent features
4. Keep that one, discard others

### Option 3: Merge Unique Features
**Extract unique code from each section**

Riskier but most thorough:
1. Extract all function/class definitions from all 4 sections
2. Deduplicate by name
3. For duplicates, keep the most recent/complete version
4. Rebuild single unified file

## Pre-Cleanup Checklist

Before attempting cleanup:
- [ ] Verify `main.aetherlink.stable.py` is a good known-working backup
- [ ] Test current `main.py` can start successfully
- [ ] Confirm all critical endpoints work
  - [ ] `GET /test`
  - [ ] `GET /ops/remediate/history`
  - [ ] `GET /health` or equivalent
  - [ ] Prometheus `/metrics`
- [ ] Document which Phase features are in active use
- [ ] Check if any sections have unique features not in others

## Post-Cleanup Verification

After cleanup:
- [ ] Server starts without errors
- [ ] Can import as module: `python -c "from main import app"`
- [ ] All endpoints respond correctly
- [ ] Prometheus metrics work (no duplication errors)
- [ ] Recovery timeline logging works
- [ ] Adaptive auto-responder functions
- [ ] File size reduced to ~1100 lines
- [ ] Git diff is clean and understandable

## Recovery Plan

If cleanup breaks something:
```bash
# Restore from backup
cp services/command-center/main.py.backup.TIMESTAMP services/command-center/main.py

# Or use git
git checkout services/command-center/main.py

# Or use stable version
cp services/command-center/main.aetherlink.stable.py services/command-center/main.py
```

## Timeline

**Priority: MEDIUM**
- Not blocking current operations
- Should be done before major new features
- Can be deferred if actively developing other features

**Estimated Time:**
- Option 1 (Conservative): 30-60 minutes
- Option 2 (Compare): 1-2 hours
- Option 3 (Merge): 2-4 hours

## Decision

**Recommendation:** Use **Option 1 (Conservative)** during a low-activity period.

**Rationale:**
- Lowest risk
- Fastest to execute
- Easy to verify
- Easy to roll back
- Recovery timeline feature already in first section

**When to do it:**
- After current Phase work is stable
- Before adding Grafana integration (clean foundation)
- During a maintenance window or low-traffic period

## Notes

- The duplicates appear to be exact copies, not variations with different features
- First section (lines 1-1100) contains our recovery timeline implementation
- Server currently works because Python stops at first `app = FastAPI` definition
- Cleanup will make the codebase more maintainable and enable module imports for testing

## Related Files
- `services/command-center/main.py` (current, 4398 lines)
- `services/command-center/main.aetherlink.stable.py` (backup)
- `services/command-center/main_minimal.py` (minimal version)
- `services/command-center/main_test_fastapi.py` (test version)
