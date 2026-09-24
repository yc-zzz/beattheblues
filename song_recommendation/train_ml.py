"""Train and audit the text-description-to-song-vector model.

Run ``python song_recommendation/train_ml.py --epochs 10``. The model splits
songs 80/20 before generating four descriptions for every song, then retrieves
held-out descriptions only from the held-out song vectors.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from dotenv import load_dotenv
from keras.layers import Concatenate, Dense, Input
from keras.models import Model
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sqlalchemy import text

try:  # Supports both ``python -m`` and direct execution.
    from song_recommendation.evaluation import (
        evaluate_retrieval, save_evaluation_artifacts, save_test_vector_artifacts,
    )
    from song_recommendation.gcs_artifacts import (
        download_embedding_cache, upload_artifacts, upload_embedding_cache,
    )
    from song_recommendation.model_utils import (
        CoralOrdinalHead,
        CumulativeToClassProbabilities,
        EqualFeatureCoralCategoricalLoss,
        import_credentials,
    )
except ModuleNotFoundError:
    from evaluation import evaluate_retrieval, save_evaluation_artifacts, save_test_vector_artifacts
    from gcs_artifacts import download_embedding_cache, upload_artifacts, upload_embedding_cache
    from model_utils import (
        CoralOrdinalHead,
        CumulativeToClassProbabilities,
        EqualFeatureCoralCategoricalLoss,
        import_credentials,
    )


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_ENCODER = "all-MiniLM-L6-v2"
NUMERIC_COLUMNS = (
    "dance", "acoustic", "aggressive", "electronic", "happy", "party",
    "relaxed", "sad", "timbre", "tonal", "voice",
)
CATEGORICAL_COLUMNS = ("gender", "genre", "mirex")
GENRE_NAMES = {
    "blu": "blues", "cla": "classical", "cou": "country", "dis": "disco",
    "hip": "hip-hop", "jaz": "jazz", "met": "metal", "pop": "pop", "reg": "reggae",
    "roc": "rock",
}
MIREX_DESCRIPTIONS = {
    "cluster1": ("passionate", "rousing", "confident", "boisterous", "rowdy"),
    "cluster2": ("rollicking", "cheerful", "fun", "sweet", "amiable"),
    "cluster3": ("literate", "poignant", "wistful", "bittersweet", "autumnal", "brooding"),
    "cluster4": ("humorous", "silly", "campy", "quirky", "whimsical", "witty", "wry"),
    "cluster5": ("aggressive", "fiery", "anxious", "intense", "volatile", "visceral"),
}
FIXED_CATEGORY_LEVELS = {
    "gender": ("female", "male"),
    "genre": tuple(sorted(GENRE_NAMES)),
    "mirex": tuple(sorted(MIREX_DESCRIPTIONS)),
}
DESCRIPTION_TEMPLATES = (
    "{name} by {artist} ({year}) is a {timbre} {genre} track with a {happy} mood and a {sad} emotional shade. "
    "Sung by a {gender} vocalist."
    "Its {dance} pulse meets {party} social energy, while the overall feel is {relaxed} and {aggressive}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}. "
    "The production balances {acoustic} and {electronic} textures with {tonal} harmony and is {voice}. ",
    "Looking for {genre} music? {name} by {artist} ({year}) offers a {happy}, {sad} atmosphere with {dance} movement and {party} appeal. "
    "Expect a {relaxed} yet {aggressive} character sung by a {gender} vocalist, combining {acoustic} and {electronic} elements, {timbre} colour, {tonal} writing and a vocal presence that's {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
    "Analytically, {name} by {artist} ({year}) is a {genre} recording sung by a {gender} vocalist."
    "Its mood is {happy} and whose sadness is {sad}. "
    "Its energy is {dance}, {party}, {relaxed}, and {aggressive}; its arrangement is {acoustic}, {electronic}, {timbre}, {tonal}, {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
    "{name} by {artist} ({year}): Sung by a {gender} vocalist, a {timbre} {genre} song with {happy} mood and {sad} undertones; {dance} motion, {party} energy, {relaxed} pacing, and {aggressive} force; "
    "{acoustic} and {electronic} production, {tonal} harmony, performance gender {gender}, and vocal presence {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
)
TEMPLATE_COUNT = len(DESCRIPTION_TEMPLATES)
EMBEDDING_CACHE_SCHEMA_VERSION = 1
NUMERIC_BIN_COUNT = 8
# Bins are [0.000, 0.125), ..., [0.875, 1.000]. The final bin includes one.
NUMERIC_BIN_UPPER_BOUNDS = tuple(index / NUMERIC_BIN_COUNT for index in range(1, NUMERIC_BIN_COUNT))
NUMERIC_BIN_CENTERS = tuple((index + 0.5) / NUMERIC_BIN_COUNT for index in range(NUMERIC_BIN_COUNT))
NUMERIC_LANGUAGE = {
    "dance": (
        ("still", "non-danceable"), ("barely rhythmic", "reserved"),
        ("lightly rhythmic", "subtle"), ("gently grooving", "easy-moving"),
        ("moderately danceable", "rhythmic"), ("danceable", "floor-ready"),
        ("highly danceable", "propulsive"), ("club-driven", "irresistibly danceable"),
    ),
    "acoustic": (
        ("fully electronic", "synthetic"), ("strongly electronic", "machine-led"),
        ("mostly electronic", "processed"), ("slightly electronic", "hybrid"),
        ("mixed acoustic-electronic", "balanced"), ("slightly acoustic", "organic-leaning"),
        ("acoustic", "natural"), ("fully acoustic", "unplugged"),
    ),
    "aggressive": (
        ("gentle", "soft-spoken"), ("mild", "unforced"),
        ("restrained", "measured"), ("assertive", "driven"),
        ("forceful", "hard-hitting"), ("fierce", "confrontational"),
        ("intense", "volatile"), ("ferocious", "maximal"),
    ),
    "electronic": (
        ("acoustic", "organic"), ("strongly acoustic", "non-electronic"),
        ("mostly organic", "lightly synthetic"), ("slightly electronic", "hybrid"),
        ("mixed-media", "balanced"), ("electronic", "synth-accented"),
        ("strongly electronic", "synth-led"), ("fully electronic", "digital"),
    ),
    "happy": (
        ("deeply somber", "gloomy"), ("very unhappy", "bleak"),
        ("melancholic", "downcast"), ("mildly unhappy", "subdued"),
        ("mildly happy", "pleasant"), ("cheerful", "upbeat"),
        ("joyful", "buoyant"), ("euphoric", "exuberant"),
    ),
    "party": (
        ("solitary", "inward-looking"), ("private", "low-key"),
        ("reserved", "uncelebratory"), ("casual", "gently social"),
        ("sociable", "gathering-friendly"), ("party-ready", "festive"),
        ("celebratory", "crowd-pleasing"), ("dancefloor-ready", "full-on party"),
    ),
    "relaxed": (
        ("tense", "restless"), ("uneasy", "wired"),
        ("alert", "brisk"), ("slightly taut", "active"),
        ("even-paced", "balanced"), ("easygoing", "settled"),
        ("relaxed", "laid-back"), ("serene", "deeply soothing"),
    ),
    "sad": (
        ("joyful", "hopeful"), ("lighthearted", "bright"),
        ("only faintly sad", "reflective"), ("slightly wistful", "pensive"),
        ("mildly sad", "melancholy"), ("sorrowful", "yearning"),
        ("heartbroken", "deeply mournful"), ("devastated", "grief-stricken"),
    ),
    "timbre": (
        ("very dark", "shadowy"), ("dark", "muted"),
        ("dusky", "low-lit"), ("warm-dark", "soft-edged"),
        ("tonally balanced", "neutral"), ("gently bright", "clear"),
        ("bright", "shimmering"), ("brilliant", "sparkling"),
    ),
    "tonal": (
        ("atonal", "dissonant"), ("harmonically unsettled", "angular"),
        ("loosely tonal", "ambiguous"), ("tonally flexible", "mixed-harmony"),
        ("moderately tonal", "balanced"), ("harmonically grounded", "consonant"),
        ("tonal", "melodically clear"), ("highly consonant", "melody-led"),
    ),
    "voice": (
        ("instrumental", "voiceless"), ("nearly instrumental", "sparsely vocal"),
        ("lightly vocal", "voice-sparing"), ("partly vocal", "instrument-led"),
        ("balanced vocal-instrumental", "mixed-voice"), ("vocal-leaning", "sung"),
        ("vocal", "voice-forward"), ("vocal-led", "voice-dominant"),
    ),
}


def _stable_seed(random_state: int, song_id: str, template_id: int, column_name: str) -> int:
    """Derive a platform-independent random seed for one feature mention."""
    seed_input = f"{random_state}|{song_id}|{template_id}|{column_name}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(seed_input).digest()[:8], "big")


def _seeded_choice(
    values: tuple[str, ...], *, random_state: int, song_id: str, template_id: int, column_name: str
) -> str:
    return random.Random(_stable_seed(random_state, song_id, template_id, column_name)).choice(values)


def _numeric_bin_index(value: float) -> int:
    """Map a bounded numeric value to its one and only configured bin."""
    if not 0 <= value <= 1:
        raise ValueError(f"Numeric values must be between zero and one; received {value}.")
    # ``side='right'`` puts exact boundaries in the higher bin.
    return int(np.searchsorted(NUMERIC_BIN_UPPER_BOUNDS, value, side="right"))


def _canonical_category(value: object) -> str:
    """Normalise source labels to the lowercase fixed vector schema."""
    return str(value).strip().lower()


def _numeric_term(value: float, column_name: str, *, random_state: int, song_id: str, template_id: int) -> str:
    """Select one reproducible term from the value's exclusive language bin."""
    if column_name not in NUMERIC_LANGUAGE:
        raise ValueError(f"No language table exists for {column_name}.")
    bin_index = _numeric_bin_index(value)
    terms = NUMERIC_LANGUAGE[column_name][bin_index]
    return _seeded_choice(
        terms, random_state=random_state, song_id=song_id, template_id=template_id, column_name=column_name,
    )


