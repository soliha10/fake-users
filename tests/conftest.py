import os

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()
DSN = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def dsn():
    return DSN


@pytest.fixture()
def db():
    with psycopg.connect(DSN, autocommit=True, row_factory=dict_row) as conn:
        yield conn
