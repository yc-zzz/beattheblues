from model_utils import import_credentials
from sqlalchemy import text 
import psycopg2

class PersonalityTable: 
    def __init__(self): 
        self.engine = import_credentials()

    def create_table(self): 
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS user_personality(
        id SERIAL PRIMARY KEY,
        request_date DATE NOT NULL, 
        description TEXT  
        );
        """

        with self.engine.connect() as connection: 
            try: 
                connection.execute(text(create_table_sql))
                connection.commit()
                return "Table already created or already exists."
            except Exception as e: 
                return f"Error: {e}"

    def refresh(self): 
        delete_rows = """
        DELETE FROM user_personality
        WHERE request_date <> CURRENT_DATE;
        """
        with self.engine.connect() as connection: 
            try: 
                connection.execute(text(delete_rows))
                connection.commit()
                return "Previous day entries deleted."
            except Exception as e: 
                return f"Error: {e}"
            
    def update_table(self, user_entry): #user_entry should be a... DataFrame with the relevant entry? 
        try: 
            user_entry.to_sql("user_personality", con=self.engine, if_exists = 'append', index=False)
            return "Data inserted successfully."
        except Exception as e: 
            return f"Error: {e}"




        