def _description_context(song: pd.Series, *, random_state: int, template_id: int) -> dict[str, str]:
    song_id = str(song.name)
    context = {
        column: _numeric_term(float(song[column]), column, random_state=random_state, song_id=song_id, template_id=template_id)
        for column in NUMERIC_COLUMNS
    }
    context.update({
        "name": str(song["name"]), "artist": str(song["artist"]), "year": str(song["year"]),
        "gender": str(song["gender"]),
        "genre": GENRE_NAMES.get(str(song["genre"]).lower(), str(song["genre"])),
        "mirex_cluster": str(song["mirex"]),
        "mirex": ", ".join(
            MIREX_DESCRIPTIONS.get(str(song["mirex"]).lower(), (str(song["mirex"]),))
        ),
    })
    return context


def generate_description(song: pd.Series, *, random_state: int = 42, template_id: int = 0) -> str:
    """Create one reproducible, complete description for a song and template."""
    if not 0 <= template_id < TEMPLATE_COUNT:
        raise ValueError(f"template_id must be between 0 and {TEMPLATE_COUNT - 1}.")
    context = _description_context(song, random_state=random_state, template_id=template_id)
    description = DESCRIPTION_TEMPLATES[template_id].format(**context)
    required_mentions = [context[column] for column in (*NUMERIC_COLUMNS, *CATEGORICAL_COLUMNS)]
    missing = [term for term in required_mentions if term not in description]
    if missing:
        raise AssertionError(f"Description omitted feature terms: {missing}")
    return description


