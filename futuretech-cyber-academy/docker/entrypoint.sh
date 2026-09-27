#!/bin/bash
set -e

echo "=== Future Tech Cyber Security Academy - Initializing ==="

if [ -n "$POSTGRES_HOST" ] && [ "$POSTGRES_HOST" != "localhost" ]; then
    echo "Waiting for PostgreSQL ($POSTGRES_HOST:$POSTGRES_PORT)..."
    while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
        sleep 0.5
    done
    echo "PostgreSQL is online and ready."
fi

# Apply migrations
python backend/manage.py migrate --noinput

exec "$@"

