import concurrent.futures
import pathlib
import re

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCALES = ["en_US", "de_DE"]
# Chi-squared critical value for 99 degrees of freedom at alpha = 0.001.
CHI2_99_CRITICAL = 148.23


def batch(conn, locale="en_US", seed=1, index=0, size=10):
    return conn.execute("SELECT * FROM fake_users(%s, %s, %s, %s)", (locale, seed, index, size)).fetchall()


@pytest.mark.parametrize("locale", LOCALES)
def test_same_arguments_across_connections(dsn, locale):
    results = []
    for _ in range(2):
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            results.append(batch(conn, locale, 77, 3))
    assert results[0] == results[1]


@pytest.mark.parametrize("args", [("de_DE", 1, 0), ("en_US", 2, 0), ("en_US", 1, 1)])
def test_each_argument_changes_output(db, args):
    base = {u["full_name"] + u["phone"] for u in batch(db)}
    other = {u["full_name"] + u["phone"] for u in batch(db, *args)}
    assert base != other


def test_index_within_batch_changes_output(db):
    assert len({u["email"] + u["address"] for u in batch(db)}) == 10


def test_position_is_independent_of_batch_size(db):
    small = batch(db, index=3, size=10)
    large = batch(db, index=0, size=100)
    assert small == large[30:40]


def test_query_order_does_not_change_results(db):
    expected = batch(db, seed=5, index=2)
    for other in (9, 0, 4):
        batch(db, seed=5, index=other)
    assert batch(db, seed=5, index=2) == expected


def test_concurrent_queries_do_not_change_results(dsn):
    def run(seed):
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            return seed, batch(conn, seed=seed, size=50)

    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        first = dict(ex.map(run, [1, 2, 3, 4] * 2))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        for seed, rows in first.items():
            assert rows == batch(conn, seed=seed, size=50)


def test_uniform_is_in_range_and_flat(db):
    row = db.execute("""
        SELECT min(u) lo, max(u) hi, avg(u) mean
        FROM (SELECT fake_uniform('en_US', 1, i, 'x') u FROM generate_series(1, 100000) i) s""").fetchone()
    assert 0 <= row["lo"] and row["hi"] < 1
    assert abs(row["mean"] - 0.5) < 0.01


def chi_squared(db, expression, low, high):
    rows = db.execute(f"""
        SELECT width_bucket({expression}, {low}, {high}, 100) AS b, count(*) AS n
        FROM (SELECT fake_lat(fake_uniform('en_US', 7, i, 'latitude'))::float8 AS lat,
                     fake_lng(fake_uniform('en_US', 7, i, 'longitude'))::float8 AS lng
              FROM generate_series(1, 100000) i) s
        GROUP BY b""").fetchall()
    counts = {r["b"]: r["n"] for r in rows}
    return sum((counts.get(b, 0) - 1000) ** 2 / 1000 for b in range(1, 101))


def test_sine_of_latitude_is_uniform(db):
    assert chi_squared(db, "sin(radians(lat))", -1, 1.0000001) < CHI2_99_CRITICAL


def test_longitude_is_uniform(db):
    assert chi_squared(db, "lng", -180, 180.0000001) < CHI2_99_CRITICAL


def test_raw_latitude_is_not_uniform(db):
    assert chi_squared(db, "lat", -90, 90.0000001) > CHI2_99_CRITICAL


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("attribute", ["height_cm", "weight_kg"])
@pytest.mark.parametrize("gender", ["M", "F"])
def test_physical_mean_and_stddev(db, locale, attribute, gender):
    row = db.execute("""
        SELECT d.mean, d.stddev, s.m, s.sd, s.lo, s.hi FROM physical_distributions d,
        LATERAL (SELECT avg(v)::float8 m, stddev(v)::float8 sd, min(v)::float8 lo, max(v)::float8 hi FROM
                 (SELECT fake_physical(d.locale, 3, i, d.gender, d.attribute) v
                  FROM generate_series(1, 20000) i) x) s
        WHERE d.locale = %s AND d.attribute = %s AND d.gender = %s""", (locale, attribute, gender)).fetchone()
    assert abs(row["m"] - row["mean"]) < 0.05 * row["stddev"]
    assert abs(row["sd"] - row["stddev"]) < 0.05 * row["stddev"]


@pytest.mark.parametrize("locale", LOCALES)
def test_eye_color_frequency(db, locale):
    rows = db.execute("""
        SELECT e.value, e.weight / sum(e.weight) OVER () AS expected, coalesce(c.n, 0) / 20000.0 AS seen
        FROM eye_colors e LEFT JOIN
             (SELECT fake_eye_color(%(l)s, 9, i) v, count(*) n FROM generate_series(1, 20000) i GROUP BY 1) c
             ON c.v = e.value
        WHERE e.locale = %(l)s""", {"l": locale}).fetchall()
    for row in rows:
        assert abs(float(row["expected"]) - float(row["seen"])) < 0.012, row["value"]


@pytest.mark.parametrize("locale", LOCALES)
def test_lookup_volume_and_combinations(db, locale):
    def count(sql):
        return db.execute(sql, (locale,)).fetchone()["n"]

    firsts = count("SELECT count(*) n FROM names WHERE locale = %s AND kind = 'first' AND gender = 'F'")
    lasts = count("SELECT count(*) n FROM names WHERE locale = %s AND kind = 'last'")
    middles = count("SELECT count(*) n FROM names WHERE locale = %s AND kind = 'middle' AND gender = 'F'")
    cities = count("SELECT count(DISTINCT city) n FROM places WHERE locale = %s")
    streets = count("SELECT count(*) n FROM address_parts WHERE locale = %s AND kind = 'street'")
    assert firsts >= 1000 and lasts >= 1000 and middles >= 200 and cities >= 500 and streets >= 1000
    assert firsts * lasts * cities * streets > 1_000_000


