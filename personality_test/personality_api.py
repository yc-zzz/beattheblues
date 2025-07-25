from datetime import date 
from personality_test.model_utils import import_credentials

questions = [
    {"id": 1, "question": "What is your MBTI?"}, 
    {"id": 2, "question": "Describe yourself using 4 adjectives."},
    {"id": 3, "question": "Describe your ideal music experience (e.g smoky jazz lounge, concert hall, etc.)."},
    {"id": 4, "question": "Give me your top 3 artists."},
    {"id": 5, "question": "What's your favourite food?"},
    {"id": 6, "question": "Describe your best friend."},
    {"id": 7, "question": "What emotion do you resonate with the most?"},
    ]

personality = None 
def get_personality(): 
    print("get_personality was called.")
    global personality
    if personality == None: 
        print("Initialising personality object...")
        personality = Personality()
    if personality.initialise == False: 
        personality.load()
    return personality

class Personality: 
    def __init__(self): 
        self.initialise = False
        self.questions = None
        self.answers = None
        self.user_description = None
        self.number_calls = 0  
        self.date = date.today()
        self.engine = None
        self.client_error = False

    def load(self): 
        self.initialise = True
        self.questions = questions
        self.engine = import_credentials
        
    def get_questions(self): 
        return self.questions 
    
    def refresh(self): 
        self.user_description = None
        self.number_calls = 0 
        self.client_error = False
    
    def no_more_requests(self): #if made >=3 requests a day / server down, no user_description.
        if self.date != date.today(): 
            self.refresh()
        if self.client_error == True: 
            return "Client Error"
        elif self.number_calls > 2: 
            return "Too many tries"
        else: 
            return "Continue" 
    
    def get_user_description(self, answers): #assume answers is a list
        if self.no_more_requests() == "Client Error": 
            return f"API is down, try again tomorrow! Your current profile: {self.user_description}"
        elif self.no_more_requests() == "Too many tries": 
            return f"Too many tries, try again tomorrow! Your current profile: {self.user_description}"
        else: 
            descriptors = ["My MBTI is: ", 
                           "4 adjectives that can be used to describe me are: ", 
                           "My ideal music experience is: ", 
                           "My favourite food is: ", 
                           "Here's how I'd describe my best friend: ", 
                           "I resonate with this emotion the most: ", 
                           "My top 3 artists are: "]
            self.answers = dict(zip(descriptors, answers))
            prompt = f"""You are a veteran in the music industry and a psychologist. 
            Based on the following descriptions, tastefully profile this individual's music taste in 3 sentences. 
            Specifically, give a sketch of who you think this individual might be like, 
            what kind of music he might enjoy or not, what he might be contemplating as he enjoys the music, and where he/she might enjoy his/her music. 
            You are not ChatGPT, simply provide the sentences without any preamble or addressing me. {self.answers}
            """

        import os 
        import openai
        import time
        from dotenv import load_dotenv

        try: 
            load_dotenv()
            api_key = os.environ['API_KEY']
        except Exception as e: 
            raise RuntimeError("Missing environment variable: ", e)
        
        try: 
            client = openai.OpenAI(api_key=api_key)
            print("Calling API...")
            response = client.responses.create(model="gpt-4o-mini", 
                                               input= [{"role": "user", 
                                                    "content": prompt}])
            self.number_calls += 1
            time.sleep(1)
        except openai.InternalServerError as e: 
            print("API rejected request: ", e)
            self.number_calls += 1
            self.client_error = True
            time.sleep(1)

        except Exception as e:
            print("Error: ", e) 

        self.user_description = response.output[0].content[0].text
        return self.user_description
    
    def get_playlist(self): 
        if self.user_description == None: 
            return "No description found, unable to generate playlist!"
        else: 
            from song_recommendation.predict_ml import get_recommender
            import numpy as np 
            import pandas as pd 
            import faiss

            recommender = get_recommender() 
            vector = recommender.generate_25d_vector(self.user_description) 

            vector = vector / np.linalg.norm(vector, axis=1, keepdims=True)
            normalised_data = get_recommender().num_data / np.linalg.norm(get_recommender().num_data, axis=1, keepdims=True)
        
            #indexing
            index = faiss.IndexFlatIP(normalised_data.shape[1])
            index.add(normalised_data)
            D, I = index.search(vector, 6) #I is a numpy array, gets 6 songs
            top_k = get_recommender().num_data_df.index[I[0]] #acceptable, because num_data and acousticbrainz data have the same index column (id).  
            
            #data retrieval
            top_k_list = top_k.tolist()
            placeholder = ','.join(['%s'] * len(top_k_list))
            query = f"""SELECT id, name, artist
                    FROM acousticbrainz_data
                    WHERE id IN ({placeholder})
            """
            with self.engine.connect() as conn: 
                recommendations = pd.read_sql(query, con=self.engine, params = tuple(top_k_list), index_col = 'id')
                playlist = recommendations[['name', 'artist']].to_dict(orient = 'records')
                return playlist
