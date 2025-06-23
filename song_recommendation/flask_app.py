from predict_ml import get_recommender
from flask import Flask, request, jsonify
import os

#Initialise Flask App
app = Flask(__name__)

#Global calling of recommendation, to prevent unnecessary loading of models
#Allows for querying multiple times while model is only trained once
#recommendation = Recommendation()

@app.route('/')
def health():
    return 'Beat the Blues Flask API is live!'

@app.route('/recommend', methods=['POST'])
def recommend(): 
    data = request.get_json()
    user_query = data.get('query')
    if not user_query: 
        return jsonify({"Error": "No query provided"}), 400
    
    recommender = get_recommender()
    result = recommender.song_recommendation(user_query)
    return jsonify({'recommendation': result})
