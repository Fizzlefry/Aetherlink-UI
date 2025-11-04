#!/usr/bin/env pwsh
# A/B Experiment Smoke Test & Validation Script
# Automates the complete testing workflow: enable → seed → outcomes → validate → promote

param(
    [string]$ApiBase = "http://localhost:8000",
    [int]$NumLeads = 10,
    [switch]$EnableExperiment,
    [switch]$SkipSeeding,
    [switch]$PromoteWinner
)

$ErrorActionPreference = "Continue"

Write-Host "`n🧪 A/B Experiment Smoke Test" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

# Step 0: Check API is running
Write-Host "`n[Step 0] Checking API health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$ApiBase/health" -ErrorAction Stop
    Write-Host "  ✅ API is running" -ForegroundColor Green
} catch {
    Write-Host "  ❌ API not responding. Start it first:" -ForegroundColor Red
    Write-Host "     cd pods/customer_ops; .\scripts\dev.ps1 -Up -Verify" -ForegroundColor White
    exit 1
}

# Step 1: Enable experiment (if requested)
if ($EnableExperiment) {
    Write-Host "`n[Step 1] Enabling followup_timing experiment..." -ForegroundColor Yellow
    Write-Host "  ⚠️  Manual step required:" -ForegroundColor Yellow
    Write-Host "     Edit api/experiments.py line 104:" -ForegroundColor White
    Write-Host "     EXPERIMENTS['followup_timing'].enabled = True" -ForegroundColor Cyan
    Write-Host "`n  Press Enter after editing..." -ForegroundColor Yellow
    Read-Host
} else {
    Write-Host "`n[Step 1] Skipping experiment enable (use -EnableExperiment to prompt)" -ForegroundColor Gray
}

