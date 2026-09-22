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

