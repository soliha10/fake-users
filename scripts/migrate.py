"""Apply db/migrations/*.sql in order, each file once. Usage: python scripts/migrate.py"""
import os
import pathlib

import psycopg
from dotenv import load_dotenv

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "db" / "migrations"


def migrate(conninfo: str) -> None:
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in done:
                continue
            print("apply", path.name)
            with conn.transaction():
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations VALUES (%s)", (path.name,))


if __name__ == "__main__":
    load_dotenv()
    migrate(os.environ["DATABASE_URL"])
