# 🧪 AetherLink v1.0 - Interactive Test Guide

**Ready to validate?** Follow this guide step-by-step in your browser.

---

## 🚀 Pre-Test Checklist

- [x] All services running (verified via `verify-health.ps1`)
- [x] Kafka events flowing (verified in logs)
- [x] No critical errors (verified in logs)
- [ ] Browser open to http://localhost:5173
- [ ] Keycloak credentials ready
- [ ] This guide open for reference

---

## 🎯 Test 1: AI Extract → Create Lead (THE BIG ONE)

### Step-by-Step:

1. **Open UI**
   ```
   Navigate to: http://localhost:5173
   ```

2. **Authenticate**
   - Login with Keycloak credentials
   - Should redirect back to CRM UI

3. **Expand Create Panel**
   - Look for "✨ Create New Lead (with AI Extract)" near the top
   - Click to expand the panel

4. **Paste Test Data**
   ```
   Sarah Chen
   Director of Engineering @ TechStart Inc
   sarah.chen@techstart.io
   415-555-0199
   Warm intro from Mike at CloudConf 2024
   ```

5. **Run AI Extract**
   - Click "Run AI Extract" button
   - Wait 1-2 seconds
   - **VERIFY**: Form fields should autofill:
     - Name: `Sarah Chen` or `(unknown)`
     - Email: `sarah.chen@techstart.io` ✅ (should always extract)
     - Company: `TechStart Inc` (if extracted)
     - Status: `new`

6. **Create the Lead**
   - Click "✅ Create Lead" button
   - Button changes to "Creating..."
   - Panel should close automatically

7. **Verify Lead Appears**
   - Look at the leads table
   - **New lead should appear** at top of list
   - Should show Sarah Chen's email

### ✅ Success Criteria:
- [ ] AI Extract button worked (no error)
- [ ] Email field populated correctly
- [ ] Create Lead succeeded (no error message)
- [ ] Lead appears in table
- [ ] Panel closed automatically

### ❌ If It Fails:
- Check browser console (F12) for errors
- Verify ApexFlow logs: `docker logs aether-apexflow --tail 20`
- Check AI Summarizer logs: `docker logs aether-ai-summarizer --tail 20`
- Document error in VALIDATION_REPORT.md

---

## 🧠 Test 2: AI Summary

### Step-by-Step:

1. **Select a Lead**
   - Click on ANY lead in the table (Sarah Chen or existing lead)
   - Lead drawer should open on the right side

2. **Click AI Summary**
   - Look for purple "✨ AI Summary" button
   - Click it
   - Button changes to "Summarizing..."

3. **Wait for Response**
   - Should take 1-3 seconds (stub mode)
   - Purple summary box should appear below button

4. **Verify Content**
   - **Stub mode (no Claude key)**: Should say something like:
     ```
     "✨ AI is wired correctly, but no Claude API key is configured..."
     ```
   - **Real Claude**: Natural language summary of lead activity

### ✅ Success Criteria:
- [ ] AI Summary button appeared
- [ ] Button showed loading state
- [ ] Summary box appeared (purple background)
- [ ] Stub mode message OR real summary text
- [ ] No error message

### ❌ If It Fails:
- Check network tab (F12) for API errors
- Verify: http://localhost:9108/health
- Check AI Summarizer logs
- Document error

---

## 📝 Test 3: AI Note Write-Back

### Step-by-Step:

1. **Prerequisites**
   - Lead drawer must be open (from Test 2)
   - AI summary must be showing in purple box

2. **Click "Add to Timeline"**
   - Look for "📥 Add to timeline" button in purple box
   - Click it
   - Button changes to "Saving..."

3. **Wait for Save**
   - Should take 1 second
   - Button returns to normal

4. **Scroll to Activity Timeline**
   - Scroll down in the lead drawer
   - Look for "Activity Timeline" section

5. **Verify Note Appears**
   - **New note should be at the top** of timeline
   - Should contain the AI summary text
   - Should show your username as author
   - Should have recent timestamp

### ✅ Success Criteria:
- [ ] "Add to timeline" button worked
- [ ] No error message appeared
- [ ] Note appears in activity timeline
- [ ] Note contains AI summary text
- [ ] Timestamp is recent

### ❌ If It Fails:
- Check if note was created: Refresh drawer
- Check ApexFlow logs for note creation
- Check Kafka logs for `note_added` event
- Document error

---

## 📊 Test 4: Grafana Observability

### Step-by-Step:

1. **Open Grafana**
   ```
   Navigate to: http://localhost:3000
   ```

