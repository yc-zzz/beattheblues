import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine

#import credentials 
def import_credentials(): 
    """Create a database engine for the Neon Postgres database.

    Uses DB_USER, DB_PASSWORD, DB_HOST and DB_NAME when all four are set (the
    original Render setup). Otherwise falls back to NEON_CONNECTION_STRING,
    the single variable the recommender already uses, so a new deployment only
    needs to configure one database secret.
    """
    load_dotenv()
    parts = ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME")
    if all(os.environ.get(name) for name in parts):
        db_user, db_password, db_host, db_name = (os.environ[name] for name in parts)
        db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}/{db_name}?sslmode=require"
    elif os.environ.get("NEON_CONNECTION_STRING"):
        db_url = os.environ["NEON_CONNECTION_STRING"]
    else:
        raise RuntimeError(
            "Missing database settings: set NEON_CONNECTION_STRING, "
            "or all of DB_USER, DB_PASSWORD, DB_HOST and DB_NAME."
        )

    engine = create_engine(db_url)
    return engine
