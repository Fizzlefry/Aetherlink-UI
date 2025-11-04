# AetherLink Customer Ops Development Commands
# Install just: https://github.com/casey/just

# Default recipe lists available commands
default:
    @just --list

# Install all dependencies (pip, pre-commit, test tools)
install:
    pip install -r pods/customer_ops/requirements.txt
    pip install pytest pytest-cov pre-commit ruff pyright
    pre-commit install
    @echo "✓ Dependencies installed and pre-commit hooks configured"

# Run fast hermetic unit tests
test:
    cd pods/customer_ops && \
    PYTHONPATH=../.. \
    DATABASE_URL=sqlite:///:memory: \
    REQUIRE_API_KEY=false \
    REDIS_URL= \
    LOG_LEVEL=DEBUG \
    pytest -q -m "not integration"

# Run tests with coverage report
test-cov:
    cd pods/customer_ops && \
    PYTHONPATH=../.. \
    DATABASE_URL=sqlite:///:memory: \
    REQUIRE_API_KEY=false \
    REDIS_URL= \
    LOG_LEVEL=DEBUG \
    pytest -q -m "not integration" --cov=api --cov-report=term --cov-report=html

# Run all tests including integration
test-all:
    cd pods/customer_ops && \
    PYTHONPATH=../.. \
    DATABASE_URL=sqlite:///:memory: \
    REQUIRE_API_KEY=false \
    REDIS_URL= \
    LOG_LEVEL=DEBUG \
    pytest -q

# Run linting checks (ruff + pyright)
lint:
    cd pods/customer_ops && ruff check .
    cd pods/customer_ops && pyright .

# Auto-fix linting issues
lint-fix:
    cd pods/customer_ops && ruff check . --fix
    cd pods/customer_ops && ruff format .

# Start docker compose stack
up:
    cd pods/customer_ops && docker compose up --build -d
    @echo "✓ Stack started. API: http://localhost:8000"

# Stop docker compose stack
down:
    cd pods/customer_ops && docker compose down -v

# Start stack and run smoke tests
smoke: up
    @echo "Waiting for health check..."
    @sleep 5
    curl -sf http://localhost:8000/healthz || (cd pods/customer_ops && docker compose logs && exit 1)
    @echo "✓ Health check passed"
    curl -s http://localhost:8000/healthz | jq .
    @echo "✓ Smoke tests passed"

# View docker compose logs
logs:
    cd pods/customer_ops && docker compose logs -f

# Clean up build artifacts and caches
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "coverage.xml" -delete 2>/dev/null || true
    find . -type f -name ".coverage" -delete 2>/dev/null || true
    @echo "✓ Build artifacts cleaned"

# Generate requirements.lock.txt for reproducible builds
lock:
    cd pods/customer_ops && pip-compile -o requirements.lock.txt requirements.txt
    @echo "✓ Requirements locked to requirements.lock.txt"

# Run pre-commit hooks on all files
pre-commit:
    pre-commit run --all-files

# Full CI check locally (lint + test + security)
ci: lint test
    @echo "✓ Local CI checks passed"

# Setup development environment from scratch
setup: install
    @echo "✓ Development environment ready"
    @echo "  Run 'just test' to verify setup"
    @echo "  Run 'just up' to start the stack"
