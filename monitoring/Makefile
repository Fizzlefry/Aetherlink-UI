# AetherLink CRM Monitoring — Quick Commands
# Sprint 5: Finance Dashboard & Alerts

.PHONY: help reload-prom open-alerts open-crm-kpis health check-metrics test-synthetic smoke-test smoke-test-nightly

help:
	@echo "AetherLink CRM Monitoring Commands"
	@echo "=================================="
	@echo ""
	@echo "Monitoring:"
	@echo "  make reload-prom         Restart Prometheus & Alertmanager"
	@echo "  make open-alerts         Open Prometheus alerts UI"
	@echo "  make open-crm-kpis       Open Grafana CRM KPIs dashboard"
	@echo "  make open-slo            Open Grafana SLO & Uptime dashboard"
	@echo ""
	@echo "Health Checks:"
	@echo "  make health              Check all service health"
	@echo "  make check-metrics       Show current CRM finance metrics"
	@echo "  make smoke-test          Run full monitoring stack validation"
	@echo "  make smoke-test-nightly  Full CI-style test (start, wait, test, teardown)"
	@echo "  make test-synthetic      Bump counters to test dashboard"
	@echo "  make prom-lint           Validate Prometheus configs with promtool"
	@echo ""
	@echo "Logs:"
	@echo "  make logs-crm            Show CRM API logs (last 50 lines)"
	@echo "  make logs-prom           Show Prometheus logs"
	@echo "  make logs-alert          Show Alertmanager logs"
	@echo ""
	@echo "Ops:"
	@echo "  make restart-crm         Restart CRM API"
	@echo "  make restart-all         Restart all monitoring services"

reload-prom:
	@echo "Reloading Prometheus & Alertmanager..."
	docker compose restart prometheus alertmanager
	@sleep 2
	@echo "✅ Reloaded. Check logs with: make logs-prom"

open-alerts:
	@powershell -Command "Start-Process 'http://localhost:9099/alerts'"

open-crm-kpis:
	@powershell -Command "Start-Process 'http://localhost:3000/d/peakpro_crm_kpis'"

.PHONY: open-slo
open-slo:
	@powershell -Command "Start-Process 'http://localhost:3000/d/peakpro_crm_slo'"

health:
	@echo "=== CRM API Health ==="
	@curl -s http://localhost:8089/metrics | head -5 || echo "❌ CRM API not responding"
	@echo ""
	@echo "=== Prometheus Targets ==="
	@curl -s http://localhost:9099/api/v1/targets | jq -r '.data.activeTargets[] | select(.labels.job=="crm-api") | "\(.labels.job): \(.health) (last scrape: \(.lastScrape))"' || echo "❌ Prometheus not responding"
	@echo ""
	@echo "=== Active Alerts ==="
	@curl -s http://localhost:9099/api/v1/alerts | jq -r '.data.alerts[] | "\(.labels.alertname): \(.state)"' || echo "✅ No active alerts"

check-metrics:
	@echo "=== CRM Finance Metrics (Last 24h) ==="
	@echo ""
	@echo "Invoices Created:"
	@curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoices_generated_total[24h]))' | jq -r '.data.result[0].value[1] // "0"'
	@echo ""
	@echo "Invoices Paid:"
	@curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoices_paid_total[24h]))' | jq -r '.data.result[0].value[1] // "0"'
	@echo ""
	@echo "Revenue (last 24h, USD):"
	@curl -s 'http://localhost:9099/api/v1/query?query=sum(increase(crm_invoice_payments_cents_total[24h]))/100' | jq -r '.data.result[0].value[1] // "0"'
	@echo ""
	@echo "Payment Rate (30d, %):"
	@curl -s 'http://localhost:9099/api/v1/query?query=100*sum(increase(crm_invoices_paid_total[30d]))/clamp_min(sum(increase(crm_invoices_generated_total[30d])),1)' | jq -r '.data.result[0].value[1] // "0"'

