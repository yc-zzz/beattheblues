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
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from dotenv import load_dotenv
from keras.layers import Concatenate, Dense, Input, LeakyReLU
from keras.models import Model
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sqlalchemy import text

try:  # Supports both ``python -m`` and direct execution.
    from song_recommendation.evaluation import (
        evaluate_retrieval, save_evaluation_artifacts, save_test_vector_artifacts,
    )
    from song_recommendation.gcs_artifacts import upload_artifacts
    from song_recommendation.model_utils import CombinedRetrievalLoss, import_credentials
except ModuleNotFoundError:
    from evaluation import evaluate_retrieval, save_evaluation_artifacts, save_test_vector_artifacts
    from gcs_artifacts import upload_artifacts
    from model_utils import CombinedRetrievalLoss, import_credentials


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
DESCRIPTION_TEMPLATES = (
    "{name} by {artist} ({year}) is a {timbre} {genre} track with a {happy} mood and a {sad} emotional shade. "
    "Its {dance} pulse meets {party} social energy, while the overall feel is {relaxed} and {aggressive}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}. "
    "The production balances {acoustic} and {electronic} textures with {tonal} harmony. "
    "Performance gender: {gender}. Vocal presence: {voice}.",
    "Looking for {genre} music? {name} by {artist} ({year}) offers a {happy}, {sad} atmosphere with {dance} movement and {party} appeal. "
    "Expect a {relaxed} yet {aggressive} character, combining {acoustic} and {electronic} elements, {timbre} colour, and {tonal} writing. "
    "Performance gender: {gender}. Vocal presence: {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
    "Analytically, {name} by {artist} ({year}) is a {genre} recording whose mood is {happy} and whose sadness is {sad}. "
    "Its energy is {dance}, {party}, {relaxed}, and {aggressive}; its arrangement is {acoustic}, {electronic}, {timbre}, and {tonal}. "
    "Performance gender: {gender}; vocal presence: {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
    "{name} by {artist} ({year}): a {timbre} {genre} song with {happy} mood and {sad} undertones; {dance} motion, {party} energy, {relaxed} pacing, and {aggressive} force; "
    "{acoustic} and {electronic} production, {tonal} harmony, performance gender {gender}, and vocal presence {voice}. "
    "Its MIREX vibe cluster is {mirex_cluster}: {mirex}.",
)
TEMPLATE_COUNT = len(DESCRIPTION_TEMPLATES)

