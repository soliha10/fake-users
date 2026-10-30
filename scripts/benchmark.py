import argparse
import datetime
import json
import pathlib
import statistics

import psycopg

from database import database_url

RESULTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "benchmarks"
BENCHMARK_SEED = 2024
RUNS_PER_CASE = 3
CASES = [(1000, False), (10000, False), (100000, False), (1000, True), (10000, True)]


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--host", required=True)
    return parser.parse_args()


def measure_speed(connection, locale, user_count, with_bio):
    return connection.execute(
        "SELECT users_per_second FROM fake_benchmark(%s, %s, %s, %s)",
        (locale, BENCHMARK_SEED, user_count, with_bio),
    ).fetchone()[0]


def measure_case(connection, locale, user_count, with_bio):
    speeds = [measure_speed(connection, locale, user_count, with_bio) for _ in range(RUNS_PER_CASE)]
    median_speed = statistics.median(speeds)
    print(locale, user_count, with_bio, round(median_speed), flush=True)
    return {"locale": locale, "users": user_count, "with_bio": with_bio,
            "runs_users_per_second": speeds, "median": median_speed}


def print_markdown_table(results):
    print("\n| Locale | Users | Bio | Median users/sec |\n|---|---:|---|---:|")
    for result in results:
        bio_label = "yes" if result["with_bio"] else "no"
        print(f"| {result['locale']} | {result['users']:,} | {bio_label} | {result['median']:,.0f} |")


def main():
    arguments = parse_arguments()
    with psycopg.connect(database_url(), autocommit=True) as connection:
        postgres_version = connection.execute("SHOW server_version").fetchone()[0]
        locales = [code for (code,) in connection.execute("SELECT code FROM fake_locales()")]
        results = [measure_case(connection, locale, user_count, with_bio)
                   for locale in locales for user_count, with_bio in CASES]

    report = {"label": arguments.label, "host": arguments.host, "postgres": postgres_version,
              "date": datetime.date.today().isoformat(), "seed": BENCHMARK_SEED, "results": results}
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / f"{arguments.label}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_markdown_table(results)


if __name__ == "__main__":
    main()
