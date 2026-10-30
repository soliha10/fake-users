import csv
import pathlib

import psycopg

from database import database_url

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
LOOKUP_TABLES = ["locales", "names", "titles", "address_parts", "places", "format_templates",
                 "email_domains", "eye_colors", "physical_distributions", "markov_transitions"]


def copy_table(connection, table: str) -> None:
    with open(DATA_DIR / f"{table}.csv", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        columns = ", ".join(next(reader))
        with connection.cursor().copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
            for csv_row in reader:
                copy.write_row(csv_row)
    print("loaded", table)


def load(conninfo: str) -> None:
    with psycopg.connect(conninfo) as connection:
        connection.execute("TRUNCATE " + ", ".join(LOOKUP_TABLES))
        for table in LOOKUP_TABLES:
            copy_table(connection, table)
        connection.execute("CALL fake_rebuild_weights()")
    with psycopg.connect(conninfo, autocommit=True) as connection:
        connection.execute("ANALYZE")


if __name__ == "__main__":
    load(database_url())
