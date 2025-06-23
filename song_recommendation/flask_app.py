from predict_ml import Recommendation 
from flask import Flask, request, jsonify

#Initialise Flask App
app = Flask(__name__)

#Global calling of recommendation, to prevent unnecessary loading of models
#Allows for querying multiple times while model is only trained once
recommendation = Recommendation()

@app.route('/recommend', methods=['POST'])
def recommend(): 
    data = request.get_json()
    user_query = data.get('query')
    if not user_query: 
        return jsonify({"Error": "No query provided"}), 400
    
    result = recommendation.song_recommendation(user_query)
    return jsonify({'recommendation': result})

