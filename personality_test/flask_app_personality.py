from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

#Initialise Flask App 
personality_app = Flask(__name__)
CORS(personality_app, 
     origins = [
         "http://localhost:3000", 
         "https://beattheblues.vercel.app"
     ], 
     supports_credentials = True, 
     allow_headers = 'Content-Type', 
     methods = ['GET', 'POST', 'OPTIONS']
)

#health check
@personality_app.route('/')
def health(): 
    print("Beat the Blues Flask API (Personality) is live!")

#methods associated with personality test
@personality_app.route('/personality', methods = ['GET', 'POST'])

#gets questions from API, displays them
def display_question(): 
    print("Getting data from 16personalities-api...") #checks if function is called
    get_url = "https://16personalities-api.com/api/personality/questions"
    
    try: 
        get_response = requests.get(get_url)
    except requests.exceptions.RequestException as e: 
        print("Error: ", e)
        return jsonify({'error': str(e)}), 400 
    
    response_json = get_response.json()
    return response_json

def personality_description(): 
    print("Getting personality description...") #checks if function is called 
    
    data = request.get_json()
    response = data.get("answers") 
    """data should be a json array. {"answers": [{"id": "something", "value": "something else"}, {...} ...], "gender": "male/female" }"""





