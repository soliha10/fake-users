# Faker in SQL

A web app that generates reproducible fake users. All generation runs in PostgreSQL stored
routines; Flask only validates input, calls `fake_users()`, and renders HTML.

- Live app: https://fake-users-tvxj.onrender.com
- Library documentation: https://soliha10.github.io/fake-users/
- Benchmark: [docs/benchmark.md](docs/benchmark.md)
- Data sources and licenses: [data/SOURCES.md](data/SOURCES.md)

## Run locally

Requires Docker and Python 3.11+.

```sh
docker compose up -d --wait
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
.venv/bin/python scripts/migrate.py
.venv/bin/python scripts/load_lookup.py
.venv/bin/gunicorn app.main:app --bind 127.0.0.1:8000
```

## Test and benchmark

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/benchmark.py --label local --host "my laptop"
```

## Deploy

1. Create a PostgreSQL 15+ database (Neon or Render).
2. With `DATABASE_URL` pointing at it, run `scripts/migrate.py` and `scripts/load_lookup.py`.
3. Create a Render Blueprint from `render.yaml` and set `DATABASE_URL`.
