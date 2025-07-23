from reset_time import PersonalityTable
from datetime import date 
from model_utils import import_credentials

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
        self.data = None
        self.client_error = False

    def load(self): 
        self.initialise = True
        self.questions = questions
        self.engine = import_credentials
        self.data = PersonalityTable()

    def get_questions(self): 
        return self.questions 
    
    def refresh(self): 
        self.user_description = None
        self.number_calls = 0 
        self.data.refresh() #deleting logs from previous days
        self.client_error = False
    
    def no_more_requests(self): 
        if self.date != date.today(): 
            self.refresh()
        return self.number_calls > 2 or self.client_error == True #if made >3 requests a day / server down, no user_description.
    
    def get_user_description(self, answers): #assume answers is a list
        if self.no_more_requests(): 
            return "You've used up your quota for today! Please try again tomorrow."
        else: 
            #self.data.create_table() #already done! 
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

        try: 
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
                          
        return response.output[0].content[0].text