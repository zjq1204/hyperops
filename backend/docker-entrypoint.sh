#!/bin/bash
set -e

echo "Waiting for database to be ready..."
python manage.py wait_for_db --settings=core.settings

echo "Running migrations..."
python manage.py migrate --settings=core.settings --noinput

echo "Collecting static files..."
python manage.py collectstatic --settings=core.settings --noinput --clear

echo "Starting Gunicorn..."
exec "$@"
