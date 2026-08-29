#!/bin/sh
set -e

echo "Initialising database..."
python -c "
from wsgi import app
from app.extensions import db
with app.app_context():
    db.create_all()
    print('Tables created (idempotent)')
"

echo "Stamping Alembic head..."
flask --app wsgi:app db stamp head 2>/dev/null || true

echo "Running pending migrations..."
flask --app wsgi:app db upgrade || true

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 wsgi:app
