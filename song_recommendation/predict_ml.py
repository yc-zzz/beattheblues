# Libraries
from model_utils import import_credentials, cosine_similarity_loss
import pandas as pd
#from sentence_transformers import SentenceTransformer #install: pip install -U sentence-transformers
#from tensorflow import keras
#from keras.models import load_model
import faiss
import numpy as np

recommender = None  # Global but uninitialized

print("predict_ml.py has been imported")

def get_recommender():
    print("get_recommender() was called")
    global recommender
    if recommender is None:
        print("Instantiating Recommendation()")
        recommender = Recommendation()
    if not recommender.loaded:
        print("Loading model...")
        recommender.load()
    return recommender

# Implementation of Obscure Music Algorithm (using OOP) 
class Recommendation: 
    def __init__(self):
        self.engine = None
        self.ml_model = None
        self.num_data_df = None
        self.num_data = None
        self.nlp_model = None
        self.current_query = None
        self.current_result = None
        self.loaded = False
        '''
        self.engine = import_credentials()
        self.ml_model = load_model('ml_vector_reduction.keras', custom_objects = {"cosine_similarity_loss": cosine_similarity_loss})
        self.num_data_df = pd.read_sql("SELECT * FROM song_vector", con=self.engine, index_col = 'id')
        self.num_data = self.num_data_df.to_numpy().astype(float)
        self.nlp_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.current_query = None
        self.current_result = None 
        ''' 
    def load(self):
        if self.loaded:
            return
        print("Loading ML model and data...")

        from tensorflow import keras
        from keras.models import load_model
        from sentence_transformers import SentenceTransformer
        
        self.engine = import_credentials()
        self.ml_model = load_model('ml_vector_reduction.keras', custom_objects = {"cosine_similarity_loss": cosine_similarity_loss})
        self.num_data_df = pd.read_sql("SELECT * FROM song_vector", con=self.engine, index_col='id')
        self.num_data = self.num_data_df.to_numpy().astype(float)
        self.nlp_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.loaded = True

    def generate_25d_vector(self, query):
        self.current_query = query
        user_embed = self.nlp_model.encode(self.current_query).reshape(1, -1)
        pred  = self.ml_model.predict(user_embed)
        return pred  
    
    def obscure_algo(self, vector, k=15):
        #normalisation
        vector = vector / np.linalg.norm(vector, axis=1, keepdims=True)
        normalised_data = self.num_data / np.linalg.norm(self.num_data, axis=1, keepdims=True)
        
        #indexing
        index = faiss.IndexFlatIP(normalised_data.shape[1])
        index.add(normalised_data)
        D, I = index.search(vector, k) #I is a numpy array
        top_k = self.num_data_df.index[I[0]] #acceptable, because num_data and acousticbrainz data have the same index column (id).  
        
        #data retrieval
        top_k_list = top_k.tolist()
        placeholder = ','.join(['%s'] * len(top_k_list))
        query = f"""SELECT id, name, artist
                FROM acousticbrainz_data
                WHERE id IN ({placeholder})
        """
        with self.engine.connect() as conn: 
            recommendations = pd.read_sql(query, con=self.engine, params = tuple(top_k_list), index_col = 'id')
        for ind, row in recommendations.iterrows(): 
            yield f"- {row['name']} by {row['artist']}"
        
    def song_generation(self, query):  
        vector = self.generate_25d_vector(query)
        self.current_result = self.obscure_algo(vector)
        try: 
            return next(self.current_result)
        except StopIteration: 
            return "No more results, please give us a new description!"
    
    def song_recommendation(self, query): 
        if query == self.current_query: 
            try: 
                return next(self.current_result) 
            except StopIteration: 
                return "Please give us a new description!"
        else: 
            self.current_query = query
            return self.song_generation(query)
            
#glo
#recommender = Recommendation()

#query = input("Tell us what you like, and we'll give you something obscure.")
#print(recommender.song_recommendation(query))