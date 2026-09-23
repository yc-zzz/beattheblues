import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
import tensorflow as tf 


@tf.keras.utils.register_keras_serializable(package="song_recommendation")
class CombinedRetrievalLoss(tf.keras.losses.Loss):
    """MSE for continuous targets plus mean categorical cross-entropy.

    The model emits one concatenated retrieval vector.  Its categorical
    segments are softmax probabilities, so this loss can train a multi-head
    model while preserving the single vector consumed by the FAISS retriever.
    """

    def __init__(
        self,
        numeric_size: int,
        categorical_sizes: tuple[int, ...] | list[int],
        lambda_numeric: float = 1.0,
        lambda_categorical: float = 1.0,
        name: str = "combined_retrieval_loss",
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        if numeric_size <= 0:
            raise ValueError("numeric_size must be positive.")
        if not categorical_sizes or any(size <= 1 for size in categorical_sizes):
            raise ValueError("categorical_sizes must contain category counts greater than one.")
        self.numeric_size = int(numeric_size)
        self.categorical_sizes = tuple(int(size) for size in categorical_sizes)
        self.lambda_numeric = float(lambda_numeric)
        self.lambda_categorical = float(lambda_categorical)

    def call(self, y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred, tf.float32)
        numeric_loss = tf.reduce_mean(
            tf.square(y_true[:, :self.numeric_size] - y_pred[:, :self.numeric_size]), axis=-1
        )
        start = self.numeric_size
        categorical_losses = []
        for size in self.categorical_sizes:
            stop = start + size
            categorical_losses.append(
                tf.keras.losses.categorical_crossentropy(
                    y_true[:, start:stop], y_pred[:, start:stop]
                )
            )
            start = stop
        categorical_loss = tf.add_n(categorical_losses) / len(categorical_losses)
        return self.lambda_numeric * numeric_loss + self.lambda_categorical * categorical_loss

    def get_config(self):
        return {
            **super().get_config(),
            "numeric_size": self.numeric_size,
            "categorical_sizes": list(self.categorical_sizes),
            "lambda_numeric": self.lambda_numeric,
            "lambda_categorical": self.lambda_categorical,
        }

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