def generate_split_descriptions(
    data: pd.DataFrame, song_ids: pd.Index, *, random_state: int
) -> tuple[list[str], pd.Index]:
    """Generate four aligned descriptions for each song in one already-made split."""
    descriptions: list[str] = []
    description_song_ids: list[str] = []
    for song_id in pd.Index(song_ids).astype(str):
        song = data.loc[song_id]
        for template_id in range(TEMPLATE_COUNT):
            descriptions.append(generate_description(song, random_state=random_state, template_id=template_id))
            description_song_ids.append(song_id)
    generated_ids = pd.Index(description_song_ids, dtype=str)
    expected_ids = pd.Index(song_ids).astype(str)
    counts = generated_ids.value_counts().reindex(expected_ids, fill_value=0)
    if len(descriptions) != TEMPLATE_COUNT * len(expected_ids) or not (counts == TEMPLATE_COUNT).all():
        raise AssertionError("Every song in a split must generate exactly four descriptions.")
    return descriptions, generated_ids


def build_manual_song_description_comparison(
    *,
    data: pd.DataFrame,
    true_song_ids: pd.Index,
    true_descriptions: list[str],
    template_ids: np.ndarray,
    details: pd.DataFrame,
    random_state: int,
) -> pd.DataFrame:
    """Create the requested human-readable feature audit for top-1 retrievals."""
    if not (len(true_song_ids) == len(true_descriptions) == len(template_ids) == len(details)):
        raise ValueError("Manual comparison inputs must have one row per evaluated description.")
    if "top_1_song_id" not in details:
        raise ValueError("Retrieval details must include top_1_song_id.")

    rows = []
    for query_row, (true_id, true_description, template_id, top_id) in enumerate(zip(
        true_song_ids.astype(str), true_descriptions, template_ids, details["top_1_song_id"].astype(str),
    )):
        true_song = data.loc[true_id]
        top_song = data.loc[top_id]
        row = {
            "query_row": query_row,
            "template_id": int(template_id),
            "true_song_id": true_id,
            "true_description": true_description,
            "top_1_song_id": top_id,
            "top_1_description": generate_description(
                top_song, random_state=random_state, template_id=int(template_id)
            ),
        }
        numeric_score = 0
        for column in NUMERIC_COLUMNS:
            true_value = float(true_song[column])
            top_value = float(top_song[column])
            true_bin = _numeric_bin_index(true_value)
            top_bin = _numeric_bin_index(top_value)
            correct = true_bin == top_bin
            adjacent = abs(true_bin - top_bin) <= 1
            row.update({
                f"{column}_true_value": true_value,
                f"{column}_top_1_value": top_value,
                f"{column}_true_bin": true_bin,
                f"{column}_top_1_bin": top_bin,
                f"{column}_exact_bin_match": int(correct),
                f"{column}_adjacent_bin_hit": int(adjacent),
            })
            numeric_score += int(correct)
        categorical_score = 0
        for column in CATEGORICAL_COLUMNS:
            correct = str(true_song[column]) == str(top_song[column])
            row.update({
                f"{column}_true": str(true_song[column]),
                f"{column}_top_1": str(top_song[column]),
                f"{column}_exact_match": int(correct),
            })
            categorical_score += int(correct)
        row["numeric_feature_score"] = numeric_score
        row["categorical_feature_score"] = categorical_score
        row["feature_score_total"] = numeric_score + categorical_score
        row["feature_score_possible"] = len(NUMERIC_COLUMNS) + len(CATEGORICAL_COLUMNS)
        rows.append(row)
    return pd.DataFrame(rows)


def make_target_vectors(data: pd.DataFrame, train_ids: pd.Index) -> tuple[pd.DataFrame, dict]:
    """Build 105D targets: eight-bin numeric one-hots plus categoricals."""
    if train_ids.empty:
        raise ValueError("At least one training song is required to create target vectors.")
    numeric_blocks = []
    for column in NUMERIC_COLUMNS:
        values = data[column].astype(float).to_numpy()
        bin_indices = np.asarray([_numeric_bin_index(value) for value in values], dtype=int)
        encoded = np.zeros((len(data), NUMERIC_BIN_COUNT), dtype=np.float32)
        encoded[np.arange(len(data)), bin_indices] = 1.0
        numeric_blocks.append(pd.DataFrame(
            encoded,
            index=data.index,
            columns=[f"{column}_bin_{bin_index}" for bin_index in range(NUMERIC_BIN_COUNT)],
        ))
    vectors = pd.concat(numeric_blocks, axis=1)
    category_levels = {}
    for column in CATEGORICAL_COLUMNS:
        levels = list(FIXED_CATEGORY_LEVELS[column])
        canonical_values = data[column].map(_canonical_category)
        unexpected_levels = sorted(set(canonical_values) - set(levels))
        if unexpected_levels:
            raise ValueError(
                f"{column} contains values outside the fixed Experiment 5 schema: {unexpected_levels}."
            )
        category_levels[column] = levels
        encoded = pd.get_dummies(canonical_values, prefix=column, dtype=float)
        expected = [f"{column}_{level}" for level in levels]
        vectors = pd.concat([vectors, encoded.reindex(columns=expected, fill_value=0.0)], axis=1)
    vectors.index = data.index
    metadata = {
        "encoder": DEFAULT_ENCODER,
        "target_columns": vectors.columns.tolist(),
        "category_levels": category_levels,
        "numeric_columns": list(NUMERIC_COLUMNS),
        "numeric_bin_count": NUMERIC_BIN_COUNT,
        "numeric_bin_centers": list(NUMERIC_BIN_CENTERS),
        "year_in_target": False,
    }
    return vectors.astype(np.float32), metadata


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