2. **Login**
   - Username: `admin`
   - Password: `admin`
   - May prompt to change password (skip for now)

3. **Navigate to Explore**
   - Click "Explore" in left sidebar (compass icon)

4. **Select Loki Data Source**
   - Dropdown at top should say "Loki" or select it

5. **Run Query 1: Notifications**
   ```logql
   {service="notifications-consumer"} |= "matched rule="
   ```
   - Click "Run query"
   - **VERIFY**: Should see logs with "matched rule=notify-on-qualified" etc.

6. **Run Query 2: AI Service**
   ```logql
   {service="ai-summarizer"} |= "POST /summaries"
   ```
   - Click "Run query"
   - **VERIFY**: Should see AI request logs

7. **Run Query 3: Lead Creation**
   ```logql
   {service="apexflow"} |= "lead.created"
   ```
   - Click "Run query"
   - **VERIFY**: Should see lead creation events

### ✅ Success Criteria:
- [ ] Grafana loads successfully
- [ ] Loki data source accessible
- [ ] Notifications query returns results
- [ ] AI service query returns results
- [ ] ApexFlow query returns results

### ❌ If It Fails:
- Check if Loki is running: `docker ps | findstr loki`
- Check Grafana logs: `docker logs aether-grafana --tail 20`
- Verify Prometheus is scraping: http://localhost:9090
- Document issue

---

## 🎉 Final Verification

### If ALL Tests Passed:

1. **Update VALIDATION_REPORT.md**
   ```markdown
   **Functional Flow**: ✅ **PASSED** - All browser tests successful
   **Observability**: ✅ **PASSED** - Grafana queries working
   **Ready for v1.0.0 Tag**: ✅ **YES**
   ```

2. **Tag the Release**
   ```powershell
   cd c:\Users\jonmi\OneDrive\Documents\AetherLink
   git add .
   git commit -m "v1.0 validation complete - all tests passed"
   git tag -a v1.0.0 -m "AetherLink v1.0: AI-Powered CRM - Validated and Production-Ready"
   git push origin main --tags
   ```

3. **Celebrate!** 🎉
   - You have a working, AI-powered CRM
   - Complete event-driven architecture
   - Full observability stack
   - Production-ready baseline

### If ANY Test Failed:

1. **Document the Failure**
   - Which test failed?
   - What was the error message?
   - What did you see instead of expected result?

2. **Add to VALIDATION_REPORT.md**
   ```markdown
   ## ❌ Failed Tests

   ### Test X: [Name]
   - **Status**: FAILED
   - **Error**: [error message]
   - **Expected**: [what should happen]
   - **Actual**: [what actually happened]
   - **Next Action**: [how to fix]
   ```

3. **Create Issue**
   - Document in `docs/ISSUES.md`
   - Assign priority
   - Plan fix

4. **Fix & Retest**
   - Address the issue
   - Re-run ONLY the failed test
   - Update validation report

---

## 🔍 Troubleshooting Quick Reference

### "AI Extract returned empty fields"
- **Check**: AI Summarizer logs
- **Fix**: Verify service is running: http://localhost:9108/health

### "Create Lead button disabled"
- **Cause**: Name field is required
- **Fix**: Make sure Name field has value (even if "(unknown)")

### "Lead doesn't appear in table"
- **Check**: Browser console for errors
- **Fix**: Refresh page manually
- **Verify**: Check ApexFlow logs for lead creation

### "AI Summary button does nothing"
- **Check**: Network tab for failed request
- **Fix**: Restart AI Summarizer: `docker restart aether-ai-summarizer`

### "Note doesn't appear in timeline"
- **Check**: Did the button show "Saving..."?
- **Fix**: Close and reopen drawer to refresh
- **Verify**: Check ApexFlow `/leads/{id}/notes` endpoint

### "Grafana queries return no results"
- **Check**: Is Loki running? `docker ps | findstr loki`
- **Fix**: Check time range (set to "Last 15 minutes")
- **Verify**: Check if any logs exist: `{service=~".+"}`

---

## 📞 Support

**If stuck**:
1. Check `docs/V1.0_VALIDATION_CHECKLIST.md` for detailed steps
2. Review `docs/ARCHITECTURE.md` for system overview
3. Check service logs: `docker logs [service-name] --tail 50`
4. Run health script: `.\scripts\verify-health.ps1`

**Before asking for help**:
- Document what you tried
- Capture error messages
- Save screenshots of failures
- Check all service logs

---

**Ready? Let's validate v1.0! 🚀**

Start with Test 1: Open http://localhost:5173
