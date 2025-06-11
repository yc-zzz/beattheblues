# Libraries
import pandas as pd
from sentence_transformers import SentenceTransformer #install: pip install -U sentence-transformers
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import tensorflow as tf 
from tensorflow import keras
from keras.models import Sequential
from keras.layers import Dense, LeakyReLU
import faiss
import numpy as np

# 1. Data Preparation
# load the data
data = pd.read_csv("sample_data.csv")[:200] # to allow for faster runtime. can remove [:1000] to train on the full dataset.

# convert to appropriate datatypes (str)
data[['id', 'name', 'artist', 'gender', 'genre', 'mirex']] = data[['id', 'name', 'artist', 'gender', 'genre', 'mirex']].astype(str)
data[['dance', 'acoustic', 'aggressive', 'electronic', 'happy', 'party', 'relaxed',
      'sad', 'timbre', 'tonal', 'voice']] = data[['dance', 'acoustic', 'aggressive', 'electronic', 'happy', 'party', 'relaxed',
      'sad', 'timbre', 'tonal', 'voice']].astype(float)
data.set_index('id', inplace=True)
data = data[~data.index.duplicated(keep='first')]

# visualisation
# data.hist(bins=50, figsize=(20,15))
# data['year'].hist(bins=200, figsize=(20,15))
data1 = data['year'].copy() # this will be used later to get original year after standardisation
# plt.show()

"""
comments: most features have already been normalised into a range of 0 to 1, it is thus already normalised.
# due to the presence of outliers (e.g one datapoint has year 2082, another has year 0),
standardisation was preferred over min-max normalisation.
"""

# standardisation of year
standardscaler = StandardScaler()
df_std = standardscaler.fit_transform(data[['year']])
df_std = pd.DataFrame(df_std, columns=['year'])
df_std.index = data.index
data['year'] = df_std

# one-hot encoding -- in future iterations, to explore implementing embeddings into genre. but this will do for a POC.
data_num = pd.get_dummies(data, columns = ['gender', 'genre', 'mirex'])

# print(data_num.head())
# print(data_num.shape) #(97086, 32)

# 2. Implementation of NLP using user queries
"""
comments: A dimensionality problem arises. Song vectors are 32D while query vectors are 384D.

This would be achieved by implementing the following 4 steps:

2a. Generate synthetic text for each song via bootstrapping (future iterations may use HuggingFace's T5 models to refine the text)
2b. Run data through SentenceTransformers to get a 384D vector
2c. Train ML Deep Learning Model (on a reduced sample size) to reduce 384D to 32D -- outputs predicted 32D vector.
2d. Optimise Deep Learning Model using Cosine Similarity as loss function (compare predicted and actual 32D vector)

It makes more sense to map 384D to 32D rather than the other way around
as "ground truth" exists within the 32D space (song data).

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
data['year'] = data1 # get back the original year

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
            description += "very "
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

# 2c. Train ML model to reduce 384D vector to 32D vector
# select only the numeric columns from data_num before converting to numpy
numeric_cols = data_num.select_dtypes(include=np.number).columns.tolist()
data_num1 = data_num[numeric_cols].to_numpy()
X_train, y_train = embeddings, data_num1

model_ml = Sequential([
    Dense(128),
    LeakyReLU(negative_slope=0.1),
    Dense(64, activation='relu'),
    Dense(data_num1.shape[1])]) 

# 2d. Optimise model using cosine similarity as loss function
def cosine_similarity_loss(y_true, y_pred):
    y_true = tf.nn.l2_normalize(tf.cast(y_true, tf.float32), axis=1) # Cast y_true to float32
    y_pred = tf.nn.l2_normalize(tf.cast(y_pred, tf.float32), axis=1) # Cast y_pred to float32
    return 1 - tf.reduce_mean(tf.reduce_sum(y_true * y_pred, axis=1))

model_ml.compile(optimizer='adam', loss = cosine_similarity_loss)
history = model_ml.fit(X_train, y_train, epochs=10, batch_size=20, verbose=0, validation_split = 0.2)

# 3. Implementation of Obscure Music Algorithm
user_input = input("Tell us what you like, and we'll give you something obscure.")
user_embed = model.encode(user_input).reshape(1, -1) # Reshape for single input prediction
pred = model_ml.predict(user_embed)

def obscure_algo(vector, database, data, k=15): # min k = 5
    # ensure database is a numpy array of floats
    if isinstance(database, pd.DataFrame):
        database = database.select_dtypes(include=np.number).to_numpy()

    vector = vector / np.linalg.norm(vector, axis=1, keepdims=True)
    database = database / np.linalg.norm(database, axis=1, keepdims=True)

    # ensure the dimension for FAISS matches the normalized vectors
    index = faiss.IndexFlatIP(database.shape[1])
    index.add(database)
    D, I = index.search(vector, k)
    top_k = data.index[I[0]]

    # handle cases where k is less than 5 or data size is less than 5
    start_index = min(5, len(top_k))
    obscure_recc = top_k[start_index:]
    for id in obscure_recc:
        if id in data.index: # check if id exists in original data index
            row = data.loc[id]
            yield row['name'], row['artist']
        else:
             print(f"Warning: ID {id} not found in original data.")

# outputs obscure song 
recommendations = obscure_algo(pred, data_num, data)
name, artist = next(recommendations)
print(f"- {name} by {artist}")