def build_model(input_dimensions: int, category_levels: dict[str, list[str]]) -> Model:
    """Build a 105D retrieval vector from CORAL and categorical heads."""
    inputs = Input(shape=(input_dimensions,), name="sentence_embedding")
    # A shared trunk maps a 384D sentence embedding to fourteen semantic
    # decisions. Numeric heads are rank-consistent CORAL thresholds, converted
    # into class probabilities only for retrieval.
    hidden = Dense(256, activation="relu", name="shared_dense_256")(inputs)
    hidden = Dense(128, activation="relu", name="shared_dense_128")(hidden)

    cumulative_heads = [
        CoralOrdinalHead(NUMERIC_BIN_COUNT, name=f"{column}_coral_cumulative")(hidden)
        for column in NUMERIC_COLUMNS
    ]
    output_heads = [
        CumulativeToClassProbabilities(name=f"{column}_class_probabilities")(head)
        for column, head in zip(NUMERIC_COLUMNS, cumulative_heads)
    ]
    for column in CATEGORICAL_COLUMNS:
        levels = category_levels[column]
        if len(levels) < 2:
            raise ValueError(f"{column} needs at least two training categories for a softmax head.")
        output_heads.append(Dense(len(levels), activation="softmax", name=f"{column}_probabilities")(hidden))
    retrieval_vector = Concatenate(name="retrieval_vector")(output_heads)
    model = Model(inputs=inputs, outputs=retrieval_vector, name="song_retrieval_multi_head")
    expected_output_dimensions = NUMERIC_BIN_COUNT * len(NUMERIC_COLUMNS) + sum(
        len(category_levels[column]) for column in CATEGORICAL_COLUMNS
    )
    if model.output_shape[-1] != expected_output_dimensions:
        raise AssertionError("Retrieval model output does not match the target-vector layout.")
    return model


def build_cumulative_output_model(retrieval_model: Model) -> Model:
    """Expose the persisted model's 77D CORAL cumulative probabilities."""
    cumulative_heads = [
        retrieval_model.get_layer(f"{column}_coral_cumulative").output
        for column in NUMERIC_COLUMNS
    ]
    cumulative_vector = Concatenate(name="coral_cumulative_vector")(cumulative_heads)
    expected_dimensions = len(NUMERIC_COLUMNS) * (NUMERIC_BIN_COUNT - 1)
    if cumulative_vector.shape[-1] != expected_dimensions:
        raise AssertionError("CORAL cumulative output does not match numeric threshold layout.")
    return Model(retrieval_model.input, cumulative_vector, name="song_retrieval_cumulative_outputs")


def class_probabilities_to_expected_vectors(
    vectors: np.ndarray, *, category_levels: dict[str, list[str]], bin_centers: tuple[float, ...] = NUMERIC_BIN_CENTERS,
) -> np.ndarray:
    """Convert 105D retrieval vectors into 28D expected-value diagnostics."""
    vectors = np.asarray(vectors, dtype=np.float32)
    expected_width = len(NUMERIC_COLUMNS) * NUMERIC_BIN_COUNT + sum(
        len(category_levels[column]) for column in CATEGORICAL_COLUMNS
    )
    if vectors.shape[-1] != expected_width:
        raise ValueError(f"Expected {expected_width}D class probabilities; received {vectors.shape[-1]}D.")
    centers = np.asarray(bin_centers, dtype=np.float32)
    if centers.shape != (NUMERIC_BIN_COUNT,):
        raise ValueError(f"Expected {NUMERIC_BIN_COUNT} numeric bin centres; received shape {centers.shape}.")
    numeric_values = []
    start = 0
    for _ in NUMERIC_COLUMNS:
        stop = start + NUMERIC_BIN_COUNT
        numeric_values.append((vectors[..., start:stop] * centers).sum(axis=-1, keepdims=True))
        start = stop
    return np.concatenate((np.concatenate(numeric_values, axis=-1), vectors[..., start:]), axis=-1)


def class_probabilities_to_cumulative_vectors(vectors: np.ndarray) -> np.ndarray:
    """Derive the 77D CORAL threshold representation from 105D classes."""
    vectors = np.asarray(vectors, dtype=np.float32)
    expected_width = len(NUMERIC_COLUMNS) * NUMERIC_BIN_COUNT + sum(
        len(FIXED_CATEGORY_LEVELS[column]) for column in CATEGORICAL_COLUMNS
    )
    if vectors.shape[-1] != expected_width:
        raise ValueError(f"Expected {expected_width}D class probabilities; received {vectors.shape[-1]}D.")
    cumulative_blocks = []
    start = 0
    for _ in NUMERIC_COLUMNS:
        stop = start + NUMERIC_BIN_COUNT
        cumulative_blocks.append(np.cumsum(vectors[..., start:stop][..., ::-1], axis=-1)[..., ::-1][..., 1:])
        start = stop
    return np.concatenate(cumulative_blocks, axis=-1)


