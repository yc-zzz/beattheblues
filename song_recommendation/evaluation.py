"""Metrics for auditing song-description retrieval.

Each test description has exactly one relevant document: the song from which
the description was bootstrapped. ``evaluate_retrieval`` therefore reports
ordinary multi-class metrics for the top-ranked song and ranking metrics at
several cut-offs for the recommender use case.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping

import faiss
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

DEFAULT_K_VALUES = (1, 5, 10)
TEST_VECTOR_ARTIFACT_FILENAMES = {
    "true": "evaluation_true_test_vectors.npy",
    "model_predictions": "evaluation_model_predicted_test_vectors.npy",
    "top_retrieved": "evaluation_top_10_predicted_test_vectors.npy",
}


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """L2-normalise rows without producing NaNs for a zero vector."""
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, np.finfo(np.float32).eps)


def _as_builtin(value):
    return value.item() if isinstance(value, np.generic) else value


def evaluate_retrieval(
    predicted_vectors: np.ndarray,
    true_song_ids: Iterable[str],
    candidate_vectors: np.ndarray,
    candidate_song_ids: Iterable[str],
    k_values: Iterable[int] = DEFAULT_K_VALUES,
) -> tuple[dict, pd.DataFrame, np.ndarray]:
    """Evaluate held-out description queries against a song catalogue.

    The catalogue includes held-out songs, as production does: the model has
    not trained on a held-out description, but may retrieve its song record.
    """
    true_song_ids = np.asarray(list(true_song_ids), dtype=str)
    candidate_song_ids = np.asarray(list(candidate_song_ids), dtype=str)
    predicted_vectors = _normalise(predicted_vectors)
    # Keep the unnormalised catalogue vectors for downstream error analysis;
    # retrieval itself is performed on L2-normalised copies below.
    candidate_vectors = np.asarray(candidate_vectors, dtype=np.float32)
    if predicted_vectors.shape[0] != len(true_song_ids):
        raise ValueError("Each predicted vector must have one true song id.")
    if candidate_vectors.shape[0] != len(candidate_song_ids):
        raise ValueError("Each candidate vector must have one song id.")
    if not len(candidate_song_ids):
        raise ValueError("The candidate catalogue is empty.")
    if len(np.unique(candidate_song_ids)) != len(candidate_song_ids):
        raise ValueError("Candidate song ids must be unique for unambiguous evaluation.")

    k_values = tuple(sorted({int(k) for k in k_values if int(k) > 0}))
    if not k_values:
        raise ValueError("Provide at least one positive retrieval cut-off.")
    max_k = min(max(k_values), len(candidate_song_ids))
    normalised_candidate_vectors = _normalise(candidate_vectors)
    index = faiss.IndexFlatIP(normalised_candidate_vectors.shape[1])
    index.add(normalised_candidate_vectors)
    _, retrieved_indices = index.search(predicted_vectors, max_k)
    retrieved_ids = candidate_song_ids[retrieved_indices]
    matches = retrieved_ids == true_song_ids[:, None]
    found = matches.any(axis=1)
    ranks = np.where(found, matches.argmax(axis=1) + 1, np.nan)
    top_1_ids = retrieved_ids[:, 0]
    top_1_correct = top_1_ids == true_song_ids

    # A single-label multi-class problem makes micro P/R/F1 identical to
    # top-1 accuracy. Macro and weighted values are retained as diagnostics.
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        true_song_ids, top_1_ids, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        true_song_ids, top_1_ids, average="weighted", zero_division=0
    )
    accuracy = accuracy_score(true_song_ids, top_1_ids)
    metrics: dict[str, object] = {
        "n_queries": int(len(true_song_ids)),
        "n_candidates": int(len(candidate_song_ids)),
        "top_1": {
            "accuracy": float(accuracy), "micro_precision": float(accuracy),
            "micro_recall": float(accuracy), "micro_f1": float(accuracy),
            "macro_precision": float(macro_p), "macro_recall": float(macro_r),
            "macro_f1": float(macro_f1), "weighted_precision": float(weighted_p),
            "weighted_recall": float(weighted_r), "weighted_f1": float(weighted_f1),
        },
        "retrieval": {},
    }
    for k in k_values:
        effective_k = min(k, len(candidate_song_ids))
        hit = ranks <= effective_k
        recall = float(hit.mean())  # There is one relevant song per query.
        precision = float(hit.mean() / effective_k)
        f1 = float(2 * precision * recall / (precision + recall)) if recall else 0.0
        rank_at_k = np.where(hit, ranks, np.nan)
        reciprocal_rank = np.where(hit, 1.0 / ranks, 0.0)
        ndcg = np.where(hit, 1.0 / np.log2(ranks + 1), 0.0)
        metrics["retrieval"][f"@{k}"] = {
            "effective_k": int(effective_k), "hit_rate": recall, "recall": recall,
            "precision": precision, "f1": f1,
            "mrr": float(reciprocal_rank.mean()), "map": float(reciprocal_rank.mean()),
            "ndcg": float(ndcg.mean()),
            "mean_rank_when_hit": float(np.nanmean(rank_at_k)) if hit.any() else None,
        }
    details = pd.DataFrame({
        "true_song_id": true_song_ids, "top_1_song_id": top_1_ids,
        "top_1_correct": top_1_correct, f"rank_within_top_{max_k}": ranks,
    })
    for position in range(max_k):
        details[f"retrieved_{position + 1}_song_id"] = retrieved_ids[:, position]
    # The position axis mirrors retrieved_1_song_id through retrieved_10_song_id
    # in ``details``. On a catalogue smaller than ten songs it is shorter.
    return metrics, details, candidate_vectors[retrieved_indices]


def save_evaluation_artifacts(
    metrics: Mapping, query_details: pd.DataFrame, output_directory: str | Path
) -> tuple[Path, Path]:
    """Write a concise summary and a query-level audit trail."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    metrics_path = output_directory / "evaluation_metrics.json"
    details_path = output_directory / "evaluation_predictions.csv"
    with metrics_path.open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2, default=_as_builtin)
    query_details.to_csv(details_path, index=False)
    return metrics_path, details_path


