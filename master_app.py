from flask import Flask
from personality_test.flask_app_personality import personality_app
from song_recommendation.flask_app import reco_app
from song_searcher.flask_app_search import search_app

master_app = Flask(__name__)

# Copy config from sub-apps (optional but safe)
master_app.config.update(personality_app.config)
master_app.config.update(reco_app.config)
master_app.config.update(search_app.config)

# Register routes from personality_app
for rule in personality_app.url_map.iter_rules():
    if rule.endpoint != 'static':
        view_func = personality_app.view_functions[rule.endpoint]
        master_app.add_url_rule(rule.rule, endpoint=rule.endpoint, view_func=view_func, methods=rule.methods)

# Register routes from reco_app
for rule in reco_app.url_map.iter_rules():
    if rule.endpoint != 'static':
        view_func = reco_app.view_functions[rule.endpoint]
        master_app.add_url_rule(rule.rule, endpoint=rule.endpoint, view_func=view_func, methods=rule.methods)

# Register routes from search_app
for rule in search_app.url_map.iter_rules():
    if rule.endpoint != 'static':
        view_func = search_app.view_functions[rule.endpoint]
        master_app.add_url_rule(rule.rule, endpoint=rule.endpoint, view_func=view_func, methods=rule.methods)

from flask_cors import CORS
CORS(master_app,
     origins=[
         "http://localhost:3000",
         "https://beattheblues.vercel.app"
     ],
     supports_credentials=True,
     allow_headers=["Content-Type"],
     methods=["GET", "POST", "OPTIONS"]
)

# Health Check
@master_app.route('/')
def health():
    return {"message": "Beat the Blues master backend is live!"}