# Adjacent ranges overlap so a score near a boundary can produce varied but
# still faithful language. Each tuple is ordered from zero to one.
VALUE_BINS = (
    (0.00, 0.15), (0.10, 0.25), (0.20, 0.35), (0.30, 0.45), (0.40, 0.55),
    (0.50, 0.65), (0.60, 0.75), (0.70, 0.85), (0.80, 0.95), (0.90, 1.00),
)
NUMERIC_LANGUAGE = {
    "dance": (
        ("still", "non-danceable"), ("unrhythmic", "reserved"), ("subtle", "light-footed"), ("gently grooving", "restrained"),
        ("moderately rhythmic", "easy-moving"), ("groove-friendly", "mobile"), ("danceable", "rhythmic"), ("floor-ready", "propulsive"),
        ("highly danceable", "kinetic"), ("irresistibly dance-driven", "club-ready", "ecstatic"),
    ),
    "acoustic": (
        ("synthetic", "non-acoustic"), ("processed", "machine-led"), ("mostly amplified", "lightly organic"), ("mixed-source", "partly acoustic"),
        ("balanced", "semi-acoustic"), ("warmly organic", "acoustic-leaning"), ("acoustic", "natural"), ("wooden", "intimate"),
        ("strongly acoustic", "unplugged"), ("entirely acoustic", "bare"),
    ),
    "aggressive": (
        ("gentle", "tender"), ("soft-spoken", "mild"), ("calm", "unforced"), ("restrained", "measured"),
        ("even-tempered", "balanced"), ("assertive", "energised"), ("forceful", "driven"), ("fierce", "hard-hitting"),
        ("intense", "confrontational"), ("ferocious", "maximal"),
    ),
    "electronic": (
        ("organic", "non-electronic"), ("natural", "unprocessed"), ("mostly organic", "lightly synthetic"), ("hybrid", "partly electronic"),
        ("balanced", "mixed-media"), ("electronically tinged", "synth-accented"), ("electronic", "synthetic"), ("synth-led", "digitised"),
        ("strongly electronic", "machine-textured"), ("fully electronic", "digital"),
    ),
    "happy": (
        ("deeply somber", "distinctly unhappy", "gloomy"), ("melancholic", "downcast", "bleak"), ("subdued", "low-spirited", "somewhat melancholy"),
        ("restrained", "slightly downbeat", "not especially cheerful"), ("emotionally neutral", "balanced"), ("mildly positive", "pleasant", "gently upbeat"),
        ("cheerful", "positive", "upbeat"), ("bright", "buoyant", "feel-good"), ("joyful", "uplifting", "sunny"), ("exuberant", "euphoric", "intensely joyful"),
    ),
    "party": (
        ("solitary", "inward-looking"), ("private", "low-key"), ("reserved", "uncelebratory"), ("casual", "gently social"),
        ("socially neutral", "easygoing"), ("gathering-friendly", "sociable"), ("party-ready", "celebratory"), ("festive", "crowd-pleasing"),
        ("high-spirited", "dancefloor-friendly"), ("full-on party", "celebration-driven"),
    ),
    "relaxed": (
        ("tense", "restless"), ("uneasy", "wired"), ("alert", "brisk"), ("slightly taut", "active"),
        ("even-paced", "neutral"), ("easygoing", "settled"), ("relaxed", "laid-back"), ("calm", "unhurried"),
        ("deeply relaxed", "soothing"), ("serene", "sleepy"),
    ),
    "sad": (
        ("joyful", "unsorrowful"), ("lighthearted", "hopeful"), ("only faintly sad", "bright-leaning"), ("slightly wistful", "reflective"),
        ("emotionally balanced", "neutral"), ("pensive", "mildly sad"), ("sad", "melancholy"), ("sorrowful", "yearning"),
        ("heartbroken", "deeply mournful"), ("devastated", "grief-stricken"),
    ),
    "timbre": (
        ("very dark", "shadowy"), ("dark", "muted"), ("dusky", "low-lit"), ("warm-dark", "soft-edged"),
        ("tonally balanced", "neutral"), ("gently bright", "clear"), ("bright", "shimmering"), ("luminous", "crisp"),
        ("brilliant", "sparkling"), ("blindingly bright", "radiant"),
    ),
    "tonal": (
        ("atonal", "dissonant"), ("harmonically unsettled", "angular"), ("loosely tonal", "ambiguous"), ("tonally flexible", "mixed-harmony"),
        ("moderately tonal", "balanced"), ("harmonically grounded", "consonant"), ("tonal", "melodically clear"), ("strongly tonal", "harmonically stable"),
        ("highly consonant", "melody-led"), ("unmistakably tonal", "resolute"),
    ),
    "voice": (
        ("instrumental", "voiceless"), ("nearly instrumental", "sparsely vocal"), ("lightly vocal", "voice-sparing"), ("partly vocal", "instrument-led"),
        ("balanced vocal-instrumental", "mixed-voice"), ("vocal-leaning", "sung"), ("vocal", "voice-forward"), ("prominently sung", "vocal-led"),
        ("strongly vocal", "voice-dominant"), ("entirely voice-centred", "vocally driven"),
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


def _numeric_term(value: float, column_name: str, *, random_state: int, song_id: str, template_id: int) -> str:
    """Select one semantically valid term from all overlapping value bins."""
    if not 0 <= value <= 1:
        raise ValueError(f"{column_name} must be between zero and one; received {value}.")
    terms = tuple(
        term for (lower, upper), bin_terms in zip(VALUE_BINS, NUMERIC_LANGUAGE[column_name])
        if lower <= value <= upper for term in bin_terms
    )
    if not terms:  # Defensive guard if the bin table is ever edited.
        raise ValueError(f"No language bin covers {column_name}={value}.")
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


def _feature_bin_indices(value: float) -> tuple[int, ...]:
    """Return every overlapping language bin that faithfully describes value."""
    return tuple(index for index, (lower, upper) in enumerate(VALUE_BINS) if lower <= value <= upper)


def _same_or_adjacent_bin(true_value: float, retrieved_value: float) -> bool:
    """Whether two values can be described by the same or adjacent bins."""
    true_bins = _feature_bin_indices(true_value)
    retrieved_bins = _feature_bin_indices(retrieved_value)
    return any(abs(true_bin - retrieved_bin) <= 1 for true_bin in true_bins for retrieved_bin in retrieved_bins)


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
            "true_year": int(true_song["year"]),
            "top_1_year": int(top_song["year"]),
            "year_difference": int(top_song["year"]) - int(true_song["year"]),
        }
        numeric_score = 0
        for column in NUMERIC_COLUMNS:
            true_value = float(true_song[column])
            top_value = float(top_song[column])
            correct = _same_or_adjacent_bin(true_value, top_value)
            row.update({
                f"{column}_true_value": true_value,
                f"{column}_top_1_value": top_value,
                f"{column}_true_bins": "|".join(map(str, _feature_bin_indices(true_value))),
                f"{column}_top_1_bins": "|".join(map(str, _feature_bin_indices(top_value))),
                f"{column}_same_or_adjacent": int(correct),
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


def build_model(input_dimensions: int, category_levels: dict[str, list[str]]) -> Model:
    """Build regression and categorical-softmax heads joined for retrieval."""
    inputs = Input(shape=(input_dimensions,), name="sentence_embedding")
    hidden = Dense(128)(inputs)
    hidden = LeakyReLU(negative_slope=0.1)(hidden)
    hidden = Dense(64, activation="relu")(hidden)

    # AcousticBrainz numeric features are bounded, while standardised year is
    # not.  Keep their output domains separate before joining the retrieval
    # representation in the established target-column order.
    numeric_features = Dense(len(NUMERIC_COLUMNS), activation="sigmoid", name="numeric_features")(hidden)
    year_standardised = Dense(1, name="year_standardised")(hidden)
    output_heads = [numeric_features, year_standardised]
    for column in CATEGORICAL_COLUMNS:
        levels = category_levels[column]
        if len(levels) < 2:
            raise ValueError(f"{column} needs at least two training categories for a softmax head.")
        output_heads.append(Dense(len(levels), activation="softmax", name=f"{column}_probabilities")(hidden))
    retrieval_vector = Concatenate(name="retrieval_vector")(output_heads)
    return Model(inputs=inputs, outputs=retrieval_vector, name="song_retrieval_multi_head")


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


def train_and_evaluate(
    data: pd.DataFrame,
    *,
    test_size: float = 0.2,
    random_state: int = 42,
    epochs: int = 10,
    batch_size: int = 32,
    encoder_name: str = DEFAULT_ENCODER,
) -> tuple[
    Model, pd.DataFrame, dict, dict, pd.DataFrame, np.ndarray, np.ndarray, np.ndarray, pd.DataFrame
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
    train_embeddings = encode_descriptions(
        train_descriptions, encoder_name=encoder_name, batch_size=batch_size
    )
    categorical_sizes = tuple(len(metadata["category_levels"][column]) for column in CATEGORICAL_COLUMNS)
    model = build_model(train_embeddings.shape[1], metadata["category_levels"])
    model.compile(
        optimizer="adam",
        loss=CombinedRetrievalLoss(
            numeric_size=len(NUMERIC_COLUMNS) + 1,
            categorical_sizes=categorical_sizes,
            lambda_numeric=1.0,
            lambda_categorical=1.0,
        ),
    )
    train_in_batches(
        model, train_embeddings, train_targets,
        epochs=epochs, batch_size=batch_size, random_state=random_state,
    )
    del train_embeddings
    gc.collect()
    test_embeddings = encode_descriptions(
        test_descriptions, encoder_name=encoder_name, batch_size=batch_size
    )
    predictions = model.predict(test_embeddings, verbose=0)
    # Experiment 3 deliberately uses a held-out-only candidate catalogue.
    # Training-song vectors therefore cannot be retrieved for test queries.
    test_candidate_vectors = targets.loc[test_song_ids]
    metrics, details, top_retrieved_vectors = evaluate_retrieval(
        predictions, test_description_song_ids,
        test_candidate_vectors.to_numpy(), test_candidate_vectors.index,
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
        "model_type": "numeric_mse_plus_categorical_cross_entropy",
        "loss_weights": {"numeric": 1.0, "categorical": 1.0},
        "candidate_catalogue": "test_only",
    })
    true_test_vectors = test_targets
    template_ids = np.tile(np.arange(TEMPLATE_COUNT, dtype=int), len(test_song_ids))
    manual_comparison = build_manual_song_description_comparison(
        data=data,
        true_song_ids=test_description_song_ids,
        true_descriptions=test_descriptions,
        template_ids=template_ids,
        details=details,
        random_state=random_state,
    )
    return (
        model, targets, metadata, metrics, details, true_test_vectors,
        predictions, top_retrieved_vectors, manual_comparison,
    )


def persist_artifacts(
    model: Model, targets: pd.DataFrame, metadata: dict, metrics: dict,
    details: pd.DataFrame, true_test_vectors: np.ndarray,
    model_predicted_vectors: np.ndarray, top_retrieved_vectors: np.ndarray,
    manual_comparison: pd.DataFrame,
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
    parser.add_argument("--no-write-db", action="store_true", help="Do not replace the song_vector table.")
    parser.add_argument(
        "--gcs-bucket-uri",
        default=os.getenv("GCS_BUCKET_URI"),
        help="GCS destination, e.g. gs://my-bucket/song-recommendation (or set GCS_BUCKET_URI).",
    )
    args = parser.parse_args()
    data = load_song_data(args.data_csv)
    (
        model, targets, metadata, metrics, details, true_test_vectors,
        model_predicted_vectors, top_retrieved_vectors, manual_comparison,
    ) = train_and_evaluate(
        data, epochs=args.epochs, batch_size=args.batch_size, random_state=args.random_state,
    )
    persist_artifacts(
        model, targets, metadata, metrics, details, true_test_vectors,
        model_predicted_vectors, top_retrieved_vectors, manual_comparison,
        write_database=not args.no_write_db, gcs_bucket_uri=args.gcs_bucket_uri,
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
