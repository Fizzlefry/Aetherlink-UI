# 🛡️ WINDOWS HARDENING GUIDE

> Real-world resilience tweaks for production monitoring on Windows

---

## 🎯 Quick Start

**One-liner setup (recommended):**
```powershell
.\scripts\setup-automation.ps1
```

This will:
1. ✅ Create auto-start task with 1-minute delay (lets Docker Desktop finish)
2. ✅ Create nightly backup task (1:30 AM daily)
3. ✅ Optionally create startup task (for reboots with no login)
4. ✅ Optionally import executive dashboard via API
5. ✅ Apply all hardening tweaks automatically

**Manual hardening (if needed):**
```powershell
# Make tasks resilient (run even if you're not logged in)
schtasks /Change /TN "AetherLink-Monitoring-Autostart" /RU "%USERNAME%" /RL HIGHEST /ENABLE
schtasks /Change /TN "AetherLink-Monitoring-Backup"    /RU "%USERNAME%" /RL HIGHEST /ENABLE

# Add 1-minute delay on logon (lets Docker Desktop start first)
schtasks /Change /TN "AetherLink-Monitoring-Autostart" /DELAY 0001:00

# Optional: Also run at system startup (covers reboots where no one logs in)
schtasks /Create /TN "AetherLink-Monitoring-AtStartup" /SC ONSTART /RL HIGHEST ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"%USERPROFILE%\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1\" -Silent"
```

---

## 🔍 30-Second Verification

```powershell
# Check tasks exist & enabled
schtasks /Query /TN "AetherLink-Monitoring-Autostart"
schtasks /Query /TN "AetherLink-Monitoring-Backup"

# Dry-run your autostart (doesn't wait for logon)
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1" -Silent

# Quick health ping
.\scripts\ship-sanity-sweep.ps1
```

**Expected Output:**
- ✅ Both tasks show "Status: Ready" and "Next Run Time"
- ✅ Monitoring stack starts without errors
- ✅ Health check confirms 3 services running, 8 rules, 5 alerts

---

## ⚠️ Watch-Outs (Learned the Hard Way)

### 1. OneDrive Path Quoting

**Problem:** OneDrive paths have spaces (`C:\Users\jonmi\OneDrive\Documents\...`) which break task creation if not quoted properly.

**Solution:** Your scripts already use proper quoting (`"$scriptsPath\..."`). If tasks fail, check History tab in Task Scheduler.

**Manual fix (if needed):**
```powershell
# Always use double quotes around full path
/TR "powershell -NoProfile -ExecutionPolicy Bypass -File \"$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1\" -Silent"
```

---

### 2. Docker Desktop Startup Race Condition

**Problem:** Scheduled task runs immediately on logon, but Docker Desktop takes 30-60s to initialize. Monitoring stack fails to start.

**Solution:** 1-minute delay on auto-start task (already applied by `setup-automation.ps1`).

```powershell
# Verify delay is set
schtasks /Query /TN "AetherLink-Monitoring-Autostart" /FO LIST /V | Select-String "Delay"

# Expected: Delay Time: 0:01:00
```

**Manual fix (if needed):**
```powershell
schtasks /Change /TN "AetherLink-Monitoring-Autostart" /DELAY 0001:00
```

---

### 3. ExecutionPolicy Blocks Scripts

**Problem:** Windows default ExecutionPolicy is `Restricted`, which blocks PowerShell scripts.

**Solution:** Scripts already launch with `-ExecutionPolicy Bypass` flag. No system-wide policy changes needed.

**If tasks still fail:**
```powershell
# Check current policy
Get-ExecutionPolicy

# Set to RemoteSigned (one-time, requires admin)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

---

### 4. Windows Sleep Kills Metrics Collection

**Problem:** Laptop sleeps at night, backups and metrics collection pause.

**Solution (for 24/7 metrics):**

**Option A - Prevent sleep (simple):**
```powershell
# Open Power Options
powercfg.cpl

# Set "Put the computer to sleep" to "Never"
```

**Option B - Wake for scheduled tasks (advanced):**
```powershell
# Enable wake timers
powercfg /change monitor-timeout-ac 0
powercfg /change standby-timeout-ac 0

