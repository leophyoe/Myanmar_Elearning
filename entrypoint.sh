#!/bin/bash
set -e

echo "=== Future Tech Cyber Range - Initializing Services ==="

# If POSTGRES_HOST is configured, wait for it to become ready
if [ -n "$POSTGRES_HOST" ] && [ "$POSTGRES_HOST" != "localhost" ]; then
    echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."
    while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
        sleep 0.5
    done
    echo "PostgreSQL is online and accepting connections."
fi

# Run database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files if in production mode
if [ "$DJANGO_SETTINGS_MODULE" = "config.settings.production" ]; then
    echo "Collecting static assets..."
    python manage.py collectstatic --noinput
fi

echo "=== Initialization Complete. Launching Application Process ==="
exec "$@"

