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


NAME_PREFIXES = {"herr", "frau", "miss"}


@app.template_filter("initials")
def initials(full_name):
    """First and last name letters for the avatar, ignoring titles and suffixes."""
    words = [w.strip(",") for w in full_name.split() if not w.endswith(".")]
    words = [w for w in words if w.lower() not in NAME_PREFIXES and w not in {"III", "PhD", "MD", "MBA"}]
    return (words[0][0] + words[-1][0]).upper() if len(words) > 1 else words[0][0].upper()


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
    first_user = batch * BATCH_SIZE + 1
    return render_template("index.html", users=users, locales=locales, locale=locale,
                           lang=locale.split("_")[0], seed=seed, batch=batch, batch_size=BATCH_SIZE,
                           max_batch=MAX_BATCH, first_user=first_user, last_user=first_user + len(users) - 1)


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
