from flask import Flask, request, jsonify
from flask_cors import CORS

#import search object
try: 
    from song_search import get_search
    print("Successfully imported get_search")
except Exception as e: 
    print("Failed to import get_search, ", e) 
    get_search = None

#initialise flask app
search_app = Flask(__name__)
CORS(search_app, 
     origins=[
         "http://localhost:3000", 
         "https://beattheblues.vercel.app"
     ], 
     supports_credentials=True,
     allow_headers=['Content-Type'],
     methods=["GET", "POST", "OPTIONS"]
)

@search_app.route('/')
def health(): 
    return "Beat the Blues Flask API (Search) is Live!"

@search_app.route('/search', methods=['POST'])
def normal_search(): 
    print("/search hit")
    if get_search is None: 
        return jsonify({'error': 'Recommender not available'}), 500 
    
    try: 
        data = request.get_json()
        user_query = data.get('query')
        if not user_query: 
            return jsonify({"error": "No query provided"}), 400
        
        searcher = get_search()
        result = searcher.return_song(user_query)

        return jsonify({'search result': result})
    
    except Exception as e: 
        print("Search error: ", e)
        return jsonify({'error': str(e)}), 500