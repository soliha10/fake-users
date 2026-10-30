import os

from dotenv import load_dotenv


def database_url() -> str:
    load_dotenv()
    return os.environ["DATABASE_URL"]
