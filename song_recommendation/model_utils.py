import os
from dotenv import load_dotenv
import psycopg2
from sqlalchemy import create_engine
import tensorflow as tf 
import keras


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


@tf.keras.utils.register_keras_serializable(package="song_recommendation")
class EqualHeadCategoricalCrossEntropy(tf.keras.losses.Loss):
    """Mean categorical cross-entropy across independently normalised heads.

    Every semantic feature contributes one loss term irrespective of how many
    classes it has. This is important for Experiment 4: a five-bin acoustic
    feature must not outweigh a two-class gender feature merely because its
    one-hot block contains more dimensions.
    """

    def __init__(
        self,
        head_sizes: tuple[int, ...] | list[int],
        name: str = "equal_head_categorical_cross_entropy",
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        if not head_sizes or any(int(size) <= 1 for size in head_sizes):
            raise ValueError("head_sizes must contain class counts greater than one.")
        self.head_sizes = tuple(int(size) for size in head_sizes)

    def call(self, y_true, y_pred):
        y_true = tf.cast(y_true, tf.float32)
        y_pred = tf.cast(y_pred, tf.float32)
        start = 0
        head_losses = []
        for size in self.head_sizes:
            stop = start + size
            head_losses.append(
                tf.keras.losses.categorical_crossentropy(
                    y_true[:, start:stop], y_pred[:, start:stop]
                )
            )
            start = stop
        return tf.add_n(head_losses) / len(head_losses)

    def get_config(self):
        return {**super().get_config(), "head_sizes": list(self.head_sizes)}


@keras.saving.register_keras_serializable(package="song_recommendation")
class CoralOrdinalHead(keras.layers.Layer):
    """Rank-consistent CORAL head returning ``P(Y > k)`` for each threshold."""

    def __init__(self, num_classes: int, **kwargs):
        super().__init__(**kwargs)
        if num_classes < 2:
            raise ValueError("A CORAL head needs at least two ordered classes.")
        self.num_classes = int(num_classes)

    def build(self, input_shape):
        self.kernel = self.add_weight(
            name="kernel", shape=(int(input_shape[-1]), 1), initializer="glorot_uniform",
        )
        # Positive increments give increasing thresholds. Centre them so the
        # latent score remains free to model the overall class location.
        self.raw_threshold_gaps = self.add_weight(
            name="raw_threshold_gaps", shape=(self.num_classes - 1,), initializer="zeros",
        )

    def call(self, inputs):
        score = keras.ops.matmul(inputs, self.kernel)
        thresholds = keras.ops.cumsum(keras.ops.softplus(self.raw_threshold_gaps))
        thresholds -= keras.ops.mean(thresholds)
        return keras.ops.sigmoid(score - keras.ops.expand_dims(thresholds, axis=0))

    def get_config(self):
        return {**super().get_config(), "num_classes": self.num_classes}


@keras.saving.register_keras_serializable(package="song_recommendation")
class CumulativeToClassProbabilities(keras.layers.Layer):
    """Convert monotonic CORAL cumulative probabilities into class masses."""

    def call(self, cumulative_probabilities):
        cumulative_probabilities = keras.ops.cast(cumulative_probabilities, "float32")
        first = 1.0 - cumulative_probabilities[:, :1]
        middle = cumulative_probabilities[:, :-1] - cumulative_probabilities[:, 1:]
        last = cumulative_probabilities[:, -1:]
        probabilities = keras.ops.concatenate((first, middle, last), axis=-1)
        # Ordered CORAL thresholds make these non-negative; the clamp protects
        # against only floating-point round-off at neighbouring thresholds.
        return keras.ops.maximum(probabilities, 0.0)

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[1] + 1)


@keras.saving.register_keras_serializable(package="song_recommendation")
class EqualFeatureCoralCategoricalLoss(keras.losses.Loss):
    """Equal-weight mean of CORAL ordinal and categorical feature losses."""

    def __init__(
        self,
        num_ordinal_features: int,
        ordinal_num_classes: int,
        categorical_sizes: tuple[int, ...] | list[int],
        name: str = "equal_feature_coral_categorical_loss",
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        if num_ordinal_features <= 0 or ordinal_num_classes < 2:
            raise ValueError("Ordinal feature and class counts must be positive.")
        if not categorical_sizes or any(int(size) <= 1 for size in categorical_sizes):
            raise ValueError("categorical_sizes must contain class counts greater than one.")
        self.num_ordinal_features = int(num_ordinal_features)
        self.ordinal_num_classes = int(ordinal_num_classes)
        self.categorical_sizes = tuple(int(size) for size in categorical_sizes)

    def call(self, y_true, y_pred):
        y_true = keras.ops.cast(y_true, "float32")
        y_pred = keras.ops.cast(y_pred, "float32")
        start = 0
        feature_losses = []
        for _ in range(self.num_ordinal_features):
            stop = start + self.ordinal_num_classes
            true_class_probabilities = y_true[:, start:stop]
            predicted_class_probabilities = y_pred[:, start:stop]
            # For a one-hot class target, tails [1:] are exactly the CORAL
            # threshold labels I(Y > 0), ..., I(Y > K - 2).
            true_cumulative = keras.ops.flip(
                keras.ops.cumsum(keras.ops.flip(true_class_probabilities, axis=-1), axis=-1), axis=-1,
            )[:, 1:]
            predicted_cumulative = keras.ops.flip(
                keras.ops.cumsum(keras.ops.flip(predicted_class_probabilities, axis=-1), axis=-1), axis=-1,
            )[:, 1:]
            threshold_bce = keras.ops.binary_crossentropy(
                true_cumulative, predicted_cumulative
            )
            # Average the K-1 threshold losses before this feature joins the
            # other heads, so every semantic feature has equal weight.
            feature_losses.append(keras.ops.mean(threshold_bce, axis=-1))
            start = stop
        for size in self.categorical_sizes:
            stop = start + size
            feature_losses.append(keras.losses.categorical_crossentropy(
                y_true[:, start:stop], y_pred[:, start:stop]
            ))
            start = stop
        return keras.ops.sum(keras.ops.stack(feature_losses, axis=0), axis=0) / len(feature_losses)

    def get_config(self):
        return {
            **super().get_config(),
            "num_ordinal_features": self.num_ordinal_features,
            "ordinal_num_classes": self.ordinal_num_classes,
            "categorical_sizes": list(self.categorical_sizes),
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
