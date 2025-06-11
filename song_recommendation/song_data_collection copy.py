import pandas as pd 
from pathlib import Path 
import json 
import psycopg2
import os 
from dotenv import load_dotenv
from sqlalchemy import create_engine

#setting of top-level directory
parent_dir = Path(__file__).parent
root_directory = parent_dir / "raw data" / "acousticbrainz-highlevel-sample-json-20220623" / "highlevel"

#creating a list of all json files from the top-level directory; removing nested structure 
json_files = list(root_directory.rglob("*json"))
data = []
for file in json_files: 
    with open(file, "r", encoding="utf-8") as f: 
        try: 
            song = json.load(f)
            #basic song information 
            id = song["metadata"]["tags"]["musicbrainz_recordingid"][0]
            name = song["metadata"]["tags"]["title"][0]
            artist = song["metadata"]["tags"]["artist"][0]
            year = int(song["metadata"]["tags"]["date"][0][0:4])
            
            #song characteristics
            dance = song["highlevel"]["danceability"]["all"]["danceable"]
            gender = song["highlevel"]["gender"]["value"] #male or female
            genre = song["highlevel"]["genre_tzanetakis"]["value"] #chosen out of the 3 genre prediction models due to its relatively high accuracy and high sample size.
            acoustic = song["highlevel"]["mood_acoustic"]["all"]["acoustic"]
            aggressive = song["highlevel"]["mood_aggressive"]["all"]["aggressive"]
            electronic = song["highlevel"]["mood_electronic"]["all"]["electronic"]
            happy = song["highlevel"]["mood_happy"]["all"]["happy"]
            party = song["highlevel"]["mood_party"]["all"]["party"]
            relaxed = song["highlevel"]["mood_relaxed"]["all"]["relaxed"]
            sad = song["highlevel"]["mood_sad"]["all"]["sad"]
            mirex = song["highlevel"]["moods_mirex"]["value"] #categorises songs into one of 5 moods
            timbre = song["highlevel"]["timbre"]["all"]["bright"]
            tonal = song["highlevel"]["tonal_atonal"]["all"]["tonal"]
            voice = song["highlevel"]["voice_instrumental"]["all"]["voice"] #either voice or instrumental 

            data.append({
                        "id": id, "name": name, "artist": artist, "year": year,
                         "dance": dance, "gender": gender, "genre": genre, "acoustic": acoustic, 
                         "aggressive": aggressive, "electronic": electronic, "happy": happy, 
                         "party": party, "relaxed": relaxed, "sad": sad, "mirex": mirex, 
                         "timbre": timbre, "tonal": tonal, "voice": voice
            })

        except (KeyError, IndexError, TypeError) as error: 
            print(f"Failure to process {file}, {error}")


df = pd.DataFrame(data)
print(df.shape) #(97086, 18) -- out of an original 100,000 entries, this is still sufficient.
#print(df.isna().sum()) #No missing values in DataFrame! 
#df.to_csv("sample_data.csv", index=False) -- can be found in GitHub as a back-up, but this will be stored primarily in MySQL

load_dotenv()
#for storing as sql database via postgresql -- to implement in future iterations 

try: 
    db_user = os.environ["DB_USER"]
    db_password = os.environ["DB_PASSWORD"]
    db_host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
except Exception as e: 
    raise RuntimeError("Missing environment variable: ", e)

db_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}/{db_name}?sslmode=require"
engine = create_engine(db_url)
df.to_sql("acousticbrainz_data", engine, if_exists = "replace", index=False)
print("data inserted successfully")
