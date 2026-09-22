# beat [the blues𝄞](https://beattheblues.vercel.app/)
beat the blues𝄞 is a simple web app where you can escape the monotonous recommendation algorithm of major music platforms.
Simply search a word or phrase, about anything. Be it your feelings, the weather, or gibberish, and there will always be a song recommended to you!

## Deployment
Frontend: Vercel

Backend: Render

Database: Neon

This is a full stack web app that is deployed, and thus can be accessed through the web link. No need to run locally!
As the web services are free tier, the deployed backend may take up to 50 seconds to spin up. Please be patient with our website!

## Recommendation-model audit

Retrain with a reproducible 80/20 song split and evaluate the held-out
bootstrapped descriptions with:

```sh
python song_recommendation/train_ml.py --epochs 10
```

This needs the `NEON_CONNECTION_STRING` environment variable for the
acousticbrainz database. It updates the model and
`song_vector` catalogue, and writes the aggregate metrics and per-query ranks
to `song_recommendation/evaluation_results/`. Use `--no-write-db` to run an
audit without replacing the catalogue table, or `--data-csv path/to/data.csv`
for a local dataset.

### Store model artifacts in Google Cloud Storage

Put the bucket URI (not the Google Cloud Console URL) in the environment where
you run training, for example in the root `.env` file:

```dotenv
GCS_BUCKET_URI=gs://your-bucket-name/song-recommendation
```

The optional path after the bucket name is the object prefix. Every training
run uploads the trained `.keras` model, its metadata, evaluation metrics,
query-level evaluation CSV, and the following aligned NumPy evaluation
artifacts to that location, including when `--no-write-db` is used:

- `evaluation_true_test_vectors.npy`: answer-key target vectors, shape `(n_test, n_features)`.
- `evaluation_model_predicted_test_vectors.npy`: raw model outputs, shape `(n_test, n_features)`.
- `evaluation_top_10_predicted_test_vectors.npy`: the target vectors of the ten
  highest-ranked retrieved songs, shape `(n_test, 10, n_features)`.

Rows are aligned with `evaluation_predictions.csv`; that file identifies the
true song and the song corresponding to each retrieved-vector position. You
may instead provide the bucket URI per run:

```sh
python song_recommendation/train_ml.py --epochs 10 \
  --gcs-bucket-uri gs://your-bucket-name/song-recommendation
```

The runtime needs Google Application Default Credentials with permission to
create objects in that bucket. For local training, set
`GOOGLE_APPLICATION_CREDENTIALS` to the path of a service-account JSON key; on
a GCP runtime, attach a service account with an object-writer role instead.

