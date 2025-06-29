#from predict_ml import get_recommender
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

try:
    from predict_ml import get_recommender
    print("predict_ml imported successfully")
except Exception as e:
    print("predict_ml import failed:", e)
    get_recommender = None

#Initialise Flask App
app = Flask(__name__)
CORS(app,
     origins=[
         "http://localhost:3000",
         "https://beattheblues.vercel.app"
     ],
     supports_credentials=True,
     allow_headers=["Content-Type"],
     methods=["GET", "POST", "OPTIONS"]
)

@app.route('/')
def health():
    return 'Beat the Blues Flask API is live!'

@app.route('/recommend', methods=['POST'])
def recommend():
    print("/recommend hit")
    if get_recommender is None:
        return jsonify({'error': 'Recommender not available'}), 500

    try:
        data = request.get_json()
        user_query = data.get('query')
        if not user_query:
            return jsonify({"error": "No query provided"}), 400

        recommender = get_recommender()
        result = recommender.song_recommendation(user_query)

        return jsonify({'recommendation': result})
    
    except Exception as e:
        print("Recommendation error:", e)
        return jsonify({'error': str(e)}), 500