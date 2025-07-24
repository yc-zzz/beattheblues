from personality_api import Personality

#Personality Object Tests
test = Personality()
test.load()

def test_get_questions(): 
    print(test.get_questions())

def test_no_more_requests(): 
    print(test.no_more_requests())
    test.number_calls = 4
    print(test.no_more_requests())

def test_get_user_description(): 
    sample_answers = ["INFP", "Sombre, Reflective, Emotional, Hopeful", 
                      "Drinking Gin & Tonic at a underground jazz bar", 
                      "Dan Forrest, Melomance, Jacob Collier", 
                      "Knafeh", "A sentimental fool with a heart that cares for others", 
                      "Loneliness"]
    print(test.get_user_description(sample_answers))
    print(test.number_calls)
    print(test.get_user_description(sample_answers))
    print(test.number_calls)
    print(test.get_user_description(sample_answers))
    print(test.number_calls)
    print(test.get_user_description(sample_answers))
    print(test.number_calls)

#flask app tests
import unittest 
from flask_app_personality import personality_app 

class FlaskTestCase(unittest.TestCase): 
    def setUp(self): 
        self.app = personality_app.test_client()
        self.app.testing = True 
    
    def test_health(self): 
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"message": "Beat the Blues Flask API (Personality) is live!"})

    def test_personality_display(self): 
        response = self.app.get('/personality', json = {'action': 'display'})
        self.assertEqual(response.get_json(), test.get_questions())

    def test_personality_description(self):
        response = self.app.post('/personality', json = {'action': 'description'})
        self.assertEqual(response.status_code, 200)

    def test_fetch_playlist(self): 
        response = self.app.post('/personality', json = {'action': 'playlist'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"playlist": 'No description found, unable to generate playlist!'})

if __name__ == "__main__": 
    unittest.main()