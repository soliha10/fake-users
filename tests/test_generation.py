import concurrent.futures
import pathlib
import re

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
LOCALES = ["en_US", "de_DE"]
CHI_SQUARED_99_DF_ALPHA_001 = 148.23
UNIFORM_SAMPLE_SIZE = 100000
BUCKET_COUNT = 100
EXPECTED_BUCKET_SIZE = UNIFORM_SAMPLE_SIZE / BUCKET_COUNT
PHYSICAL_SAMPLE_SIZE = 20000
EYE_COLOR_SAMPLE_SIZE = 20000
PHYSICAL_TOLERANCE_IN_STDDEVS = 0.05
EYE_COLOR_TOLERANCE = 0.012
RESERVED_DOMAINS = {"example.com", "example.org", "example.net"}
GERMAN_EYE_COLORS = {"braun", "blau", "grün", "grau", "haselnussbraun", "bernsteinfarben"}
GERMAN_FICTIONAL_PHONE_BLOCK = r"(23125|66969|90009|3920)"


def fetch_batch(connection, locale="en_US", seed=1, batch_index=0, batch_size=10):
    return connection.execute(
        "SELECT * FROM fake_users(%s, %s, %s, %s)", (locale, seed, batch_index, batch_size)
    ).fetchall()


def fetch_one_value(connection, query, parameters=None):
    return next(iter(connection.execute(query, parameters).fetchone().values()))


def identity_of(user):
    return user["full_name"] + user["phone"]


def chi_squared_of_flatness(connection, expression, low, high):
    buckets = connection.execute(f"""
        SELECT width_bucket({expression}, {low}, {high}, {BUCKET_COUNT}) AS bucket, count(*) AS points
        FROM (SELECT fake_lat(fake_uniform('en_US', 7, i, 'latitude'))::float8 AS lat,
                     fake_lng(fake_uniform('en_US', 7, i, 'longitude'))::float8 AS lng
              FROM generate_series(1, {UNIFORM_SAMPLE_SIZE}) i) coordinates
        GROUP BY bucket""").fetchall()
    points_by_bucket = {row["bucket"]: row["points"] for row in buckets}
    return sum((points_by_bucket.get(bucket, 0) - EXPECTED_BUCKET_SIZE) ** 2 / EXPECTED_BUCKET_SIZE
               for bucket in range(1, BUCKET_COUNT + 1))


@pytest.mark.parametrize("locale", LOCALES)
def test_same_arguments_across_connections(dsn, locale):
    def read_batch():
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            return fetch_batch(connection, locale, 77, 3)

    assert read_batch() == read_batch()


@pytest.mark.parametrize("arguments", [("de_DE", 1, 0), ("en_US", 2, 0), ("en_US", 1, 1)])
def test_each_argument_changes_output(db, arguments):
    base_identities = {identity_of(user) for user in fetch_batch(db)}
    other_identities = {identity_of(user) for user in fetch_batch(db, *arguments)}
    assert base_identities != other_identities


def test_index_within_batch_changes_output(db):
    assert len({user["email"] + user["address"] for user in fetch_batch(db)}) == 10


def test_position_is_independent_of_batch_size(db):
    assert fetch_batch(db, batch_index=3, batch_size=10) == fetch_batch(db, batch_index=0, batch_size=100)[30:40]


def test_query_order_does_not_change_results(db):
    expected = fetch_batch(db, seed=5, batch_index=2)
    for other_batch in (9, 0, 4):
        fetch_batch(db, seed=5, batch_index=other_batch)
    assert fetch_batch(db, seed=5, batch_index=2) == expected


def test_concurrent_queries_do_not_change_results(dsn):
    def read_seed(seed):
        with psycopg.connect(dsn, row_factory=dict_row) as connection:
            return seed, fetch_batch(connection, seed=seed, batch_size=50)

    with concurrent.futures.ThreadPoolExecutor(8) as executor:
        concurrent_results = dict(executor.map(read_seed, [1, 2, 3, 4] * 2))
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        for seed, users in concurrent_results.items():
            assert users == fetch_batch(connection, seed=seed, batch_size=50)


def test_uniform_is_in_range_and_flat(db):
    summary = db.execute(f"""
        SELECT min(draw) AS low, max(draw) AS high, avg(draw) AS mean
        FROM (SELECT fake_uniform('en_US', 1, i, 'x') AS draw
              FROM generate_series(1, {UNIFORM_SAMPLE_SIZE}) i) draws""").fetchone()
    assert 0 <= summary["low"] and summary["high"] < 1
    assert abs(summary["mean"] - 0.5) < 0.01


@pytest.mark.parametrize("expression, low, high", [
    ("sin(radians(lat))", -1, 1.0000001),
    ("lng", -180, 180.0000001),
])
def test_coordinates_are_uniform_on_the_sphere(db, expression, low, high):
    assert chi_squared_of_flatness(db, expression, low, high) < CHI_SQUARED_99_DF_ALPHA_001


