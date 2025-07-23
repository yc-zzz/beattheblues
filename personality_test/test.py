from reset_time import PersonalityTable
from personality_api import Personality

#PersonalityTable Object Tests
example = PersonalityTable()

def update_table_test():
    import pandas as pd
    from datetime import date
    df = [{'id': 1, 'request_date': date(2025, 7, 21), 'description': 'yabadabadoo'}, 
        {'id': 2, 'request_date': date(2025, 7, 21), 'description': 'yabadabadoo'}]
    df = pd.DataFrame(df)
    print(example.refresh())

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

if __name__ == "__main__": 
    unittest.main()
