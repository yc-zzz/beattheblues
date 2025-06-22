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

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))  # Render sets this!
    app.run(host="0.0.0.0", port=port)
