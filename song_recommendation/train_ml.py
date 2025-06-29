# Libraries
from model_utils import import_credentials, cosine_similarity_loss
import psycopg2
from sqlalchemy import text
import pandas as pd
from sentence_transformers import SentenceTransformer #install: pip install -U sentence-transformers
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from keras.models import Sequential
from keras.layers import Dense, LeakyReLU
import numpy as np

# 1. Data Preparation
#a. load the data
engine = import_credentials()
data = pd.read_sql("SELECT * FROM acousticbrainz_data", con=engine, index_col = 'id') 

#b. visualisation
# data.hist(bins=50, figsize=(20,15))
# data['year'].hist(bins=200, figsize=(20,15))
#data1 = data['year'].copy() # this will be used later to get original year after standardisation
# plt.show()

"""
comments: most features have already been normalised into a range of 0 to 1, it is thus already normalised.
# due to the presence of outliers (e.g one datapoint has year 2082, another has year 0),
standardisation was preferred over min-max normalisation for 'year'.
"""

#c. creation of numerical database for cosine similarity comparison.
# standardisation of year
standardscaler = StandardScaler()
df_std = standardscaler.fit_transform(data[['year']])
df_std = pd.DataFrame(df_std, columns=['year'])
df_std.index = data.index
data['year_std'] = df_std

# one-hot encoding 
data_num = pd.get_dummies(data, columns = ['gender', 'genre', 'mirex'])
data_num = data_num.drop(columns=['year']) #data will have 'year', data_num will have 'year_std'
#print(data_num.dtypes)

numeric_cols = data_num.select_dtypes(include=[np.number, bool]).columns.to_list()
data_num = data_num[numeric_cols]

# print(data_num.head())
# print(data_num.shape) 

data_num.to_sql("song_vector", engine, if_exists='replace', index=True, index_label = 'id')

with engine.connect() as conn: 
    conn.execute(text("""
                 ALTER TABLE song_vector
                 ADD PRIMARY KEY (id);
                 """))
    conn.commit()

print("database created")

# 2. Implementation of NLP using user queries
"""
comments: A dimensionality problem arises. Song vectors are 25D while query vectors are 384D.

This would be achieved by implementing the following 4 steps:

2a. Generate synthetic text for each song via bootstrapping (future iterations may use HuggingFace's T5 models to refine the text)
2b. Run data through SentenceTransformers to get a 384D vector
2c. Train ML Deep Learning Model (on a reduced sample size) to reduce 384D to 25D -- outputs predicted 25D vector.
2d. Optimise Deep Learning Model using Cosine Similarity as loss function (compare predicted and actual 25D vector)

It makes more sense to map 384D to 25D rather than the other way around
as "ground truth" exists within the 25D space (song data).

Also note that the distinction between data and data_num was intentional.
data_num contains numerical data with one-hot encoding of genre and mirex.
data will be used to generate synthetic text, as detailed later.
"""

# 2a. Generate synthetic text: Bootstrapping + Refinement
# genres spelt out in full
replace_values_genre = {'blu': 'blues', 'cla': 'classical', 'cou': 'country', 'dis': 'disco', 'hip': 'hiphop', 'jaz': 'jazz',
                        'met': 'metal', 'reg': 'reggae', 'roc': 'rock'}

# provide richer metadata -- data from AcousticBrainz data
replace_values_mirex = {'cluster1': 'passionate, rousing, confident, boisterous, rowdy, ',
                        'cluster2': 'rollicking, cheerful, fun, sweet, amiable, ',
                        'cluster3': 'literate, poignant, wistful, bittersweet, autumnal, brooding, ',
                        'cluster4': 'humorous, silly, campy, quirky, whimsical, witty, wry, ',
                        'cluster5': 'aggressive, fiery, anxious, intense, volatile, visceral, '}
data['genre'] = data['genre'].replace(replace_values_genre)
data['mirex'] = data['mirex'].replace(replace_values_mirex)

# generate bootstrapped song description
def generate_description(song):
    name, artist, year, gender = song['name'], song['artist'], song['year'], song['gender']
    genre, mirex = song['genre'], song['mirex']
    description = f"This song is {name}, sung by {artist} in {year}. Sung by a {gender}. Likely falls into the {genre} genre. Has the following undertones: {mirex} "
    song_num = song[['dance', 'acoustic', 'aggressive', 'electronic', 'happy', 'party', 'relaxed','sad', 'timbre', 'tonal', 'voice']]
    song_num = song_num.rename({'timbre': 'bright'})
    for col, value in song_num.items():
        if value < 0.25:
            description += "not "
        elif 0.25 <= value < 0.5:
            description += "not very "
        elif 0.5 <= value < 0.75:
            description += "quite "
        else:
            description += "extremely "
        description += str(col) + ","
    if song['voice'] < 0.5:
        description += "instrumental"
    else:
        description += "vocal"
    return description

sentences = []
for idx, song in data.iterrows():
    sentences.append(generate_description(song))

# 2b. Generate 384D vectors using synthetic output
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(sentences, batch_size=32)

# 2c. Train ML model to reduce 384D vector to 25D vector
# select only the numeric columns from data_num before converting to numpy
data_num1 = pd.read_sql("SELECT * FROM song_vector", con = engine, index_col = 'id')
data_num1 = data_num1.to_numpy()

#assign each embedding with a "ground truth" in y_train (supervised learning)
X_train, y_train = embeddings, data_num1.astype(float)

#train model
model_ml = Sequential([
    Dense(128),
    LeakyReLU(negative_slope=0.1),
    Dense(64, activation='relu'),
    Dense(data_num1.shape[1])]) #corresponds to the feature space of song data

# 2d. Optimise model using cosine similarity as loss function
def train_model(): 
    model_ml.compile(optimizer='adam', loss = cosine_similarity_loss)
    history = model_ml.fit(X_train, y_train, epochs=10, batch_size=20, verbose=0, validation_split = 0.2)
    model_ml.save('ml_vector_reduction.keras')

if __name__ == '__main__': 
    train_model()

print("model trained")