# Task Scheduler already has "Wake the computer to run this task" enabled
```

**Option C - VM deployment (enterprise):**
- Deploy to always-on VM or server
- Windows Server has better task scheduling defaults

---

### 5. Firewall Blocks Dashboard Access

**Problem:** Want to view Grafana from other devices on LAN, but Windows Firewall blocks port 3000.

**Solution (localhost-only = no changes needed):**

Current config: Dashboards only accessible from `localhost:3000` (safe default).

**If you need LAN access:**
```powershell
# Allow Grafana (port 3000) through firewall
New-NetFirewallRule -DisplayName "AetherLink Grafana" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow

# Allow Prometheus (port 9090) through firewall
New-NetFirewallRule -DisplayName "AetherLink Prometheus" -Direction Inbound -LocalPort 9090 -Protocol TCP -Action Allow

# Allow Alertmanager (port 9093) through firewall
New-NetFirewallRule -DisplayName "AetherLink Alertmanager" -Direction Inbound -LocalPort 9093 -Protocol TCP -Action Allow
```

**Then update docker-compose.yml to bind to all interfaces:**
```yaml
services:
  grafana:
    ports:
      - "0.0.0.0:3000:3000"  # Was: "3000:3000"
```

---

### 6. Task Runs But Doesn't Work

**Problem:** Task Scheduler shows "Last Run: 0x0 (Success)" but monitoring stack isn't running.

**Root causes:**
1. Docker Desktop not running
2. Script path has typo
3. User permissions mismatch

**Debug checklist:**
```powershell
# 1. Check task history
taskschd.msc
# Navigate to: Task Scheduler Library → Find task → History tab

# 2. Test script manually
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\OneDrive\Documents\AetherLink\scripts\start-monitoring.ps1" -Silent

# 3. Verify Docker Desktop is running
docker ps

# 4. Check task user matches current user
schtasks /Query /TN "AetherLink-Monitoring-Autostart" /FO LIST /V | Select-String "Run As User"
# Should match: DESKTOP-...\jonmi (your username)
```

---

## 🔧 Advanced Management

### Modify Backup Schedule

**Change to 3:00 AM:**
```powershell
schtasks /Change /TN "AetherLink-Monitoring-Backup" /ST 03:00
```

**Change to weekly (Sunday 2 AM):**
```powershell
schtasks /Delete /TN "AetherLink-Monitoring-Backup" /F
schtasks /Create /TN "AetherLink-Monitoring-Backup" /SC WEEKLY /D SUN /ST 02:00 /RL HIGHEST ^
  /TR "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%USERPROFILE%\OneDrive\Documents\AetherLink\scripts\backup-monitoring.ps1\""
```

---

### Temporary Disable/Enable

**Disable auto-start (e.g., for maintenance):**
```powershell
schtasks /Change /TN "AetherLink-Monitoring-Autostart" /DISABLE
```

**Re-enable:**
```powershell
schtasks /Change /TN "AetherLink-Monitoring-Autostart" /ENABLE
```

---

### Force Task to Run Now

```powershell
# Test auto-start immediately
schtasks /Run /TN "AetherLink-Monitoring-Autostart"

# Test backup immediately
schtasks /Run /TN "AetherLink-Monitoring-Backup"
```

---

### Export/Import Tasks (for cloning to another machine)

**Export:**
```powershell
schtasks /Query /TN "AetherLink-Monitoring-Autostart" /XML > AetherLink-Autostart.xml
schtasks /Query /TN "AetherLink-Monitoring-Backup" /XML > AetherLink-Backup.xml
```

**Import on new machine:**
```powershell
# Update paths in XML first (change username)
schtasks /Create /TN "AetherLink-Monitoring-Autostart" /XML AetherLink-Autostart.xml
schtasks /Create /TN "AetherLink-Monitoring-Backup" /XML AetherLink-Backup.xml
```

---

## 🚀 New Machine Quick Setup

**Zero to production in 5 minutes:**

```powershell
# 1. Clone repo
git clone https://github.com/your-org/AetherLink
cd AetherLink

# 2. Start Docker Desktop (wait 1 minute)
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
Start-Sleep -Seconds 60

# 3. Run automation setup (creates tasks + imports dashboard)
.\scripts\setup-automation.ps1
# When prompted:
#   - Create startup task? Y
#   - Import executive dashboard? Y

# 4. Verify
schtasks /Query /TN "AetherLink-*"
.\scripts\ship-sanity-sweep.ps1