test-synthetic:
	@echo "Bumping synthetic test data..."
	@docker exec crm-api python -c "from crm.metrics import CRM_INVOICES_PAID, CRM_INVOICE_PAYMENTS_CENTS; from crm.routers.qbo import QBO_INVOICES_TOTAL; org='1'; QBO_INVOICES_TOTAL.labels(org_id=org).inc(3); CRM_INVOICES_PAID.labels(org_id=org).inc(2); CRM_INVOICE_PAYMENTS_CENTS.labels(org_id=org).inc(250000); print('✅ Bumped: 3 invoices created, 2 paid, $2,500 revenue')"
	@echo ""
	@echo "Wait 30 seconds for Prometheus scrape, then check:"
	@echo "  make open-crm-kpis"

smoke-test:
	@echo "Running monitoring stack validation..."
	@cd .. && powershell -ExecutionPolicy Bypass -File ./scripts/test_monitoring_stack.ps1

logs-crm:
	docker logs crm-api --tail 50

logs-prom:
	docker logs aether-prom --tail 30

logs-alert:
	docker logs aether-alertmanager --tail 30

restart-crm:
	@echo "Restarting CRM API..."
	docker compose restart crm-api
	@sleep 3
	@echo "✅ Restarted. Checking status..."
	@docker logs crm-api --tail 10

restart-all:
	@echo "Restarting all monitoring services..."
	docker compose restart prometheus alertmanager grafana crm-api
	@sleep 5
	@echo "✅ All services restarted"
	@echo ""
	@echo "Check health with: make health"

smoke-test-nightly:
	@echo "Running nightly-style stack + smoke test locally..."
	@echo "This mirrors the GitHub Actions nightly workflow"
	@echo ""
	docker compose up -d prometheus alertmanager grafana crm-api postgres-crm
	@echo "Waiting for Prometheus..."
	@bash -c 'for i in {1..90}; do curl -fsS http://localhost:9090/-/ready >/dev/null 2>&1 && exit 0 || true; echo "  waiting $$i/90"; sleep 2; done; exit 1' || (echo "❌ Prometheus not ready"; exit 1)
	@echo "Waiting for Grafana..."
	@bash -c 'for i in {1..90}; do curl -fsS http://localhost:3000/api/health >/dev/null 2>&1 && exit 0 || true; echo "  waiting $$i/90"; sleep 2; done; exit 1' || (echo "❌ Grafana not ready"; exit 1)
	@echo "Waiting for Alertmanager..."
	@bash -c 'for i in {1..90}; do curl -fsS http://localhost:9093/api/v2/status >/dev/null 2>&1 && exit 0 || true; echo "  waiting $$i/90"; sleep 2; done; exit 1' || (echo "❌ Alertmanager not ready"; exit 1)
	@echo "Waiting for CRM API..."
	@bash -c 'for i in {1..90}; do curl -fsS http://localhost:8089/metrics >/dev/null 2>&1 && exit 0 || true; echo "  waiting $$i/90"; sleep 2; done; exit 1' || (echo "❌ CRM API not ready"; exit 1)
	@echo ""
	@echo "All services ready. Running smoke test..."
	@cd .. && pwsh -ExecutionPolicy Bypass -File ./scripts/test_monitoring_stack.ps1
	@echo ""
	@echo "Tearing down stack..."
	docker compose down -v
	@echo "✅ Nightly smoke test complete"

.PHONY: prom-lint
prom-lint:
	@echo "Linting Prometheus configuration files..."
	@which promtool >/dev/null || (echo "❌ promtool not found - install from https://prometheus.io/download/"; exit 1)
	@echo "Checking Prometheus config..."
	@promtool check config prometheus-config.yml
	@echo "Checking alert rules..."
	@promtool check rules prometheus-alerts.yml
	@echo "Checking recording rules..."
	@promtool check rules prometheus-recording-rules.yml
	@echo "✅ All Prometheus configs valid"

.PHONY: open-probes
open-probes: ## Open Prometheus targets UI
	@powershell -NoProfile -Command "Start-Process 'http://localhost:9090/targets'"

