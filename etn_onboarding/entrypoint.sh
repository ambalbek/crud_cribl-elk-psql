#!/bin/sh
set -e

echo "Running database migrations..."
flask --app wsgi:app db upgrade

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
