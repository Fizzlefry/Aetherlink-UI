#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Waiting for database to be ready..."

# Wait for PostgreSQL to be available (max 60 seconds)
for i in {1..60}; do
    if python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('db-apexflow', 5432)); s.close()" 2>/dev/null; then
        echo "✅ Database is ready"
        break
    fi
    echo "⏳ Waiting for database... ($i/60)"
    sleep 1
done

echo "🔄 Running database migrations..."
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✅ Migrations complete"
else
    echo "❌ Migration failed"
    exit 1
fi

echo "🚀 Starting ApexFlow API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8080