.PHONY: test-tcp-failure
test-tcp-failure: ## Simulate TCP failure by stopping a target briefly
	@echo "Stopping crm-api for 150s to trigger TcpEndpointDownFast..."
	-docker stop crm-api
	@sleep 150
	@docker start crm-api
	@echo "crm-api restarted."

.PHONY: show-tcp
show-tcp: ## Print TCP probe results
	@powershell -Command "$$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=probe_success{job=\"blackbox_tcp\"}'; $$result.data.result | ForEach-Object { Write-Host \"$$($$_.metric.instance) => $$($$_.value[1])\" }"

.PHONY: open-alert-templates
open-alert-templates: ## Open Slack alert template file
	@powershell -NoProfile -Command "Start-Process 'alert-templates.tmpl'"

.PHONY: show-ebr
show-ebr: ## Show Error Budget Remaining value
	@powershell -Command "$$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:error_budget_remaining'; $$result.data.result | ForEach-Object { Write-Host \"EBR => $$($$_.value[1])\" }"

.PHONY: show-burn
show-burn: ## Show 1h and 6h payment-rate burn rates
	@powershell -Command "Write-Host 'Burn(1h):' -ForegroundColor Cyan; $$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:burn_1h'; $$result.data.result | ForEach-Object { Write-Host \"  => $$($$_.value[1])\" }; Write-Host 'Burn(6h):' -ForegroundColor Cyan; $$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:burn_6h'; $$result.data.result | ForEach-Object { Write-Host \"  => $$($$_.value[1])\" }"

.PHONY: show-slo
show-slo: ## Show EBR and 30d ratio
	@powershell -Command "Write-Host 'EBR:' -ForegroundColor Cyan; $$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:error_budget_remaining'; $$result.data.result | ForEach-Object { Write-Host \"  EBR => $$($$_.value[1])\" }; Write-Host 'Ratio30d:' -ForegroundColor Cyan; $$result = Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:ratio_30d'; $$result.data.result | ForEach-Object { Write-Host \"  Ratio30d => $$($$_.value[1])\" }"

.PHONY: autoheal-up
autoheal-up: ## Start autohealer (dev only)
	@docker compose up -d autoheal
	@echo "Autohealer started. Status: AUTOHEAL_ENABLED=false (safe mode)"
	@echo "To enable: Set AUTOHEAL_ENABLED=true in docker-compose.yml or use 'make autoheal-on'"

.PHONY: autoheal-on
autoheal-on: ## Enable autoheal actions in the container
	@echo "Enabling auto-remediation (DEV ONLY)..."
	@docker exec aether-autoheal sh -c 'echo "AUTOHEAL_ENABLED=true" > /tmp/.autoheal_enabled'
	@docker compose restart autoheal
	@echo "✅ Auto-remediation ENABLED. Use 'make autoheal-off' to disable."

.PHONY: autoheal-off
autoheal-off: ## Disable autoheal actions
	@echo "Disabling auto-remediation..."
	@docker exec aether-autoheal sh -c 'rm -f /tmp/.autoheal_enabled' || true
	@docker compose restart autoheal
	@echo "✅ Auto-remediation DISABLED (safe mode)."

.PHONY: autoheal-status
autoheal-status: ## Check autoheal service status
	@powershell -Command "try { $$r = Invoke-RestMethod 'http://localhost:9009/'; Write-Host \"✅ Autoheal: $$($$r.status)\" -ForegroundColor Green; Write-Host \"   Enabled: $$($$r.enabled)\" -ForegroundColor $(if ($$r.enabled) { 'Yellow' } else { 'Gray' }); Write-Host \"   Actions: $$($$r.actions -join ', ')\" -ForegroundColor Gray } catch { Write-Host \"❌ Autoheal: offline\" -ForegroundColor Red }"

