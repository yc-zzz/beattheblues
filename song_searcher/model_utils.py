import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine

#import credentials 
def import_credentials(): 
    load_dotenv()
    try: 
        db_user = os.environ["DB_USER"]
        db_password = os.environ["DB_PASSWORD"]
        db_host = os.environ["DB_HOST"]
        db_name = os.environ["DB_NAME"]
    except Exception as e: 
        raise RuntimeError("Missing environment variable: ", e)

    db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}/{db_name}?sslmode=require"
    engine = create_engine(db_url)
    return engine
