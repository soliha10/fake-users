"""Replace all lookup rows with data/*.csv and rebuild cum_weight.

The load runs in one transaction, so a failure leaves the old data in place.
Usage: python scripts/load_lookup.py
"""
import csv
import os
import pathlib

import psycopg
from dotenv import load_dotenv

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
TABLES = ["locales", "names", "titles", "address_parts", "places", "format_templates",
          "email_domains", "eye_colors", "physical_distributions", "markov_transitions"]


def load(conninfo: str) -> None:
    with psycopg.connect(conninfo) as conn:
        conn.execute("TRUNCATE " + ", ".join(TABLES))
        for table in TABLES:
            with open(DATA / f"{table}.csv", newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                columns = ", ".join(next(reader))
                with conn.cursor().copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
                    for row in reader:
                        copy.write_row(row)
            print("loaded", table)
        conn.execute("CALL fake_rebuild_weights()")
        conn.commit()
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("ANALYZE")


if __name__ == "__main__":
    load_dotenv()
    load(os.environ["DATABASE_URL"])