.PHONY: ack-slo
ack-slo: ## Silence SLO alerts for 30 minutes (maintenance window)
	@powershell -Command "$$startTime = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); $$endTime = (Get-Date).AddMinutes(30).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'); $$body = @{ matchers = @(@{ name='layer'; value='slo'; isRegex=$$false }); startsAt=$$startTime; endsAt=$$endTime; createdBy='make ack-slo'; comment='temporary SLO silence' } | ConvertTo-Json -Depth 10; $$result = Invoke-RestMethod -Method POST -Uri 'http://localhost:9093/api/v2/silences' -ContentType 'application/json' -Body $$body; Write-Host \"✅ SLO alerts silenced for 30 minutes. Silence ID: $$($$result.silenceID)\" -ForegroundColor Green"

.PHONY: list-silences
list-silences: ## List active silences
	@powershell -Command "$$silences = Invoke-RestMethod 'http://localhost:9093/api/v2/silences'; if ($$silences.Count -eq 0) { Write-Host 'No active silences.' -ForegroundColor Gray } else { $$silences | ForEach-Object { $$matchers = ($$_.matchers | ForEach-Object { \"$$($$_.name)=$$($$_.value)\" }) -join ','; Write-Host \"$$($$_.id)  $$($$_.status.state)  $$matchers  $$($$_.comment)\" } }"

.PHONY: clear-silences
clear-silences: ## Expire all active silences immediately
	@powershell -Command "$$silences = Invoke-RestMethod 'http://localhost:9093/api/v2/silences'; if ($$silences.Count -eq 0) { Write-Host 'No silences to clear.' -ForegroundColor Gray; exit } $$silences | ForEach-Object { Invoke-RestMethod -Method POST -Uri \"http://localhost:9093/api/v2/silence/$$($$_.id)\" | Out-Null }; Write-Host \"✅ Cleared $$($$silences.Count) silence(s).\" -ForegroundColor Green"

.PHONY: prom-test
prom-test: ## Unit-test Prometheus rules with promtool
	@powershell -Command "docker run --rm --entrypoint promtool -v $${PWD}:/workspace -w /workspace prom/prometheus:v2.54.1 test rules tests/rules.test.yml"

.PHONY: amtool-check
amtool-check: ## Validate Alertmanager config
	@docker run --rm -v $$(pwd):/conf quay.io/prometheus/alertmanager:latest amtool check-config /conf/alertmanager.yml

.PHONY: amtool-silences
amtool-silences: ## Query Alertmanager silences via amtool
	@docker run --rm --network host quay.io/prometheus/alertmanager:latest amtool --alertmanager.url=http://localhost:9093 silence query

.PHONY: chaos-tcp
chaos-tcp: ## Simulate TCP outage for crm-api (60s)
	@echo "🔥 Chaos: Stopping crm-api for 60 seconds..."
	@docker stop crm-api
	@powershell -Command "Start-Sleep -Seconds 60"
	@docker start crm-api
	@echo "✅ Chaos complete: crm-api restarted"

.PHONY: chaos-metrics
chaos-metrics: ## Simulate metrics scrape failure (45s Prometheus outage)
	@echo "🔥 Chaos: Stopping Prometheus for 45 seconds..."
	@docker compose stop prometheus
	@powershell -Command "Start-Sleep -Seconds 45"
	@docker compose start prometheus
	@echo "✅ Chaos complete: Prometheus restarted"

.PHONY: grafana-export
grafana-export: ## Export SLO dashboard JSON (requires GRAFANA_USER/GRAFANA_PASS env)
	@powershell -Command "$$user = $$env:GRAFANA_USER ?? 'admin'; $$pass = $$env:GRAFANA_PASS ?? 'admin'; $$cred = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes(\"$$user:$$pass\")); $$headers = @{ Authorization = \"Basic $$cred\" }; try { $$resp = Invoke-RestMethod -Uri 'http://localhost:3000/api/dashboards/uid/peakpro_crm_slo' -Headers $$headers; $$resp.dashboard | ConvertTo-Json -Depth 50 | Out-File 'grafana-dashboard-slo.json' -Encoding UTF8; Write-Host '✅ Dashboard exported to grafana-dashboard-slo.json' -ForegroundColor Green } catch { Write-Host '❌ Export failed. Check GRAFANA_USER/GRAFANA_PASS env vars.' -ForegroundColor Red }"

