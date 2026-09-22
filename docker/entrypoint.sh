#!/bin/bash
set -euo pipefail

python - <<'PY'
import os
import time
import psycopg

url = os.getenv('DATABASE_URL')
if not url:
    raise RuntimeError('DATABASE_URL is required')

host = os.getenv('POSTGRES_HOST', 'db')
port = os.getenv('POSTGRES_PORT', '5432')
user = os.getenv('POSTGRES_USER', 'postgres')
password = os.getenv('POSTGRES_PASSWORD', 'postgres')
dbname = os.getenv('POSTGRES_DB', 'plan_gastos')

for _ in range(30):
    try:
        conn = psycopg.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        conn.close()
        break
    except Exception:
        time.sleep(2)
else:
    raise RuntimeError('PostgreSQL is not available')
PY

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
