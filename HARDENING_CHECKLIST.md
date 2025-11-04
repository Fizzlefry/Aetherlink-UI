# Production Hardening Checklist

## Security

- [x] **API Keys**: Dynamic hot-reload via `/ops/reload-auth` ✅
- [ ] **Prod defaults**: Set `REQUIRE_API_KEY=true` in production
- [ ] **CORS**: Restrict `CORS_ORIGINS` (not `*`) for production
- [ ] **Docs**: Disable `/docs` and `/redoc` in production if needed
- [ ] **Secrets**: Use secret manager instead of `.env` for prod keys
- [ ] **Rate limiting**: Add modest limits to `/ops/*` routes (e.g., 5/minute)

## Observability

- [x] **Health endpoints**: `/health`, `/healthz`, `/readyz` ✅
- [ ] **Access logs**: Ensure INFO-level logging with request IDs
- [ ] **JSON logs**: Structured logging for production
- [ ] **Metrics**: Prometheus `/metrics` endpoint configured
- [ ] **Alerting**: Set up alerts for health check failures

## Database

- [x] **Schema drift**: Alembic check in pre-commit & CI ✅
- [x] **Backups**: Nightly automated backups with retention ✅
- [x] **Restore tested**: E2E verify includes backup/restore ✅
- [ ] **Connection pooling**: Review SQLAlchemy pool settings for load
- [ ] **Read replicas**: Consider for high-traffic scenarios

## Operations

- [x] **One-command launch**: `.\makefile.ps1 up` ✅
- [x] **One-command health**: `.\makefile.ps1 health` ✅
- [x] **One-command verify**: `.\makefile.ps1 verify` ✅
- [x] **Hot-reload**: API keys without restart ✅
- [ ] **Docker healthcheck**: Add to compose for `up --wait`
- [ ] **Zero-downtime deploy**: Blue-green or rolling updates

## Testing

- [x] **Coverage**: HTML reports via `.\coverage.ps1` ✅
- [x] **E2E verify**: Backup → restore → health ✅
- [ ] **Load testing**: Baseline API throughput
- [ ] **Chaos testing**: Redis/Postgres failure scenarios

## Notes

- All checkboxes with ✅ are implemented and tested
- Remaining items are recommended for production hardening
- Drift guard, backups, and hot-reload are high-leverage wins already in place
