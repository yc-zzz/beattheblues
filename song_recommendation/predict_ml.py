# Libraries
from song_recommendation.model_utils import (
    CombinedRetrievalLoss,
    CoralOrdinalHead,
    CumulativeToClassProbabilities,
    EqualHeadCategoricalCrossEntropy,
    EqualFeatureCoralCategoricalLoss,
    cosine_similarity_loss,
    import_credentials,
)
import pandas as pd
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
       
    def load(self):
        import os
        import json
        from pathlib import Path
        os.environ["HF_HOME"] = "/tmp" #Prevent memory spikes by disabling SentenceTransformer's cache
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1" #disable GPU since Render doesn't use GPU

        if self.loaded:
            return
        print("Loading ML model and data...")

        from keras.models import load_model
        from sentence_transformers import SentenceTransformer
        import os
        
        model_path = os.path.join(os.path.dirname(__file__), 'ml_vector_reduction.keras')
        engine = import_credentials() #engine instead of self.engine to force fresh engines
        self.ml_model = load_model(
            model_path,
            custom_objects={
                "cosine_similarity_loss": cosine_similarity_loss,
                "CombinedRetrievalLoss": CombinedRetrievalLoss,
                "EqualHeadCategoricalCrossEntropy": EqualHeadCategoricalCrossEntropy,
                "CoralOrdinalHead": CoralOrdinalHead,
                "CumulativeToClassProbabilities": CumulativeToClassProbabilities,
                "EqualFeatureCoralCategoricalLoss": EqualFeatureCoralCategoricalLoss,
            },
            compile=False,
        )
        # The query encoder must be identical to the encoder used while
        # training the vector-reduction model.  Older artefacts have no
        # metadata, so retain the historical training encoder as a fallback.
        metadata_path = Path(__file__).with_name('model_metadata.json')
        encoder_name = 'all-MiniLM-L6-v2'
        if metadata_path.exists():
            with metadata_path.open(encoding='utf-8') as handle:
                encoder_name = json.load(handle).get('encoder', encoder_name)
        self.nlp_model = SentenceTransformer(encoder_name)

        try:
            with engine.connect() as conn:
                self.num_data_df = pd.read_sql("SELECT * FROM song_vector", con=conn, index_col='id')
        except Exception as e:
            print(e)
            raise

        self.num_data = self.num_data_df.to_numpy().astype(float)
        self.loaded = True

    def generate_25d_vector(self, query):
        self.current_query = query
        user_embed = self.nlp_model.encode(self.current_query).reshape(1, -1)
        pred  = self.ml_model.predict(user_embed, verbose=0)
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
        engine = import_credentials()
        with engine.connect() as conn: 
            recommendations = pd.read_sql(query, con=conn, params=tuple(top_k_list), index_col='id')
        for ind, row in recommendations.iterrows(): 
            yield f"{row['name']} by {row['artist']}"
        
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
