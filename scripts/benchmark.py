"""Run fake_benchmark() three times per case and save the raw results.

Usage: python scripts/benchmark.py --label local --host "Apple Silicon, Docker"
Writes benchmarks/<label>.json and prints a Markdown table.
"""
import argparse
import datetime
import json
import os
import pathlib
import statistics

import psycopg
from dotenv import load_dotenv

OUT = pathlib.Path(__file__).resolve().parent.parent / "benchmarks"
SEED = 2024
RUNS = 3
CASES = [(1000, False), (10000, False), (100000, False), (1000, True), (10000, True)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--host", required=True)
    args = parser.parse_args()
    load_dotenv()

    results = []
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
        locales = [row[0] for row in conn.execute("SELECT code FROM fake_locales()")]
        for locale in locales:
            for n, with_bio in CASES:
                speeds = [conn.execute("SELECT users_per_second FROM fake_benchmark(%s, %s, %s, %s)",
                                       (locale, SEED, n, with_bio)).fetchone()[0] for _ in range(RUNS)]
                results.append({"locale": locale, "users": n, "with_bio": with_bio,
                                "runs_users_per_second": speeds, "median": statistics.median(speeds)})
                print(locale, n, with_bio, round(statistics.median(speeds)), flush=True)

    report = {"label": args.label, "host": args.host, "postgres": version,
              "date": datetime.date.today().isoformat(), "seed": SEED, "results": results}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{args.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n| Locale | Users | Bio | Median users/sec |\n|---|---:|---|---:|")
    for r in results:
        print(f"| {r['locale']} | {r['users']:,} | {'yes' if r['with_bio'] else 'no'} | {r['median']:,.0f} |")


if __name__ == "__main__":
    main()