@pytest.mark.parametrize("locale", LOCALES)
def test_duplicates_are_rare_in_a_sample(db, locale):
    row = db.execute("""
        SELECT count(*) n, count(DISTINCT (full_name, address)) d,
               count(DISTINCT email) e
        FROM generate_series(0, 49999) i, fake_user(%s, 11, i, false)""", (locale,)).fetchone()
    assert row["d"] == row["n"]
    assert row["e"] / row["n"] > 0.75


def test_weights_end_at_one(db):
    rows = db.execute("""SELECT locale, kind, gender, max(cum_weight) m FROM names GROUP BY 1, 2, 3""").fetchall()
    assert all(r["m"] == 1 for r in rows)


def test_english_format(db):
    users = batch(db, "en_US", 2, 0, 200)
    assert all(re.search(r"555[-.]01\d\d$", u["phone"]) for u in users)
    assert any(", Apt " in u["address"] for u in users)
    assert all(re.search(r"\b[A-Z]{2}\b", u["address"]) for u in users)
    assert any(u["full_name"].startswith(("Mr.", "Ms.", "Mrs.", "Dr.")) for u in users)


def test_german_format(db):
    users = batch(db, "de_DE", 2, 0, 200)
    assert all(re.search(r"\b\d{5}\b", u["address"]) for u in users)
    assert any(re.search(r"(straße|weg|gasse|allee)\b", u["address"]) for u in users)
    assert any(u["full_name"].startswith(("Herr", "Frau")) for u in users)
    assert all(re.fullmatch(r"[+()\d -]+", u["phone"]) for u in users)
    assert all(re.search(r"(23125|66969|90009|3920)", u["phone"]) for u in users)
    assert {u["eye_color"] for u in users} <= {"braun", "blau", "grün", "grau", "haselnussbraun", "bernsteinfarben"}


@pytest.mark.parametrize("locale", LOCALES)
def test_email_is_ascii_on_a_reserved_domain(db, locale):
    for user in batch(db, locale, 4, 0, 200):
        local, domain = user["email"].split("@")
        assert re.fullmatch(r"[a-z0-9._-]+", local)
        assert domain.endswith(".example") or domain in {"example.com", "example.org", "example.net"}


def test_transliteration(db):
    assert db.execute("SELECT fake_transliterate('Jürgen Weiß Öztürk José') t").fetchone()["t"] == \
        "JuergenWeissOeztuerkJose"


@pytest.mark.parametrize("locale", LOCALES)
def test_markov_bio(db, locale):
    bios = [u["bio"] for u in batch(db, locale, 6, 0, 30)]
    assert all(bio[-1] in ".!?" and len(bio.split()) >= 6 for bio in bios)
    assert len(set(bios)) == 30
    assert not any("lorem" in bio.lower() for bio in bios)


@pytest.mark.parametrize("sql, args", [
    ("SELECT * FROM fake_users(%s, 1, 0)", ("xx_XX",)),
    ("SELECT * FROM fake_users('en_US', 1, %s)", (-1,)),
    ("SELECT * FROM fake_users('en_US', 1, 0, %s)", (0,)),
    ("SELECT * FROM fake_users('en_US', 1, 0, %s)", (1001,)),
    ("SELECT * FROM fake_users('en_US', 1, %s)", (2**62,)),
])
def test_invalid_arguments(db, sql, args):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        db.execute(sql, args)


def test_extreme_seed_and_position(db):
    assert len(batch(db, seed=-(2**63), index=(2**63 - 11) // 10, size=10)) == 10


def test_new_locale_needs_only_rows(dsn):
    conn = psycopg.connect(dsn)
    try:
        for table, columns in [
            ("names", "kind, gender, idx, value, weight"), ("titles", "kind, gender, idx, value, weight"),
            ("address_parts", "kind, idx, value, weight"), ("places", "idx, city, region, postal_code, weight"),
            ("format_templates", "kind, idx, template, weight"), ("email_domains", "idx, value, weight"),
            ("eye_colors", "idx, value, weight"),
            ("physical_distributions", "attribute, gender, mean, stddev, min_value, max_value"),
            ("markov_transitions", "prefix, idx, next_word, weight"),
        ]:
            if table == "names":
                conn.execute("INSERT INTO locales VALUES ('xx_XX', 'Test', 'Test', 10)")
            conn.execute(f"INSERT INTO {table} (locale, {columns}) SELECT 'xx_XX', {columns} FROM {table} WHERE locale = 'en_US'")
        conn.execute("CALL fake_rebuild_weights('xx_XX')")
        users = conn.execute("SELECT * FROM fake_users('xx_XX', 1, 0)").fetchall()
        assert len(users) == 10
    finally:
        conn.rollback()
        conn.close()


def test_generation_has_no_session_state():
    banned = re.compile(r"\b(random|setseed|nextval|now|current_timestamp|gen_random_uuid)\s*\(", re.I)
    for path in (ROOT / "db" / "migrations").glob("*.sql"):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name
        text = path.read_text(encoding="utf-8").replace("clock_timestamp()", "", 2) if path.name == "007_api.sql" \
            else path.read_text(encoding="utf-8")
        assert "clock_timestamp" not in text, path.name


def test_only_benchmark_is_volatile(db):
    rows = db.execute("""
        SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND proname LIKE 'fake\\_%' AND provolatile = 'v' AND prokind = 'f'""").fetchall()
    assert [r["proname"] for r in rows] == ["fake_benchmark"]


def test_app_has_no_generation_logic():
    banned = re.compile(r"\b(random|faker|secrets|uuid|numpy|hashlib)\b", re.I)
    for path in (ROOT / "app").glob("*.py"):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name
