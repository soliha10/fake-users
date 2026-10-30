import psycopg
import pytest
from psycopg.rows import dict_row

from scripts.database import database_url


@pytest.fixture(scope="session")
def dsn():
    return database_url()


@pytest.fixture()
def db(dsn):
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
        yield connection
