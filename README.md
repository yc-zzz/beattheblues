# beat [the blues𝄞](https://beattheblues.vercel.app/)
beat the blues𝄞 is a simple web app where you can escape the monotonous recommendation algorithm of major music platforms.
Simply search a word or phrase, about anything. Be it your feelings, the weather, or gibberish, and there will always be a song recommended to you!

## Deployment
Frontend: Vercel

Backend: Render

Database: Neon

This is a full stack web app that is deployed, and thus can be accessed through the web link. No need to run locally!
As the web services are free tier, the deployed backend may take up to 50 seconds to spin up. Please be patient with our website!

## ML Implementation (Documentation)

### Model Architecture
The model takes in a natural language input and outputs a relevant song that aims to match the input. Powering this recommendation is a three-tiered architecture: 
1) Embedding: Using HuggingFace's SentenceTransformers 'all-MiniLM-L6-v2' model, natural language queries were embedded into a 384D vector. 
2) Dimensionality Reduction: A multi-layer perceptron was trained to map the 384D vector onto a shared 72D latent space that contained the song metadata vectors. 
3) Retrieval: The vector with the highest cosine similarity as the model would be retrieved. 

### Training
In order to train the model, we bootstrapped song descriptions using the song metadata. Numeric features were binned to 5 groups, and the model would choose 1 of 2 adjectives within each bin to describe the song. For instance, if happy = 0.78, this fell within the (0.60, 0.80) bin, and would be classified as either "cheerful" or "upbeat". In so doing, these numeric features became ordinal categorical features. This had a few consequences: 

(a) The dimensionality of the song vectors would increase. Previously, these song vectors were in 28D space, but with each of the 11 numeric features now having 5 class, these song vectors now exist in the 72D space. The model would return softmax predictions for each class for each feature, and these would be concatenated together to form a 72D vector. 

(b) The objective function for the training of the model would have to change. 
- The project originally began with a simple cosine similarity baseline, but that ignored the vector's magnitude. To illustate the problem with ignoring magnitude, one would consider that a song with 'happy' = 0.2 and 'relaxed' = 0.3 to be quite different from a song with 'happy' = 0.6 and 'relaxed' = 0.9.
- This later changed into a multi-objective function: RMSE for the numeric variables, and cross-entropy loss for the categorical variables -- and with the binning of numeric variables, all variables were then trained on cross-entropy loss. 
- A problem with having binned numeric variables being trained on cross-entropy loss is that it ignores how these different classes have an inherent ordering within them. To account for this, these binned numeric variables was trained on CORAL ordinal loss, which predicts 4 boundaries P(Y > k), thereby ensuring monotonicity in the values. Using these threshold values, the probabilities for each class P(Y = k) can be computed -- this would then be the representation used for retrieval. 
- The final objective function (as of now) is a multi-objective loss function: It seeks to minimise L, which is the sum of CORAL ordinal loss across all binned numeric variables and the sum of all cross-entropy loss for all other variables (which are categorical). 

The model was split into a 80-20 train-test split, and evaluation was conducted solely on the test-set.  

### Results 
The model began with a 3.0% Recall@10, and eventually progressed to a high of 12.2% Recall@10. This means that if a song's descriptions are passed to our model, the correct song will appear within the top 10 recommendations 12.1% of the time -- given a original dataset of over 86,000 songs. There is no fixed benchmark for Recall@10 as the difficulty of the task increases with the number of rows (dense / sparse) and features (curse of dimensionality). 

As elucidated earlier, cosine similarity was deprioritised as a evaluation metric due to its singular focus on vector direction instead of magnitude. Nonetheless, cosine similarity performance did not take a hit even when cosine similarity was deprioritised. By converting each softmax head's probabilities into a weighted sum = sum(P(X = k) * bin_center), and using these numbers to compress the vector representation back to 28D, the expected top-1 cosine similarity was 0.93, which was almost the same as when the first experiment was conducted. 

There was a regression in Experiment 5 -- but as of writing, it has yet to be diagnosed, and fixes have yet to be implemented. 

### Future Work 
First, we have not created a validation set nor implemented hyperparameter tuning. This is an obvious omission that could lead to significantly better model performance. The main reason for this omission would be training time -- we figured it would be better to optimise the architecture before implementing hyperparameter tuning. 

Second, more experimentation would have to be done viz-a-viz the bootstrapping. Further finetuning the list of adjectives, number of bins, etc. is needed -- on one hand, more bins and descriptors means more semantic meaning captured, and on the other it makes the problem harder, since the problem moves from a coarse classification problem to a more fine-grained one. A trade-off has to be made here. 

Third, we would like to experiment with some model architecture changes. Some ideas that we would like to experiment with include having more layers in the intermediate neural network, and a two-tiered re-ranking system similar to RAG.

### Remarks 
This project originally began as a software engineering project. Its focus was to develop and deploy a user-facing software product with a number of features, not optimising recommendations. After taking a break, we decided to focus on evaluating and improving the performance of our model. 

These experiments were run via Google Cloud Run. 

## Running Experiments 
The outputs of @song_data_retrieval.py can be found via this link: https://drive.google.com/file/d/1eL04SZ5D0Op8t_WEChYwoTnfzIzMSlbe/view?usp=sharing. This was obtained via a public data dump on the AcousticBrainz website (https://data.metabrainz.org/pub/musicbrainz/acousticbrainz/dumps/acousticbrainz-highlevel-json-20220623/). 

Retrain with a reproducible 80/20 song split and evaluate the held-out
descriptions with:

```sh
python song_recommendation/train_ml.py --epochs 10
```

Each song receives four deterministic, feature-complete description templates after the split, so no song appears in both train and test data. This needs the
`NEON_CONNECTION_STRING` environment variable for the acousticbrainz database. It updates the model and `song_vector` catalogue, and writes the aggregate metrics and per-query ranks to `song_recommendation/evaluation_results/`. Use `--no-write-db` to run an audit without replacing the catalogue table, or `--data-csv path/to/data.csv` for a local dataset.

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

The first run for a particular generated train/test description set also
stores its SentenceTransformer outputs beneath
`embedding_cache/<fingerprint>/`. Later runs with the same descriptions,
split, seed, and encoder download those arrays and skip re-encoding. Changing
the template text, source data, split, seed, or encoder creates a new cache.

Rows are aligned with `evaluation_predictions.csv`; that file identifies the
true song and the song corresponding to each retrieved-vector position. You
may instead provide the bucket URI per run:

```sh
python song_recommendation/train_ml.py --epochs 10 \
  --gcs-bucket-uri gs://your-bucket-name/song-recommendation
```

To additionally calculate each held-out description's exact rank across the
entire evaluation catalogue and save full MRR, add `--compute-full-mrr`. The
calculation uses bounded query/candidate score tiles rather than allocating an
all-query-by-all-candidate matrix; it adds evaluation time, but writes
`full_rank` to `evaluation_predictions.csv` and `full_ranking.mrr` to the
metrics JSON.

The runtime needs Google Application Default Credentials with permission to
create objects in that bucket. For local training, set
`GOOGLE_APPLICATION_CREDENTIALS` to the path of a service-account JSON key; on
a GCP runtime, attach a service account with an object-writer role instead.