def test_raw_latitude_is_not_uniform(db):
    assert chi_squared_of_flatness(db, "lat", -90, 90.0000001) > CHI_SQUARED_99_DF_ALPHA_001


@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("attribute", ["height_cm", "weight_kg"])
@pytest.mark.parametrize("gender", ["M", "F"])
def test_physical_mean_and_stddev(db, locale, attribute, gender):
    measured = db.execute(f"""
        SELECT configured.mean, configured.stddev, sample.sample_mean, sample.sample_stddev
        FROM physical_distributions configured,
        LATERAL (SELECT avg(draw)::float8 AS sample_mean, stddev(draw)::float8 AS sample_stddev FROM
                 (SELECT fake_physical(configured.locale, 3, i, configured.gender, configured.attribute) AS draw
                  FROM generate_series(1, {PHYSICAL_SAMPLE_SIZE}) i) draws) sample
        WHERE configured.locale = %s AND configured.attribute = %s AND configured.gender = %s""",
                          (locale, attribute, gender)).fetchone()
    tolerance = PHYSICAL_TOLERANCE_IN_STDDEVS * measured["stddev"]
    assert abs(measured["sample_mean"] - measured["mean"]) < tolerance
    assert abs(measured["sample_stddev"] - measured["stddev"]) < tolerance


@pytest.mark.parametrize("locale", LOCALES)
def test_eye_color_frequency(db, locale):
    frequencies = db.execute(f"""
        SELECT color.value, color.weight / sum(color.weight) OVER () AS expected,
               coalesce(drawn.times, 0) / {EYE_COLOR_SAMPLE_SIZE}.0 AS seen
        FROM eye_colors color LEFT JOIN
             (SELECT fake_eye_color(%(locale)s, 9, i) AS value, count(*) AS times
              FROM generate_series(1, {EYE_COLOR_SAMPLE_SIZE}) i GROUP BY 1) drawn
             ON drawn.value = color.value
        WHERE color.locale = %(locale)s""", {"locale": locale}).fetchall()
    for frequency in frequencies:
        assert abs(float(frequency["expected"]) - float(frequency["seen"])) < EYE_COLOR_TOLERANCE, frequency["value"]


@pytest.mark.parametrize("locale", LOCALES)
def test_lookup_volume_and_combinations(db, locale):
    def count_rows(query):
        return fetch_one_value(db, query, (locale,))

    first_names = count_rows("SELECT count(*) FROM names WHERE locale = %s AND kind = 'first' AND gender = 'F'")
    last_names = count_rows("SELECT count(*) FROM names WHERE locale = %s AND kind = 'last'")
    middle_names = count_rows("SELECT count(*) FROM names WHERE locale = %s AND kind = 'middle' AND gender = 'F'")
    cities = count_rows("SELECT count(DISTINCT city) FROM places WHERE locale = %s")
    streets = count_rows("SELECT count(*) FROM address_parts WHERE locale = %s AND kind = 'street'")
    assert first_names >= 1000 and last_names >= 1000 and middle_names >= 200
    assert cities >= 500 and streets >= 1000
    assert first_names * last_names * cities * streets > 1_000_000


@pytest.mark.parametrize("locale", LOCALES)
def test_duplicates_are_rare_in_a_sample(db, locale):
    uniqueness = db.execute("""
        SELECT count(*) AS total, count(DISTINCT (full_name, address)) AS people, count(DISTINCT email) AS emails
        FROM generate_series(0, 49999) i, fake_user(%s, 11, i, false)""", (locale,)).fetchone()
    assert uniqueness["people"] == uniqueness["total"]
    assert uniqueness["emails"] / uniqueness["total"] > 0.75


def test_weights_end_at_one(db):
    groups = db.execute("SELECT max(cum_weight) AS last_weight FROM names GROUP BY locale, kind, gender").fetchall()
    assert all(group["last_weight"] == 1 for group in groups)


def test_english_format(db):
    users = fetch_batch(db, "en_US", 2, 0, 200)
    assert all(re.search(r"555[-.]01\d\d$", user["phone"]) for user in users)
    assert any(", Apt " in user["address"] for user in users)
    assert all(re.search(r"\b[A-Z]{2}\b", user["address"]) for user in users)
    assert any(user["full_name"].startswith(("Mr.", "Ms.", "Mrs.", "Dr.")) for user in users)