def _regression_metrics(true_values: np.ndarray, predicted_values: np.ndarray) -> dict[str, float | None]:
    """Return aggregate continuous diagnostics for aligned numeric matrices."""
    error = predicted_values - true_values
    total_sum_of_squares = np.square(true_values - true_values.mean(axis=0, keepdims=True)).sum()
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "bias_predicted_minus_true": float(error.mean()),
        "r_squared": float(1 - np.square(error).sum() / total_sum_of_squares) if total_sum_of_squares else None,
        "pearson_correlation": (
            float(np.corrcoef(true_values.ravel(), predicted_values.ravel())[0, 1])
            if np.std(true_values) and np.std(predicted_values) else None
        ),
    }


def _per_feature_regression_metrics(
    true_values: np.ndarray, predicted_values: np.ndarray,
) -> dict[str, dict[str, float | None]]:
    """Return continuous metrics separately for every Experiment 5 numeric feature."""
    if true_values.shape != predicted_values.shape or true_values.shape[-1] != len(NUMERIC_COLUMNS):
        raise ValueError("Per-feature numeric metrics require aligned matrices with one column per numeric feature.")
    return {
        column: _regression_metrics(true_values[:, index:index + 1], predicted_values[:, index:index + 1])
        for index, column in enumerate(NUMERIC_COLUMNS)
    }


def _mean_row_cosine(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float32)
    right = np.asarray(right, dtype=np.float32)
    left_norm = left / np.maximum(np.linalg.norm(left, axis=-1, keepdims=True), np.finfo(np.float32).eps)
    right_norm = right / np.maximum(np.linalg.norm(right, axis=-1, keepdims=True), np.finfo(np.float32).eps)
    return float(np.mean(np.sum(left_norm * right_norm, axis=-1)))


def train_in_batches(
    model: Model,
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
    descriptions: list[str], *, encoder_name: str, batch_size: int
) -> np.ndarray:
    """Encode one already-generated split at a time to limit memory use."""
    encoder = SentenceTransformer(encoder_name)
    embeddings = np.asarray(
        encoder.encode(descriptions, batch_size=batch_size, show_progress_bar=True), dtype=np.float32
    )
    del encoder
    gc.collect()
    return embeddings


def _sequence_digest(values: list[str] | pd.Index) -> str:
    """Hash an ordered sequence without constructing one very large string."""
    digest = hashlib.sha256()
    for value in values:
        encoded = str(value).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _embedding_cache_identity(
    *,
    train_descriptions: list[str],
    test_descriptions: list[str],
    train_description_song_ids: pd.Index,
    test_description_song_ids: pd.Index,
    encoder_name: str,
    random_state: int,
) -> tuple[str, dict[str, object]]:
    """Return a content-addressed cache key and the manifest fields to verify.

    Description text and its ordered song IDs are included rather than only a
    dataset filename. This makes a cache unusable if templates, split, seed,
    source rows, or their order change.
    """
    identity: dict[str, object] = {
        "schema_version": EMBEDDING_CACHE_SCHEMA_VERSION,
        "encoder_name": encoder_name,
        "random_state": random_state,
        "template_count": TEMPLATE_COUNT,
        "train_description_count": len(train_descriptions),
        "test_description_count": len(test_descriptions),
        "train_descriptions_sha256": _sequence_digest(train_descriptions),
        "test_descriptions_sha256": _sequence_digest(test_descriptions),
        "train_song_ids_sha256": _sequence_digest(train_description_song_ids),
        "test_song_ids_sha256": _sequence_digest(test_description_song_ids),
    }
    serialized_identity = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    cache_key = hashlib.sha256(serialized_identity.encode("utf-8")).hexdigest()
    return cache_key, identity


def _load_cached_embedding_array(
    path: Path, *, expected_rows: int, label: str,
) -> np.ndarray:
    """Load and validate one cache array before it reaches the model."""
    embeddings = np.load(path, allow_pickle=False)
    if embeddings.ndim != 2:
        raise ValueError(f"Cached {label} embeddings must be two-dimensional; got {embeddings.shape}.")
    if embeddings.shape[0] != expected_rows:
        raise ValueError(
            f"Cached {label} embeddings have {embeddings.shape[0]} rows; expected {expected_rows}."
        )
    if embeddings.dtype != np.float32:
        raise ValueError(f"Cached {label} embeddings must use float32; got {embeddings.dtype}.")
    if not np.isfinite(embeddings).all():
        raise ValueError(f"Cached {label} embeddings contain NaN or infinite values.")
    return embeddings


