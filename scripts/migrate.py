import pathlib

import psycopg

from database import database_url

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "db" / "migrations"


def apply_migration(connection, migration_path) -> None:
    print("apply", migration_path.name)
    with connection.transaction():
        connection.execute(migration_path.read_text(encoding="utf-8"))
        connection.execute("INSERT INTO schema_migrations VALUES (%s)", (migration_path.name,))


def migrate(conninfo: str) -> None:
    with psycopg.connect(conninfo, autocommit=True) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)")
        applied = {name for (name,) in connection.execute("SELECT name FROM schema_migrations")}
        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_path.name not in applied:
                apply_migration(connection, migration_path)


if __name__ == "__main__":
    migrate(database_url())