def test_german_format(db):
    users = fetch_batch(db, "de_DE", 2, 0, 200)
    assert all(re.search(r"\b\d{5}\b", user["address"]) for user in users)
    assert any(re.search(r"(straße|weg|gasse|allee)\b", user["address"]) for user in users)
    assert any(user["full_name"].startswith(("Herr", "Frau")) for user in users)
    assert all(re.fullmatch(r"[+()\d -]+", user["phone"]) for user in users)
    assert all(re.search(GERMAN_FICTIONAL_PHONE_BLOCK, user["phone"]) for user in users)
    assert {user["eye_color"] for user in users} <= GERMAN_EYE_COLORS


@pytest.mark.parametrize("locale", LOCALES)
def test_email_is_ascii_on_a_reserved_domain(db, locale):
    for user in fetch_batch(db, locale, 4, 0, 200):
        local_part, domain = user["email"].split("@")
        assert re.fullmatch(r"[a-z0-9._-]+", local_part)
        assert domain.endswith(".example") or domain in RESERVED_DOMAINS


def test_transliteration(db):
    assert fetch_one_value(db, "SELECT fake_transliterate('Jürgen Weiß Öztürk José')") == "JuergenWeissOeztuerkJose"


@pytest.mark.parametrize("locale", LOCALES)
def test_markov_bio(db, locale):
    bios = [user["bio"] for user in fetch_batch(db, locale, 6, 0, 30)]
    assert all(bio[-1] in ".!?" and len(bio.split()) >= 6 for bio in bios)
    assert len(set(bios)) == 30
    assert not any("lorem" in bio.lower() for bio in bios)


@pytest.mark.parametrize("query, parameters", [
    ("SELECT * FROM fake_users(%s, 1, 0)", ("xx_XX",)),
    ("SELECT * FROM fake_users('en_US', 1, %s)", (-1,)),
    ("SELECT * FROM fake_users('en_US', 1, 0, %s)", (0,)),
    ("SELECT * FROM fake_users('en_US', 1, 0, %s)", (1001,)),
    ("SELECT * FROM fake_users('en_US', 1, %s)", (2**62,)),
])
def test_invalid_arguments(db, query, parameters):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        db.execute(query, parameters)


def test_extreme_seed_and_position(db):
    assert len(fetch_batch(db, seed=-(2**63), batch_index=(2**63 - 11) // 10, batch_size=10)) == 10


def copy_lookup_rows_to_new_locale(connection):
    connection.execute("INSERT INTO locales VALUES ('xx_XX', 'Test', 'Test', 10)")
    for table, columns in [
        ("names", "kind, gender, idx, value, weight"), ("titles", "kind, gender, idx, value, weight"),
        ("address_parts", "kind, idx, value, weight"), ("places", "idx, city, region, postal_code, weight"),
        ("format_templates", "kind, idx, template, weight"), ("email_domains", "idx, value, weight"),
        ("eye_colors", "idx, value, weight"),
        ("physical_distributions", "attribute, gender, mean, stddev, min_value, max_value"),
        ("markov_transitions", "prefix, idx, next_word, weight"),
    ]:
        connection.execute(
            f"INSERT INTO {table} (locale, {columns}) SELECT 'xx_XX', {columns} FROM {table} WHERE locale = 'en_US'")


def test_new_locale_needs_only_rows(dsn):
    connection = psycopg.connect(dsn)
    try:
        copy_lookup_rows_to_new_locale(connection)
        connection.execute("CALL fake_rebuild_weights('xx_XX')")
        assert len(fetch_batch(connection, "xx_XX")) == 10
    finally:
        connection.rollback()
        connection.close()


def fake_routines_matching(connection, pattern):
    routines = connection.execute("""
        SELECT DISTINCT proname FROM pg_proc routine JOIN pg_namespace namespace ON namespace.oid = routine.pronamespace
        WHERE namespace.nspname = 'public' AND proname LIKE 'fake\\_%%' AND prosrc ~* %s""", (pattern,)).fetchall()
    return [routine["proname"] for routine in routines]


def test_generation_has_no_session_state(db):
    assert fake_routines_matching(db, r"\m(random|setseed|nextval|now|current_timestamp|gen_random_uuid)\s*\(") == []


def test_only_benchmark_reads_the_clock(db):
    assert fake_routines_matching(db, "clock_timestamp") == ["fake_benchmark"]


def test_only_benchmark_is_volatile(db):
    routines = db.execute("""
        SELECT proname FROM pg_proc routine JOIN pg_namespace namespace ON namespace.oid = routine.pronamespace
        WHERE namespace.nspname = 'public' AND proname LIKE 'fake\\_%' AND provolatile = 'v' AND prokind = 'f'
        """).fetchall()
    assert [routine["proname"] for routine in routines] == ["fake_benchmark"]


def test_app_has_no_generation_logic():
    banned_names = re.compile(r"\b(random|faker|secrets|uuid|numpy|hashlib)\b", re.I)
    for python_file in (ROOT_DIR / "app").glob("*.py"):
        assert not banned_names.search(python_file.read_text(encoding="utf-8")), python_file.name