# Step 2: Check experiment status
Write-Host "`n[Step 2] Checking experiment dashboard..." -ForegroundColor Yellow
try {
    $experiments = Invoke-RestMethod -Uri "$ApiBase/ops/experiments" -ErrorAction Stop
    $exp = $experiments.experiments.followup_timing

    if ($exp.enabled) {
        Write-Host "  ✅ followup_timing experiment is ENABLED" -ForegroundColor Green
        Write-Host "     Variants: $($exp.variants -join ', ')" -ForegroundColor Gray
        Write-Host "     Min sample: $($exp.min_sample_size)" -ForegroundColor Gray
    } else {
        Write-Host "  ⚠️  followup_timing experiment is DISABLED" -ForegroundColor Yellow
        Write-Host "     Enable it first (use -EnableExperiment)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Failed to check experiments: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Seed test leads (if not skipped)
if (-not $SkipSeeding) {
    Write-Host "`n[Step 3] Creating $NumLeads test leads..." -ForegroundColor Yellow

    $leadIds = @()
    $variantCounts = @{}

    for ($i = 1; $i -le $NumLeads; $i++) {
        try {
            $body = @{
                name = "AB Test Lead $i"
                phone = "555-000$i"
                details = "Urgent metal roof quote - test lead $i for A/B experiment"
            } | ConvertTo-Json

            $response = Invoke-RestMethod -Method POST -Uri "$ApiBase/v1/lead" `
                -ContentType "application/json" -Body $body -ErrorAction Stop

            $leadIds += $response.lead_id

            # Track variants (if available in response)
            if ($response.PSObject.Properties['experiment_variant']) {
                $variant = $response.experiment_variant
                if (-not $variantCounts.ContainsKey($variant)) {
                    $variantCounts[$variant] = 0
                }
                $variantCounts[$variant]++
            }

            Write-Host "  ✅ Lead $i created: $($response.lead_id)" -ForegroundColor Green
            Start-Sleep -Milliseconds 200  # Rate limit
        } catch {
            Write-Host "  ⚠️  Lead $i failed: $_" -ForegroundColor Yellow
        }
    }

    Write-Host "`n  Created $($leadIds.Count) leads" -ForegroundColor Green
    if ($variantCounts.Count -gt 0) {
        Write-Host "  Variant distribution:" -ForegroundColor Gray
        $variantCounts.GetEnumerator() | ForEach-Object {
            Write-Host "    $($_.Key): $($_.Value)" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "`n[Step 3] Skipping lead seeding (use without -SkipSeeding to create leads)" -ForegroundColor Gray
    $leadIds = @()
}

# Step 4: Record outcomes (simulate conversion funnel)
if ($leadIds.Count -gt 0) {
    Write-Host "`n[Step 4] Recording outcomes for test leads..." -ForegroundColor Yellow

    # Simulate realistic conversion funnel:
    # 30% booked, 20% ghosted, 20% qualified, 10% callback, 10% nurture, 10% lost
    $outcomes = @("booked", "ghosted", "qualified", "callback", "nurture", "lost")
    $weights = @(0.3, 0.2, 0.2, 0.1, 0.1, 0.1)

    $outcomeStats = @{}

    for ($i = 0; $i -lt $leadIds.Count; $i++) {
        $leadId = $leadIds[$i]

        # Weighted random outcome
        $rand = Get-Random -Minimum 0.0 -Maximum 1.0
        $cumulative = 0.0
        $outcome = "lost"

        for ($j = 0; $j -lt $weights.Count; $j++) {
            $cumulative += $weights[$j]
            if ($rand -lt $cumulative) {
                $outcome = $outcomes[$j]
                break
            }
        }

        # Track stats
        if (-not $outcomeStats.ContainsKey($outcome)) {
            $outcomeStats[$outcome] = 0
        }
        $outcomeStats[$outcome]++

        try {
            $body = @{
                outcome = $outcome
                time_to_conversion = if ($outcome -eq "booked") { Get-Random -Minimum 600 -Maximum 3600 } else { $null }
                notes = "A/B test outcome"
            } | ConvertTo-Json

            $response = Invoke-RestMethod -Method POST -Uri "$ApiBase/v1/lead/$leadId/outcome" `
                -ContentType "application/json" -Body $body -ErrorAction Stop

            Write-Host "  ✅ Lead $leadId → $outcome" -ForegroundColor Green
            Start-Sleep -Milliseconds 150
        } catch {
            Write-Host "  ⚠️  Failed to record outcome for $leadId : $_" -ForegroundColor Yellow
        }
    }

    Write-Host "`n  Outcome distribution:" -ForegroundColor Green
    $outcomeStats.GetEnumerator() | Sort-Object -Property Value -Descending | ForEach-Object {
        $pct = [math]::Round(($_.Value / $leadIds.Count) * 100, 1)
        Write-Host "    $($_.Key): $($_.Value) ($pct%)" -ForegroundColor Gray
    }
}

# Step 5: Check experiment metrics
Write-Host "`n[Step 5] Checking experiment metrics..." -ForegroundColor Yellow

try {
    $experiments = Invoke-RestMethod -Uri "$ApiBase/ops/experiments" -ErrorAction Stop
    $exp = $experiments.experiments.followup_timing

    if ($exp.significance) {
        $sig = $exp.significance

        Write-Host "`n  Significance Test Results:" -ForegroundColor Cyan
        Write-Host "    Significant: $($sig.significant)" -ForegroundColor $(if ($sig.significant) { "Green" } else { "Yellow" })
        Write-Host "    P-value: $($sig.p_value)" -ForegroundColor Gray

        if ($sig.winner) {
            Write-Host "    Winner: $($sig.winner) 🏆" -ForegroundColor Green
        } else {
            Write-Host "    Winner: None yet" -ForegroundColor Gray
        }

        if ($sig.variants) {
            Write-Host "`n  Per-Variant Stats:" -ForegroundColor Cyan
            $sig.variants.PSObject.Properties | ForEach-Object {
                $variant = $_.Name
                $stats = $_.Value
                Write-Host "    $variant :" -ForegroundColor White
                Write-Host "      Samples: $($stats.samples)" -ForegroundColor Gray
                Write-Host "      Conversions: $($stats.conversions)" -ForegroundColor Gray
                Write-Host "      Rate: $([math]::Round($stats.rate * 100, 2))%" -ForegroundColor $(if ($stats.rate -gt 0.25) { "Green" } else { "Yellow" })
            }
        }
    } else {
        Write-Host "  ⚠️  No significance data available yet" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ Failed to check experiment stats: $_" -ForegroundColor Red
}

# Step 6: Check Prometheus metrics
Write-Host "`n[Step 6] Checking Prometheus metrics..." -ForegroundColor Yellow

try {
    $metrics = Invoke-WebRequest -Uri "$ApiBase/metrics" -ErrorAction Stop
    $metricsText = $metrics.Content

    $experimentMetrics = $metricsText -split "`n" | Where-Object {
        $_ -match "experiment_" -and $_ -notmatch "^#"
    }

    if ($experimentMetrics.Count -gt 0) {
        Write-Host "  ✅ Found $($experimentMetrics.Count) experiment metrics" -ForegroundColor Green

        # Show sample metrics
        $experimentMetrics | Select-Object -First 10 | ForEach-Object {
            Write-Host "    $_" -ForegroundColor Gray
        }

        if ($experimentMetrics.Count -gt 10) {
            Write-Host "    ... and $($experimentMetrics.Count - 10) more" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ⚠️  No experiment metrics found (may need to wait for outcomes)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️  Failed to fetch metrics: $_" -ForegroundColor Yellow
}

# Step 7: Promote winner (if requested)
if ($PromoteWinner) {
    Write-Host "`n[Step 7] Promoting winner..." -ForegroundColor Yellow

    try {
        $result = Invoke-RestMethod -Method POST -Uri "$ApiBase/ops/experiments/followup_timing/promote" -ErrorAction Stop

        if ($result.ok) {
            Write-Host "  🏆 Winner promoted: $($result.promoted)" -ForegroundColor Green
            Write-Host "     P-value: $($result.p_value)" -ForegroundColor Gray
            Write-Host "     Chi-square: $($result.chi_square)" -ForegroundColor Gray
        } else {
            Write-Host "  ⚠️  Promotion failed: $($result.error)" -ForegroundColor Yellow
            if ($result.p_value) {
                Write-Host "     P-value: $($result.p_value) (need < 0.05)" -ForegroundColor Gray
            }
        }
    } catch {
        Write-Host "  ❌ Failed to promote: $_" -ForegroundColor Red
    }
} else {
    Write-Host "`n[Step 7] Skipping winner promotion (use -PromoteWinner to attempt)" -ForegroundColor Gray
}

# Summary
Write-Host "`n" + "=" * 60 -ForegroundColor Cyan
Write-Host "Smoke Test Summary" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan

Write-Host "`n✅ Next Steps:" -ForegroundColor Green
Write-Host "  1. Enable experiment: Edit api/experiments.py, set enabled=True" -ForegroundColor White
Write-Host "  2. Run smoke test: .\test_ab_experiment.ps1 -NumLeads 20" -ForegroundColor White
Write-Host "  3. Monitor metrics: curl http://localhost:8000/metrics | Select-String experiment_" -ForegroundColor White
Write-Host "  4. Check dashboard: curl http://localhost:8000/ops/experiments | jq '.'" -ForegroundColor White
Write-Host "  5. Wait for significance (>100 samples, p < 0.05)" -ForegroundColor White
Write-Host "  6. Promote winner: .\test_ab_experiment.ps1 -PromoteWinner" -ForegroundColor White

Write-Host "`n📚 Documentation:" -ForegroundColor Cyan
Write-Host "  - Complete guide: AB_EXPERIMENTS_GUIDE.md" -ForegroundColor White
Write-Host "  - Quick reference: SHIPPED_AB_EXPERIMENTS.md" -ForegroundColor White

Write-Host ""
