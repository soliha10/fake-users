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

POOL_TIMEOUT_SECONDS = 15
HONORIFICS = {"herr", "frau", "miss"}
NAME_SUFFIXES = {"III", "PhD", "MD", "MBA"}

load_dotenv()
app = Flask(__name__)
pool = ConnectionPool(
    os.environ.get("DATABASE_URL", ""),
    min_size=int(os.environ.get("DB_POOL_MIN", 1)),
    max_size=int(os.environ.get("DB_POOL_MAX", 5)),
    timeout=POOL_TIMEOUT_SECONDS,
    check=ConnectionPool.check_connection,
    kwargs={"row_factory": dict_row, "prepare_threshold": None},
    open=False,
)


class InvalidInput(ValueError):
    pass


def is_given_or_family_name(word):
    return not word.endswith(".") and word.lower() not in HONORIFICS and word not in NAME_SUFFIXES


@app.template_filter("initials")
def initials(full_name):
    name_words = [word.strip(",") for word in full_name.split() if is_given_or_family_name(word.strip(","))]
    letters = name_words[0][0] if len(name_words) == 1 else name_words[0][0] + name_words[-1][0]
    return letters.upper()


def database_connection():
    if pool.closed:
        pool.open()
    return pool.connection()


def parse_int_argument(name, default, minimum, maximum):
    raw_value = request.args.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        raise InvalidInput(f"{name.capitalize()} must be a whole number.") from None
    if not minimum <= value <= maximum:
        raise InvalidInput(f"{name.capitalize()} must be between {minimum} and {maximum}.")
    return value


@app.get("/")
def index():
    seed = parse_int_argument("seed", DEFAULT_SEED, -INT64_MAX - 1, INT64_MAX)
    batch = parse_int_argument("batch", 0, 0, MAX_BATCH)
    locale = request.args.get("locale", DEFAULT_LOCALE)
    with database_connection() as connection:
        locales = connection.execute("SELECT * FROM fake_locales()").fetchall()
        users = connection.execute(
            "SELECT * FROM fake_users(%s, %s, %s, %s)", (locale, seed, batch, BATCH_SIZE)
        ).fetchall()
    first_user = batch * BATCH_SIZE + 1
    return render_template("index.html", users=users, locales=locales, locale=locale,
                           lang=locale.split("_")[0], seed=seed, batch=batch, batch_size=BATCH_SIZE,
                           max_batch=MAX_BATCH, first_user=first_user, last_user=first_user + len(users) - 1)


@app.get("/health")
def health():
    with database_connection() as connection:
        connection.execute("SELECT 1")
    return {"status": "ok"}


def render_error(title, message, status_code):
    return render_template("error.html", title=title, message=message), status_code


@app.errorhandler(InvalidInput)
def invalid_input(error):
    return render_error("Invalid input", str(error), 400)


@app.errorhandler(psycopg.errors.InvalidParameterValue)
def rejected_by_database(error):
    return render_error("Invalid input", error.diag.message_primary, 400)


@app.errorhandler(psycopg.OperationalError)
@app.errorhandler(PoolTimeout)
def database_unavailable(_error):
    return render_error("Database unavailable",
                        "The database is not reachable right now. Please try again in a moment.", 503)