# 5. Done! Monitoring is now set-and-forget
```

---

## 📊 Resilience Features Applied

| Feature | Status | Benefit |
|---------|--------|---------|
| Run whether user is logged in or not | ✅ Enabled | Tasks survive lock screen, RDP disconnects |
| 1-minute delay on logon | ✅ Enabled | Waits for Docker Desktop to initialize |
| Highest privileges | ✅ Enabled | Avoids permission issues |
| Silent mode (WindowStyle Hidden) | ✅ Enabled | No popup windows interrupting work |
| Nightly backups | ✅ Enabled | Auto-recovery from config mistakes |
| Auto-start on logon | ✅ Enabled | Zero manual intervention |
| Optional startup task | ⚪ Optional | Covers reboots with no login (servers) |

---

## 🎯 Final Checklist

**Before declaring "set-and-forget":**

- [ ] `.\scripts\setup-automation.ps1` completed without errors
- [ ] `schtasks /Query /TN "AetherLink-*"` shows all tasks as "Ready"
- [ ] `.\scripts\ship-sanity-sweep.ps1` passes (3 services, 8 rules, 5 alerts)
- [ ] Grafana dashboard shows "No recent traffic" (not red errors) when idle
- [ ] Executive dashboard imported (if needed): http://localhost:3000
- [ ] Test logoff/logon: Monitoring auto-starts within 2 minutes
- [ ] Check backup folder next morning: `.\monitoring\backups\`

**Once checklist passes:**
- 🟢 **PRODUCTION READY**
- 🟢 **FULLY AUTOMATED**
- 🟢 **ZERO MAINTENANCE**
- 🟢 **SURVIVES REBOOTS**
- 🟢 **SURVIVES SLEEP/HIBERNATION** (if power settings configured)

---

## 🆘 Troubleshooting One-Liners

```powershell
# Task not running?
schtasks /Query /TN "AetherLink-Monitoring-Autostart" /FO LIST /V

# Docker not starting?
docker ps
docker-compose -f .\monitoring\docker-compose.yml up -d

# Backup not working?
.\scripts\backup-monitoring.ps1
dir .\monitoring\backups\

# Dashboard not loading?
Start-Process "http://localhost:3000"
# Login: admin / admin

# Nuclear option (reset everything)
schtasks /Delete /TN "AetherLink-Monitoring-Autostart" /F
schtasks /Delete /TN "AetherLink-Monitoring-Backup" /F
schtasks /Delete /TN "AetherLink-Monitoring-AtStartup" /F
.\scripts\setup-automation.ps1
```

---

## 📚 Reference Links

**Internal Docs:**
- [FINAL_SHIP_CHECKLIST.md](FINAL_SHIP_CHECKLIST.md) - Complete deployment summary
- [FINAL_POLISH.md](FINAL_POLISH.md) - Automation setup guide
- [QUICK_REFERENCE_CARD.md](QUICK_REFERENCE_CARD.md) - Print-friendly cheat sheet
- [ON_CALL_RUNBOOK.md](ON_CALL_RUNBOOK.md) - Alert response playbook

**Windows Task Scheduler:**
- [Microsoft Docs: Task Scheduler Overview](https://docs.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page)
- [Schtasks.exe Command Reference](https://docs.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks)

**Docker Desktop:**
- [Docker Desktop for Windows Docs](https://docs.docker.com/desktop/windows/)
- [Configure Docker to Start on Boot](https://docs.docker.com/engine/install/linux-postinstall/#configure-docker-to-start-on-boot)

---

## ✨ What's Different from Basic Setup?

**Before hardening:**
- ❌ Manual start required after every reboot
- ❌ Task fails if Docker Desktop hasn't started yet
- ❌ Task stops if you lock screen or RDP disconnects
- ❌ No backups unless you remember to run script
- ❌ Dashboard import requires manual UI clicks

**After hardening:**
- ✅ Monitoring auto-starts on every logon/reboot
- ✅ 1-minute delay waits for Docker Desktop
- ✅ Tasks run in background even when locked/disconnected
- ✅ Nightly backups run automatically at 1:30 AM
- ✅ Dashboard import via one-liner script (optional during setup)

---

**Status:** 🟢 **PRODUCTION-HARDENED - WINDOWS QUIRKS HANDLED**

Last updated: 2025-11-02
