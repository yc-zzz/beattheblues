from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

#import Personality
try: 
    from personality_test.personality_api import get_personality
    print("get_personality successfully imported.")
except Exception as e: 
    print("Failed to import get_personality ", e)
    get_personality = None

#functions for retrieval & recommendation
#gets questions from API, displays them
def display_question(): 
    print("Retrieving questions...") #checks if function is called

    try: 
        questions = get_personality().get_questions()
        return jsonify(questions)
    except requests.exceptions.RequestException as e: 
        print("Error: ", e)
        return jsonify({'error': str(e)}), 400 
    
#returns personality description
def personality_description(data): 
    print("Getting personality description...") #checks if function is called 
    
    try:
        response = data.get("answers", []) #returns list, empty list if failed. 
        description = get_personality().get_user_description(response)
        return jsonify({'description': description})
    except Exception as e: 
        print('Something went wrong: ', e)
        return jsonify({'error': e})
    
def fetch_playlist(): 
    print("Getting playlist...")

    try: 
        playlist = get_personality().get_playlist()
        return jsonify({'playlist': playlist})
    except Exception as e: 
        print('No playlist fetched: ', e)
        return jsonify({'error': e})

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
    return jsonify({"message": "Beat the Blues Flask API (Personality) is live!"}), 200

#methods associated with personality test
@personality_app.route('/personality', methods = ['GET', 'POST'])
def action(): 
    data = request.get_json()
    action = data.get("action") #frontend must send {"action": "..."}
    if action == "display": 
        return display_question()
    elif action == "description": 
        return personality_description(data)
    elif action == "playlist": 
        return fetch_playlist()
    else: 
        return "Unknown action", 400





