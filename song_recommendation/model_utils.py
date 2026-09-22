import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
import tensorflow as tf 

#import credentials 
def import_credentials(): 
    load_dotenv()
    try: 
        db_url = os.environ["NEON_CONNECTION_STRING"]
    except Exception as e: 
        raise RuntimeError("Missing connection string: ", e)

    engine = create_engine(db_url)
    return engine

#cosine similarity loss 
def cosine_similarity_loss(y_true, y_pred):
    y_true = tf.nn.l2_normalize(tf.cast(y_true, tf.float32), axis=-1) # Cast y_true to float32
    y_pred = tf.nn.l2_normalize(tf.cast(y_pred, tf.float32), axis=-1) # Cast y_pred to float32
    return 1 - tf.reduce_mean(tf.reduce_sum(y_true * y_pred, axis=1)) #turns into a loss function when subtracted from 1