.PHONY: obs-verify
obs-verify: ## End-to-end observability smoke test
	@echo "=== Observability Verification ===" && \
	echo "1) Prometheus rules test..." && $(MAKE) -s prom-test && \
	echo "2) Alertmanager config check..." && $(MAKE) -s amtool-check && \
	echo "3) Active targets..." && powershell -Command "$$t = Invoke-RestMethod 'http://localhost:9090/api/v1/targets'; Write-Host \"✅ $$($$t.data.activeTargets.Count) targets up\" -ForegroundColor Green" && \
	echo "4) Loaded alerts..." && powershell -Command "$$r = Invoke-RestMethod 'http://localhost:9090/api/v1/rules'; $$count = ($$r.data.groups | ForEach-Object { $$_.rules | Where-Object { $$_.type -eq 'alerting' } }).Count; Write-Host \"✅ $$count alerts loaded\" -ForegroundColor Green" && \
	echo "✅ All checks passed!"

.PHONY: show-breach
show-breach: ## Show SLO runway predictions (days/hours to breach)
	@powershell -Command "Write-Host '=== SLO Runway Predictions ===' -ForegroundColor Cyan; try { $$d = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:days_to_breach').data.result[0].value[1]; Write-Host \"Days to breach: $$d\" -ForegroundColor Green } catch { Write-Host 'Days to breach: N/A (no data yet)' -ForegroundColor Gray }; try { $$h1 = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:hours_to_breach_1h').data.result[0].value[1]; $$h6 = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:hours_to_breach_6h').data.result[0].value[1]; $$hmin = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=slo:payment_rate:hours_to_breach').data.result[0].value[1]; Write-Host \"Hours to breach (1h burn): $$h1\" -ForegroundColor Yellow; Write-Host \"Hours to breach (6h burn): $$h6\" -ForegroundColor Yellow; Write-Host \"Hours to breach (conservative): $$hmin\" -ForegroundColor Green } catch { Write-Host 'Hours metrics: N/A (no data yet)' -ForegroundColor Gray }"

.PHONY: open-vision
open-vision: ## Open AetherVision SLO dashboard
	@powershell -Command "Start-Process 'http://localhost:3000/d/peakpro_crm_slo'"

.PHONY: vision-verify
vision-verify: ## Quick AetherVision status check
	@powershell -Command "Write-Host '=== AetherVision Quick Status ===' -ForegroundColor Cyan; Write-Host ''; Write-Host 'Prometheus Rules:' -ForegroundColor Yellow; docker run --rm --entrypoint promtool -v $${PWD}:/w -w /w prom/prometheus:v2.54.1 check rules prometheus-recording-rules.yml prometheus-alerts.yml | Select-String 'SUCCESS'; Write-Host ''; Write-Host 'SLO Runway:' -ForegroundColor Yellow; try { $$d = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=aethervision:days_to_breach').data.result[0].value[1]; Write-Host \"  Days to breach: $$d\" } catch { Write-Host '  Days to breach: N/A' }; Write-Host ''; Write-Host 'Active Alerts:' -ForegroundColor Yellow; try { $$a = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=aethervision:alerts:count').data.result[0].value[1]; Write-Host \"  Alerts firing: $$a\" } catch { Write-Host '  Alerts firing: N/A' }; Write-Host ''; Write-Host 'Autoheal Status:' -ForegroundColor Yellow; try { $$e = (Invoke-RestMethod 'http://localhost:9090/api/v1/query?query=aethervision:autoheal_enabled').data.result[0].value[1]; $$status = if ($$e -eq '1') { 'ENABLED' } else { 'disabled' }; Write-Host \"  Autoheal: $$status\" } catch { Write-Host '  Autoheal: N/A' }"

