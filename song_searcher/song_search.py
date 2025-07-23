#libraries
from model_utils import import_credentials
import pandas as pd

searcher = None 

def get_search(): 
    print("get_search was called")
    global searcher
    if searcher is None: 
        print("Instantiating Search...")
        searcher = Search()
    return searcher

#song search object
class Search: 
    def __init__(self): 
        self.file_path = None
        self.sql_query = None
        self.user_query = None 
        self.data = None
        self.current_result = None
        self.engine = import_credentials()
        self.parameters = None

    def load_sql(self): 
        from pathlib import Path
        self.file_path = Path(__file__).parent / "song_search.sql"
        with open(self.file_path, "r") as file: 
            self.sql_query = file.read()
        try: 
            return self.sql_query
        except Exception as e: 
            print(f"Did you get your file path right? Anyways, here's your error: {e}")

    def load_data(self, query): 
        self.sql_query = self.load_sql()
        self.user_query = query
        self.parameters = {"q": self.user_query}
        self.data = pd.read_sql(self.sql_query, con=self.engine, params = self.parameters)
        if not self.data.empty: 
            for ind, row in self.data.iterrows(): 
                yield f"Here's our closest song: {row['name']} by {row['artist']}. Click again if this isn't it!"
        else: 
            self.current_result = None
            return self.current_result
    
    def return_song(self, query): 
        if query is None: 
            return "Please enter a prompt!"
        elif self.user_query == query and self.current_result is not None: 
            try: 
                return next(self.current_result)
            except StopIteration: 
                return "We might not have the song you're looking for. Try another song?"
        else:   
            self.user_query = query 
            self.current_result = self.load_data(query)
            if self.current_result is None: 
                return "We might not have this song in our database! Please try a different song."
            else: 
                return next(self.current_result)