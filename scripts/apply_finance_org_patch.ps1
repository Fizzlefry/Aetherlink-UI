# apply_finance_org_patch.ps1
# - Adds $org dashboard variable
# - Rewrites 4 finance panel queries to use :by_org recordings
# - Inserts a "Finance (Sprint 5)" row above those panels
# - Restarts Grafana container

$ErrorActionPreference = 'Stop'

# Find repo root (navigate up from script location)
$ScriptRoot = Split-Path -Parent $PSCommandPath
$RepoRoot = Split-Path -Parent $ScriptRoot
Set-Location $RepoRoot

# Paths
$DashPath = "monitoring\grafana-provisioning\dashboards\peakpro-crm-kpis.json"

if (-not (Test-Path $DashPath)) {
    throw "Dashboard JSON not found at: $DashPath (from $RepoRoot)"
}Write-Host "Loading dashboard from $DashPath..."

# Load dashboard JSON
$dashRaw = Get-Content -Raw -Path $DashPath
$json = $dashRaw | ConvertFrom-Json

# Ensure templating container exists
if (-not $json.PSObject.Properties.Name.Contains("templating") -or $null -eq $json.templating) {
    $json | Add-Member -NotePropertyName templating -NotePropertyValue ([pscustomobject]@{ list = @() })
}
elseif (-not $json.templating.PSObject.Properties.Name.Contains("list") -or $null -eq $json.templating.list) {
    $json.templating | Add-Member -NotePropertyName list -NotePropertyValue @()
}

# Try to inherit datasource from first panel
$inheritedDS = $null
if ($json.panels -and $json.panels.Count -gt 0) {
    if ($json.panels[0].PSObject.Properties.Name -contains "datasource") {
        $inheritedDS = $json.panels[0].datasource
    }
}

# Add $org variable if missing
$hasOrgVar = $false
foreach ($v in $json.templating.list) {
    if ($v.name -eq "org") { $hasOrgVar = $true; break }
}

if (-not $hasOrgVar) {
    $orgVar = [pscustomobject]@{
        name       = "org"
        type       = "query"
        label      = "Org"
        hide       = 0
        refresh    = 1
        includeAll = $false
        multi      = $false
        query      = "label_values(crm_invoices_generated_total,org_id)"
        regex      = ""
        sort       = 0
        current    = @{
            selected = $false
            text     = ""
            value    = ""
        }
        options    = @()
    }
    if ($inheritedDS) {
        $orgVar | Add-Member -NotePropertyName datasource -NotePropertyValue $inheritedDS
    }
    $json.templating.list += $orgVar
    Write-Host "[+] Added Grafana variable: org"
}
else {
    Write-Host "[i] Grafana variable org already exists - leaving as-is."
}

# Panel rewrites: map panel titles to :by_org recording expressions
$targetMap = @{}
$targetMap["Invoices Created (24h)"] = 'crm:invoices_created_24h:by_org{org_id=\"$org\"}'
$targetMap["Invoices Paid (24h)"] = 'crm:invoices_paid_24h:by_org{org_id=\"$org\"}'
$targetMap["Revenue (7 days)"] = 'crm:revenue_usd:by_org{org_id=\"$org\"}'
$targetMap["Invoice Payment Rate (30d)"] = 'crm:payment_rate_30d_pct:by_org{org_id=\"$org\"}'

# Collect finance panels and track min Y for row insertion
$financePanels = @()
$minY = [int]::MaxValue

foreach ($p in $json.panels) {
    if ($null -eq $p.title) { continue }
    if ($targetMap.ContainsKey($p.title)) {
        if ($p.PSObject.Properties.Name -contains "targets" -and $p.targets.Count -gt 0) {
            $p.targets[0].expr = $targetMap[$p.title]
            $financePanels += $p
            if ($p.PSObject.Properties.Name -contains "gridPos") {
                $y = [int]$p.gridPos.y
                if ($y -lt $minY) { $minY = $y }
            }
            Write-Host "[+] Rewrote panel '$($p.title)' -> $($targetMap[$p.title])"
        }
    }
}

if ($financePanels.Count -eq 0) {
    Write-Warning "No finance panels matched by title. Skipping row insert."
}
else {
    # Insert a compact row above the earliest finance panel cluster
    $rowY = if ($minY -eq [int]::MaxValue) { 20 } else { [Math]::Max($minY - 1, 0) }
    $rowPanel = [pscustomobject]@{
        type      = "row"
        title     = "Finance (Sprint 5)"
        gridPos   = @{ h = 1; w = 24; x = 0; y = $rowY }
        collapsed = $false
        panels    = @()
    }

    # Only add if a row with same title doesn't already exist
    $rowExists = $false
    foreach ($p in $json.panels) {
        if ($p.type -eq "row" -and $p.title -eq "Finance (Sprint 5)") { $rowExists = $true; break }
    }
    if (-not $rowExists) {
        # Insert row just before the first panel that starts at/after rowY
        $insertIndex = 0
        for ($i = 0; $i -lt $json.panels.Count; $i++) {
            $gp = $json.panels[$i].gridPos
            if ($gp -and $gp.y -ge $rowY) { $insertIndex = $i; break }
            $insertIndex = $i + 1
        }
        $before = @()
        $after = @()
        if ($insertIndex -gt 0) { $before = $json.panels[0..($insertIndex - 1)] }
        if ($insertIndex -le $json.panels.Count - 1) { $after = $json.panels[$insertIndex..($json.panels.Count - 1)] }
        $json.panels = @($before + @($rowPanel) + $after)
        Write-Host "[+] Inserted row panel 'Finance (Sprint 5)' at y=$rowY"
    }
    else {
        Write-Host "[i] Row 'Finance (Sprint 5)' already exists - leaving as-is."
    }
}

# Save dashboard JSON (use depth 100, PowerShell's max)
$json | ConvertTo-Json -Depth 100 -Compress:$false | Out-File -FilePath $DashPath -Encoding UTF8
Write-Host "[+] Saved updated dashboard -> $DashPath"

# Restart Grafana
try {
    Write-Host "[+] Restarting Grafana container..."
    Push-Location "monitoring"
    docker compose restart grafana | Out-Null
    Pop-Location
    Start-Sleep -Seconds 3
    Write-Host "[+] Grafana restart complete."
}
catch {
    Write-Warning "Couldn't restart Grafana automatically. Restart it manually if needed."
}

Write-Host ""
Write-Host "Done! Open Grafana -> PeakPro CRM KPIs and select an org from the org dropdown to filter the finance panels."
Write-Host "Dashboard URL: http://localhost:3000/d/peakpro_crm_kpis"
