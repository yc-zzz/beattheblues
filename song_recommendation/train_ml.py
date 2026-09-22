"""Train and audit the text-description-to-song-vector model.

Run ``python song_recommendation/train_ml.py --epochs 10``. The model fits on
80% of song descriptions, then retrieves songs for the held-out 20%.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from keras.layers import Dense, LeakyReLU
from keras.models import Sequential
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sqlalchemy import text

try:  # Supports both ``python -m`` and direct execution.
    from song_recommendation.evaluation import evaluate_retrieval, save_evaluation_artifacts
    from song_recommendation.model_utils import cosine_similarity_loss, import_credentials
except ModuleNotFoundError:
    from evaluation import evaluate_retrieval, save_evaluation_artifacts
    from model_utils import cosine_similarity_loss, import_credentials


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_ENCODER = "all-MiniLM-L6-v2"
NUMERIC_COLUMNS = (
    "dance", "acoustic", "aggressive", "electronic", "happy", "party",
    "relaxed", "sad", "timbre", "tonal", "voice",
)
CATEGORICAL_COLUMNS = ("gender", "genre", "mirex")
GENRE_NAMES = {
    "blu": "blues", "cla": "classical", "cou": "country", "dis": "disco",
    "hip": "hiphop", "jaz": "jazz", "met": "metal", "reg": "reggae", "roc": "rock",
}
MIREX_DESCRIPTIONS = {
    "cluster1": "passionate, rousing, confident, boisterous, rowdy",
    "cluster2": "rollicking, cheerful, fun, sweet, amiable",
    "cluster3": "literate, poignant, wistful, bittersweet, autumnal, brooding",
    "cluster4": "humorous, silly, campy, quirky, whimsical, witty, wry",
    "cluster5": "aggressive, fiery, anxious, intense, volatile, visceral",
}


def generate_description(song: pd.Series) -> str:
    """Create the deterministic natural-language description for a song."""
    genre = GENRE_NAMES.get(str(song["genre"]).lower(), str(song["genre"]))
    mirex = MIREX_DESCRIPTIONS.get(str(song["mirex"]).lower(), str(song["mirex"]))
    description = (
        f"This song is {song['name']}, sung by {song['artist']} in {song['year']}. "
        f"Sung by a {song['gender']}. Likely falls into the {genre} genre. "
        f"Has the following undertones: {mirex}. "
    )
    for column in NUMERIC_COLUMNS:
        value = float(song[column])
        qualifier = "not " if value < 0.25 else "not very " if value < 0.5 else "quite " if value < 0.75 else "extremely "
        name = "bright" if column == "timbre" else column
        description += f"{qualifier}{name}, "
    return description + ("instrumental" if float(song["voice"]) < 0.5 else "vocal")


def make_target_vectors(data: pd.DataFrame, train_ids: pd.Index) -> tuple[pd.DataFrame, dict]:
    """Build target vectors using preprocessing fitted on training songs only."""
    train = data.loc[train_ids]
    year_mean = float(train["year"].mean())
    year_scale = float(train["year"].std(ddof=0)) or 1.0
    vectors = data.loc[:, NUMERIC_COLUMNS].astype(float).copy()
    vectors["year_std"] = (data["year"].astype(float) - year_mean) / year_scale
    category_levels = {}
    for column in CATEGORICAL_COLUMNS:
        levels = sorted(train[column].astype(str).unique().tolist())
        category_levels[column] = levels
        encoded = pd.get_dummies(data[column].astype(str), prefix=column, dtype=float)
        expected = [f"{column}_{level}" for level in levels]
        vectors = pd.concat([vectors, encoded.reindex(columns=expected, fill_value=0.0)], axis=1)
    vectors.index = data.index
    metadata = {
        "encoder": DEFAULT_ENCODER, "year_mean": year_mean, "year_scale": year_scale,
        "target_columns": vectors.columns.tolist(), "category_levels": category_levels,
    }
    return vectors.astype(float), metadata


def load_song_data(csv_path: str | None = None) -> pd.DataFrame:
    """Load a database catalogue, or a local CSV for a repeatable dry run."""
    if csv_path:
        data = pd.read_csv(csv_path, index_col="id")
    else:
        engine = import_credentials()
        data = pd.read_sql("SELECT * FROM acousticbrainz_data", con=engine, index_col="id")
    data.index = data.index.astype(str)
    # A song ID is the class label, so duplicates cannot be evaluated exactly.
    return data.loc[~data.index.duplicated(keep="first")].copy()


def build_model(input_dimensions: int, output_dimensions: int) -> Sequential:
    return Sequential([
        Dense(128, input_shape=(input_dimensions,)), LeakyReLU(negative_slope=0.1),
        Dense(64, activation="relu"), Dense(output_dimensions),
    ])


def train_in_batches(
    model: Sequential,
    embeddings: np.ndarray,
    targets: np.ndarray,
    *,
    epochs: int,
    batch_size: int,
    random_state: int,
) -> None:
    """Train without Keras's multi-epoch data adapter.

    On the current macOS/TensorFlow runtime, ``model.fit`` exits natively
    after its first epoch.  Explicit batches retain the identical optimizer
    and loss while avoiding that unstable epoch-transition path.
    """
    rng = np.random.default_rng(random_state)
    for epoch in range(epochs):
        order = rng.permutation(len(embeddings))
        losses = []
        for start in range(0, len(order), batch_size):
            batch = order[start:start + batch_size]
            losses.append(float(model.train_on_batch(embeddings[batch], targets[batch])))
        print(f"Epoch {epoch + 1}/{epochs} - loss: {np.mean(losses):.6f}")


def encode_descriptions(
    data: pd.DataFrame, song_ids: pd.Index, *, encoder_name: str, batch_size: int
) -> np.ndarray:
    """Encode one split at a time to keep the 86k-song run within memory."""
    descriptions = data.loc[song_ids].apply(generate_description, axis=1).tolist()
    encoder = SentenceTransformer(encoder_name)
    embeddings = np.asarray(
        encoder.encode(descriptions, batch_size=batch_size, show_progress_bar=True), dtype=np.float32
    )
    del descriptions, encoder
    gc.collect()
    return embeddings


def train_and_evaluate(
    data: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    epochs: int = 10,
    batch_size: int = 32,
    encoder_name: str = DEFAULT_ENCODER,
) -> tuple[Sequential, pd.DataFrame, dict, dict, pd.DataFrame]:
    """Fit on 80%, retrieve the held-out 20% against the full catalogue."""
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between zero and one.")
    if len(data) < 2:
        raise ValueError("At least two unique songs are required for a train/test split.")
    random.seed(random_state)
    np.random.seed(random_state)
    tf.keras.utils.set_random_seed(random_state)

    train_ids, test_ids = train_test_split(
        data.index, test_size=test_size, random_state=random_state, shuffle=True
    )
    targets, metadata = make_target_vectors(data, pd.Index(train_ids))
    train_embeddings = encode_descriptions(
        data, pd.Index(train_ids), encoder_name=encoder_name, batch_size=batch_size
    )
    model = build_model(train_embeddings.shape[1], targets.shape[1])
    model.compile(optimizer="adam", loss=cosine_similarity_loss)
    train_in_batches(
        model, train_embeddings, targets.loc[train_ids].to_numpy(),
        epochs=epochs, batch_size=batch_size, random_state=random_state,
    )
    del train_embeddings
    gc.collect()
    test_embeddings = encode_descriptions(
        data, pd.Index(test_ids), encoder_name=encoder_name, batch_size=batch_size
    )
    predictions = model.predict(test_embeddings, verbose=0)
    metrics, details = evaluate_retrieval(predictions, test_ids, targets.to_numpy(), targets.index)
    metrics["split"] = {
        "train_fraction": 1 - test_size, "test_fraction": test_size,
        "random_state": random_state, "n_train": int(len(train_ids)), "n_test": int(len(test_ids)),
    }
    metadata["encoder"] = encoder_name
    return model, targets, metadata, metrics, details


def persist_artifacts(
    model: Sequential, targets: pd.DataFrame, metadata: dict, metrics: dict,
    details: pd.DataFrame, *, write_database: bool,
) -> None:
    """Save the trained model, its catalogue vectors, and evaluation evidence."""
    metric_path, detail_path = save_evaluation_artifacts(metrics, details, MODULE_DIR / "evaluation_results")
    if write_database:
        engine = import_credentials()
        targets.to_sql("song_vector", engine, if_exists="replace", index=True, index_label="id")
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE song_vector ADD PRIMARY KEY (id)"))
        model.save(MODULE_DIR / "ml_vector_reduction.keras")
        with (MODULE_DIR / "model_metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
    else:
        print("Skipped model and database replacement (--no-write-db).")
    print(f"Saved evaluation metrics to {metric_path}")
    print(f"Saved query-level predictions to {detail_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and audit the song recommender.")
    parser.add_argument("--data-csv", help="Use a local CSV instead of acousticbrainz_data.")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--no-write-db", action="store_true", help="Do not replace the song_vector table.")
    args = parser.parse_args()
    data = load_song_data(args.data_csv)
    model, targets, metadata, metrics, details = train_and_evaluate(
        data, epochs=args.epochs, batch_size=args.batch_size, random_state=args.random_state,
    )
    persist_artifacts(model, targets, metadata, metrics, details, write_database=not args.no_write_db)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