def get_embeddings(
    gcs_bucket_uri: str,
    *,
    train_descriptions: list[str],
    test_descriptions: list[str],
    train_description_song_ids: pd.Index,
    test_description_song_ids: pd.Index,
    encoder_name: str,
    batch_size: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Load compatible embeddings from GCS, or encode, store, and return them.

    The cache is content-addressed by the generated descriptions and their
    ordered song IDs. A cache can therefore be reused for model/loss/epoch
    changes, but not after changing text generation, split, data, or encoder.
    """
    cache_key, identity = _embedding_cache_identity(
        train_descriptions=train_descriptions,
        test_descriptions=test_descriptions,
        train_description_song_ids=train_description_song_ids,
        test_description_song_ids=test_description_song_ids,
        encoder_name=encoder_name,
        random_state=random_state,
    )
    with tempfile.TemporaryDirectory(prefix="song_embedding_cache_") as temporary_directory:
        cache_paths = download_embedding_cache(gcs_bucket_uri, cache_key, temporary_directory)
        if cache_paths is not None:
            with cache_paths["cache_manifest.json"].open(encoding="utf-8") as handle:
                cached_manifest = json.load(handle)
            mismatched_fields = [
                field for field, expected_value in identity.items()
                if cached_manifest.get(field) != expected_value
            ]
            if cached_manifest.get("cache_key") != cache_key or mismatched_fields:
                raise ValueError(
                    "Embedding cache manifest does not match this training run: "
                    f"{', '.join(mismatched_fields) or 'cache_key'}."
                )
            train_embeddings = _load_cached_embedding_array(
                cache_paths["train_embeddings.npy"],
                expected_rows=len(train_descriptions), label="train",
            )
            test_embeddings = _load_cached_embedding_array(
                cache_paths["test_embeddings.npy"],
                expected_rows=len(test_descriptions), label="test",
            )
            if train_embeddings.shape[1] != test_embeddings.shape[1]:
                raise ValueError("Cached train and test embeddings have different dimensions.")
            print(f"Loaded embedding cache {cache_key[:12]} from Google Cloud Storage.")
            return train_embeddings, test_embeddings, {
                "source": "gcs_cache", "cache_key": cache_key, "bucket_uri": gcs_bucket_uri,
            }

        print(f"No embedding cache found for {cache_key[:12]}; encoding descriptions and uploading it.")
        train_embeddings = encode_descriptions(
            train_descriptions, encoder_name=encoder_name, batch_size=batch_size,
        )
        test_embeddings = encode_descriptions(
            test_descriptions, encoder_name=encoder_name, batch_size=batch_size,
        )
        np.save(Path(temporary_directory) / "train_embeddings.npy", train_embeddings)
        np.save(Path(temporary_directory) / "test_embeddings.npy", test_embeddings)
        manifest = {
            **identity,
            "cache_key": cache_key,
            "train_embedding_shape": list(train_embeddings.shape),
            "test_embedding_shape": list(test_embeddings.shape),
            "embedding_dtype": str(train_embeddings.dtype),
        }
        manifest_path = Path(temporary_directory) / "cache_manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
        uploaded_uris = upload_embedding_cache(
            gcs_bucket_uri,
            cache_key,
            {
                "train_embeddings.npy": Path(temporary_directory) / "train_embeddings.npy",
                "test_embeddings.npy": Path(temporary_directory) / "test_embeddings.npy",
                "cache_manifest.json": manifest_path,
            },
        )
        print("Uploaded embedding cache to Google Cloud Storage:")
        for artifact_uri in uploaded_uris:
            print(f"  {artifact_uri}")
        return train_embeddings, test_embeddings, {
            "source": "generated_and_uploaded", "cache_key": cache_key, "bucket_uri": gcs_bucket_uri,
        }


def train_and_evaluate(
    data: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    epochs: int = 10,
    batch_size: int = 32,
    encoder_name: str = DEFAULT_ENCODER,
    gcs_bucket_uri: str | None = None,
    compute_full_mrr: bool = False,
) -> tuple[
    Model, pd.DataFrame, dict, dict, pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, pd.DataFrame, dict[str, np.ndarray]
]:
    """Fit on 80%, retrieve each held-out description against held-out songs."""
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
    train_song_ids, test_song_ids = pd.Index(train_ids), pd.Index(test_ids)
    overlap = train_song_ids.intersection(test_song_ids)
    if not overlap.empty:
        raise AssertionError("A song cannot appear in both the train and test splits.")
    targets, metadata = make_target_vectors(data, pd.Index(train_ids))
    train_descriptions, train_description_song_ids = generate_split_descriptions(
        data, train_song_ids, random_state=random_state
    )
    test_descriptions, test_description_song_ids = generate_split_descriptions(
        data, test_song_ids, random_state=random_state
    )
    if len(train_descriptions) != TEMPLATE_COUNT * len(train_song_ids):
        raise AssertionError("Train descriptions are not aligned with the train split.")
    if len(test_descriptions) != TEMPLATE_COUNT * len(test_song_ids):
        raise AssertionError("Test descriptions are not aligned with the test split.")
    train_targets = targets.loc[train_description_song_ids].to_numpy()
    test_targets = targets.loc[test_description_song_ids].to_numpy(dtype=np.float32)
    if len(train_descriptions) != len(train_targets) or len(test_descriptions) != len(test_targets):
        raise AssertionError("Each generated description must have exactly one target vector.")
    test_embeddings: np.ndarray | None = None
    if gcs_bucket_uri:
        train_embeddings, test_embeddings, embedding_cache = get_embeddings(
            gcs_bucket_uri,
            train_descriptions=train_descriptions,
            test_descriptions=test_descriptions,
            train_description_song_ids=train_description_song_ids,
            test_description_song_ids=test_description_song_ids,
            encoder_name=encoder_name,
            batch_size=batch_size,
            random_state=random_state,
        )
    else:
        print("No GCS bucket configured; encoding descriptions without an embedding cache.")
        train_embeddings = encode_descriptions(
            train_descriptions, encoder_name=encoder_name, batch_size=batch_size
        )
        embedding_cache = {"source": "disabled"}
    categorical_sizes = tuple(len(metadata["category_levels"][column]) for column in CATEGORICAL_COLUMNS)
    head_sizes = (NUMERIC_BIN_COUNT,) * len(NUMERIC_COLUMNS) + categorical_sizes
    if targets.shape[1] != sum(head_sizes):
        raise AssertionError("Target-vector width does not match the configured output heads.")
    model = build_model(train_embeddings.shape[1], metadata["category_levels"])
    model.compile(
        optimizer="adam",
        loss=EqualFeatureCoralCategoricalLoss(
            num_ordinal_features=len(NUMERIC_COLUMNS),
            ordinal_num_classes=NUMERIC_BIN_COUNT,
            categorical_sizes=categorical_sizes,
        ),
    )
    train_in_batches(
        model, train_embeddings, train_targets,
        epochs=epochs, batch_size=batch_size, random_state=random_state,
    )
    del train_embeddings
    gc.collect()
    if test_embeddings is None:
        test_embeddings = encode_descriptions(
            test_descriptions, encoder_name=encoder_name, batch_size=batch_size
        )
    predictions = model.predict(test_embeddings, verbose=0)
    cumulative_model = build_cumulative_output_model(model)
    cumulative_predictions = cumulative_model.predict(test_embeddings, verbose=0)
    if not np.allclose(
        class_probabilities_to_cumulative_vectors(predictions), cumulative_predictions, atol=1e-5,
    ):
        raise AssertionError("CORAL cumulative outputs do not round-trip through class probabilities.")
    # Experiment 5 deliberately uses a held-out-only candidate catalogue.
    # Training-song vectors therefore cannot be retrieved for test queries.
    test_candidate_vectors = targets.loc[test_song_ids]
    metrics, details, top_retrieved_vectors = evaluate_retrieval(
        predictions, test_description_song_ids,
        test_candidate_vectors.to_numpy(), test_candidate_vectors.index,
        calculate_full_mrr=compute_full_mrr,
    )
    metrics["split"] = {
        "train_fraction": 1 - test_size, "test_fraction": test_size,
        "random_state": random_state,
        "n_train_songs": int(len(train_song_ids)), "n_test_songs": int(len(test_song_ids)),
        "n_train_descriptions": int(len(train_descriptions)), "n_test_descriptions": int(len(test_descriptions)),
        "descriptions_per_song": TEMPLATE_COUNT,
        "candidate_catalogue": "test_only",
    }
    metadata.update({
        "encoder": encoder_name,
        "description_templates": TEMPLATE_COUNT,
        "model_type": "coral_numeric_plus_categorical_softmax_heads",
        "loss": "equal_feature_coral_categorical_loss",
        "head_sizes": list(head_sizes),
        "output_dimensions": int(sum(head_sizes)),
        "retrieval_representation": "105D class probabilities converted from CORAL numerics plus categorical softmax heads",
        "coral_thresholds_per_numeric_feature": NUMERIC_BIN_COUNT - 1,
        "coral_cumulative_dimensions": len(NUMERIC_COLUMNS) * (NUMERIC_BIN_COUNT - 1),
        "expected_value_dimensions": len(NUMERIC_COLUMNS) + sum(categorical_sizes),
        "representation_artifacts": {
            "retrieval_class_probabilities": "evaluation_*_vectors.npy (105D)",
            "coral_cumulative_numeric": "evaluation_*_cumulative_vectors.npy (77D)",
            "expected_value_with_categories": "evaluation_*_expected_vectors_28d.npy (28D)",
        },
        "candidate_catalogue": "test_only",
        "embedding_cache": embedding_cache,
    })
    true_test_vectors = test_targets
    true_cumulative_vectors = class_probabilities_to_cumulative_vectors(true_test_vectors)
    true_expected_vectors = class_probabilities_to_expected_vectors(
        true_test_vectors, category_levels=metadata["category_levels"],
    )
    model_expected_vectors = class_probabilities_to_expected_vectors(
        predictions, category_levels=metadata["category_levels"],
    )
    top_retrieved_expected_vectors = class_probabilities_to_expected_vectors(
        top_retrieved_vectors, category_levels=metadata["category_levels"],
    )
    true_raw_numeric = data.loc[test_description_song_ids, NUMERIC_COLUMNS].to_numpy(dtype=np.float32)
    top_1_raw_numeric = data.loc[details["top_1_song_id"].astype(str), NUMERIC_COLUMNS].to_numpy(dtype=np.float32)
    model_expected_numeric = model_expected_vectors[:, :len(NUMERIC_COLUMNS)]
    top_1_quantized_numeric = top_retrieved_expected_vectors[:, 0, :len(NUMERIC_COLUMNS)]
    oracle_quantized_numeric = true_expected_vectors[:, :len(NUMERIC_COLUMNS)]
    metrics["representation_metrics"] = {
        "retrieval_cosine_105d": {
            "mean_raw_model_to_true": _mean_row_cosine(predictions, true_test_vectors),
            "mean_top_1_retrieved_to_true": _mean_row_cosine(top_retrieved_vectors[:, 0, :], true_test_vectors),
        },
        "numeric_expected_value_28d": {
            "mean_cosine": {
                "direct_model_to_true": _mean_row_cosine(model_expected_vectors, true_expected_vectors),
                "top_1_retrieved_to_true": _mean_row_cosine(
                    top_retrieved_expected_vectors[:, 0, :], true_expected_vectors,
                ),
            },
            "direct_model": _regression_metrics(true_raw_numeric, model_expected_numeric),
            "top_1_retrieved_quantized": _regression_metrics(true_raw_numeric, top_1_quantized_numeric),
            "top_1_retrieved_raw_values": _regression_metrics(true_raw_numeric, top_1_raw_numeric),
            "oracle_quantization": _regression_metrics(true_raw_numeric, oracle_quantized_numeric),
            "per_feature": {
                "direct_model": _per_feature_regression_metrics(true_raw_numeric, model_expected_numeric),
                "top_1_retrieved_quantized": _per_feature_regression_metrics(
                    true_raw_numeric, top_1_quantized_numeric,
                ),
                "top_1_retrieved_raw_values": _per_feature_regression_metrics(true_raw_numeric, top_1_raw_numeric),
                "oracle_quantization": _per_feature_regression_metrics(true_raw_numeric, oracle_quantized_numeric),
            },
        },
    }
    template_ids = np.tile(np.arange(TEMPLATE_COUNT, dtype=int), len(test_song_ids))
    manual_comparison = build_manual_song_description_comparison(
        data=data,
        true_song_ids=test_description_song_ids,
        true_descriptions=test_descriptions,
        template_ids=template_ids,
        details=details,
        random_state=random_state,
    )
    representation_vectors = {
        "true_cumulative": true_cumulative_vectors,
        "model_cumulative": cumulative_predictions,
        "true_expected": true_expected_vectors,
        "model_expected": model_expected_vectors,
        "top_retrieved_expected": top_retrieved_expected_vectors,
    }
    return (
        model, targets, metadata, metrics, details, true_test_vectors,
        predictions, top_retrieved_vectors, manual_comparison, representation_vectors,
    )


def persist_artifacts(
    model: Model, targets: pd.DataFrame, metadata: dict, metrics: dict,
    details: pd.DataFrame, true_test_vectors: np.ndarray,
    model_predicted_vectors: np.ndarray, top_retrieved_vectors: np.ndarray,
    manual_comparison: pd.DataFrame,
    representation_vectors: dict[str, np.ndarray],
    *, write_database: bool,
    gcs_bucket_uri: str | None = None,
) -> None:
    """Save the trained model, its catalogue vectors, and evaluation evidence."""
    metric_path, detail_path = save_evaluation_artifacts(metrics, details, MODULE_DIR / "evaluation_results")
    vector_paths = save_test_vector_artifacts(
        true_test_vectors, model_predicted_vectors, top_retrieved_vectors,
        MODULE_DIR / "evaluation_results",
    )
    manual_comparison_path = metric_path.parent / "manual_top_1_song_description_comparison.csv"
    manual_comparison.to_csv(manual_comparison_path, index=False)
    artifact_paths = [metric_path, detail_path, *vector_paths, manual_comparison_path]
    representation_filenames = {
        "true_cumulative": "evaluation_true_test_cumulative_vectors.npy",
        "model_cumulative": "evaluation_model_predicted_test_cumulative_vectors.npy",
        "true_expected": "evaluation_true_test_expected_vectors_28d.npy",
        "model_expected": "evaluation_model_predicted_test_expected_vectors_28d.npy",
        "top_retrieved_expected": "evaluation_top_10_predicted_test_expected_vectors_28d.npy",
    }
    if set(representation_vectors) != set(representation_filenames):
        raise ValueError("Experiment 5 representation artifacts are incomplete.")
    for representation_name, filename in representation_filenames.items():
        representation_path = metric_path.parent / filename
        np.save(representation_path, np.asarray(representation_vectors[representation_name], dtype=np.float32))
        artifact_paths.append(representation_path)
    if write_database:
        engine = import_credentials()
        targets.to_sql("song_vector", engine, if_exists="replace", index=True, index_label="id")
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE song_vector ADD PRIMARY KEY (id)"))
    else:
        print("Skipped song_vector replacement (--no-write-db).")
    model_path = MODULE_DIR / "ml_vector_reduction.keras"
    metadata_path = MODULE_DIR / "model_metadata.json"
    model.save(model_path)
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
    artifact_paths.extend((model_path, metadata_path))
    print(f"Saved evaluation metrics to {metric_path}")
    print(f"Saved query-level predictions to {detail_path}")
    print(f"Saved true and predicted test vectors to {metric_path.parent}")
    print("Saved CORAL cumulative and 28D expected-value evaluation vectors.")
    print(f"Saved manual top-1 comparison to {manual_comparison_path}")
    if gcs_bucket_uri:
        uploaded_uris = upload_artifacts(gcs_bucket_uri, artifact_paths)
        print("Uploaded artifacts to Google Cloud Storage:")
        for artifact_uri in uploaded_uris:
            print(f"  {artifact_uri}")


def main() -> None:
    # Load GCS configuration and Application Default Credential settings before
    # argparse reads the environment-backed default below.
    load_dotenv()
    parser = argparse.ArgumentParser(description="Train and audit the song recommender.")
    parser.add_argument("--data-csv", help="Use a local CSV instead of acousticbrainz_data.")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--compute-full-mrr",
        action="store_true",
        help=(
            "Compute exact full-catalogue ranks and MRR in bounded batches. "
            "This adds evaluation time but does not allocate a full score matrix."
        ),
    )
    parser.add_argument("--no-write-db", action="store_true", help="Do not replace the song_vector table.")
    parser.add_argument(
        "--gcs-bucket-uri",
        default=os.getenv("GCS_BUCKET_URI"),
        help=(
            "GCS artifact destination and embedding-cache root, e.g. "
            "gs://my-bucket/song-recommendation (or set GCS_BUCKET_URI)."
        ),
    )
    args = parser.parse_args()
    data = load_song_data(args.data_csv)
    (
        model, targets, metadata, metrics, details, true_test_vectors,
        model_predicted_vectors, top_retrieved_vectors, manual_comparison, representation_vectors,
    ) = train_and_evaluate(
        data, epochs=args.epochs, batch_size=args.batch_size, random_state=args.random_state,
        gcs_bucket_uri=args.gcs_bucket_uri, compute_full_mrr=args.compute_full_mrr,
    )
    persist_artifacts(
        model, targets, metadata, metrics, details, true_test_vectors,
        model_predicted_vectors, top_retrieved_vectors, manual_comparison, representation_vectors,
        write_database=not args.no_write_db, gcs_bucket_uri=args.gcs_bucket_uri,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