def save_test_vector_artifacts(
    true_vectors: np.ndarray,
    model_predicted_vectors: np.ndarray,
    top_retrieved_vectors: np.ndarray,
    output_directory: str | Path,
) -> tuple[Path, Path, Path]:
    """Write aligned test-set vectors for offline evaluation diagnostics.

    ``true_vectors`` and ``model_predicted_vectors`` have shape
    ``(n_test, n_features)``. ``top_retrieved_vectors`` has shape
    ``(n_test, 10, n_features)`` for the normal production catalogue; its
    middle dimension is smaller only when fewer than ten candidates exist.
    Row order is the same as ``evaluation_predictions.csv``.
    """
    true_vectors = np.asarray(true_vectors, dtype=np.float32)
    model_predicted_vectors = np.asarray(model_predicted_vectors, dtype=np.float32)
    top_retrieved_vectors = np.asarray(top_retrieved_vectors, dtype=np.float32)
    if true_vectors.ndim != 2:
        raise ValueError("True test vectors must be a two-dimensional array.")
    if model_predicted_vectors.shape != true_vectors.shape:
        raise ValueError("Model-predicted and true test vectors must have the same shape.")
    if (
        top_retrieved_vectors.ndim != 3
        or top_retrieved_vectors.shape[0] != true_vectors.shape[0]
        or top_retrieved_vectors.shape[2] != true_vectors.shape[1]
    ):
        raise ValueError("Top retrieved test vectors must have shape (n_test, k, n_features).")

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    true_path = output_directory / TEST_VECTOR_ARTIFACT_FILENAMES["true"]
    model_predictions_path = output_directory / TEST_VECTOR_ARTIFACT_FILENAMES["model_predictions"]
    top_retrieved_path = output_directory / TEST_VECTOR_ARTIFACT_FILENAMES["top_retrieved"]
    np.save(true_path, true_vectors)
    np.save(model_predictions_path, model_predicted_vectors)
    np.save(top_retrieved_path, top_retrieved_vectors)
    return true_path, model_predictions_path, top_retrieved_path
