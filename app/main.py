"""Flask front end. All fake data comes from the fake_* stored routines."""
import os

import psycopg
from dotenv import load_dotenv
from flask import Flask, render_template, request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

BATCH_SIZE = 10
DEFAULT_LOCALE = "en_US"
DEFAULT_SEED = 42
INT64_MAX = 2**63 - 1
MAX_BATCH = INT64_MAX // BATCH_SIZE - 1

load_dotenv()
app = Flask(__name__)
pool = ConnectionPool(
    os.environ.get("DATABASE_URL", ""),
    min_size=int(os.environ.get("DB_POOL_MIN", 1)),
    max_size=int(os.environ.get("DB_POOL_MAX", 5)),
    timeout=15,
    check=ConnectionPool.check_connection,
    # Neon's pooled endpoint runs PgBouncer, which cannot track server-side prepared statements.
    kwargs={"row_factory": dict_row, "prepare_threshold": None},
    open=False,
)


class InvalidInput(ValueError):
    pass


def ensure_pool():
    if pool.closed:
        pool.open()


def parse_int(name, default, low, high):
    raw = request.args.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise InvalidInput(f"{name.capitalize()} must be a whole number.") from None
    if not low <= value <= high:
        raise InvalidInput(f"{name.capitalize()} must be between {low} and {high}.")
    return value


@app.get("/")
def index():
    ensure_pool()
    seed = parse_int("seed", DEFAULT_SEED, -INT64_MAX - 1, INT64_MAX)
    batch = parse_int("batch", 0, 0, MAX_BATCH)
    locale = request.args.get("locale", DEFAULT_LOCALE)
    with pool.connection() as conn:
        locales = conn.execute("SELECT * FROM fake_locales()").fetchall()
        users = conn.execute(
            "SELECT * FROM fake_users(%s, %s, %s, %s)", (locale, seed, batch, BATCH_SIZE)
        ).fetchall()
    return render_template("index.html", users=users, locales=locales, locale=locale,
                           seed=seed, batch=batch, batch_size=BATCH_SIZE, max_batch=MAX_BATCH)


@app.get("/health")
def health():
    ensure_pool()
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.errorhandler(InvalidInput)
@app.errorhandler(psycopg.errors.InvalidParameterValue)
def invalid_input(error):
    message = getattr(getattr(error, "diag", None), "message_primary", None) or str(error)
    return render_template("error.html", title="Invalid input", message=message), 400


@app.errorhandler(psycopg.OperationalError)
@app.errorhandler(PoolTimeout)
def database_unavailable(_error):
    message = "The database is not reachable right now. Please try again in a moment."
    return render_template("error.html", title="Database unavailable", message=message), 503
