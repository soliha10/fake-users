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

## Rebuild lookup data

`data/*.csv` is committed, so this step is only needed when the word lists change.
It downloads the sources in `data/SOURCES.md` into `.raw/` and needs `requirements-dev.txt`.

```sh
.venv/bin/python scripts/build_lookup_data.py --raw-dir .raw
.venv/bin/python scripts/load_lookup.py
```

`scripts/load_lookup.py` replaces all lookup rows in one transaction, so a failed load keeps
the old data. `scripts/migrate.py` applies each file in `db/migrations/` once, in order.

## Test and benchmark

```sh
.venv/bin/python -m pytest
.venv/bin/python scripts/benchmark.py --label local --host "my laptop"
```

The benchmark runs each case three times and writes `benchmarks/<label>.json` plus a Markdown table.

## Deploy

1. Create a PostgreSQL 15+ database (Neon or Render).
2. With `DATABASE_URL` pointing at it, run `scripts/migrate.py` and `scripts/load_lookup.py`.
3. Create a Render Blueprint from `render.yaml` and set `DATABASE_URL`.
