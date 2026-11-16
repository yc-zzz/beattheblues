# Deploying the recommendation API to Google Cloud Run

This guide moves the **recommendation API** (`master_app.py`: `/search`,
`/recommend` and `/personality`, which used to be the `beattheblues-reco`
service on Render) to Google Cloud Run. It assumes you have never used Google
Cloud before. Every step says what it does and why it matters.

Commands are written for **Windows PowerShell**. They also work in macOS or
Linux terminals if you change the line-continuation character from a backtick
(`` ` ``) to a backslash (`\`).

## Contents

1. [How the pieces fit together](#1-how-the-pieces-fit-together)
2. [What it costs](#2-what-it-costs)
3. [Install the gcloud CLI](#3-install-the-gcloud-cli)
4. [Create a project, billing and a budget alert](#4-create-a-project-billing-and-a-budget-alert)
5. [Turn on the services we use](#5-turn-on-the-services-we-use)
6. [Choose a region](#6-choose-a-region)
7. [Put the model files in place and check they match the database](#7-put-the-model-files-in-place-and-check-they-match-the-database)
8. [Store the secrets](#8-store-the-secrets)
9. [Create a service account for the API](#9-create-a-service-account-for-the-api)
10. [Build the container image](#10-build-the-container-image)
11. [Deploy to Cloud Run](#11-deploy-to-cloud-run)
12. [Test it](#12-test-it)
13. [Point the Vercel frontend at the new URL](#13-point-the-vercel-frontend-at-the-new-url)
14. [Day-to-day: redeploying, logs, shutting down Render](#14-day-to-day-redeploying-logs-shutting-down-render)
15. [Optional: move the accounts backend too](#15-optional-move-the-accounts-backend-too)
16. [Troubleshooting](#16-troubleshooting)

---

## 1. How the pieces fit together

```
Browser ──> Vercel (my-frontend, React)
              │
              ├──> my-backend (Node/Express)        accounts, playlists, random song
              │        └──> Neon Postgres
              │
              └──> Cloud Run: reco-api (Flask)      search, recommend, personality
                       ├──> Neon Postgres           song_vector, acousticbrainz_data
                       ├──> model files baked into the image
                       └──> OpenAI API              personality description only
```

Words you will meet:

- **Container image**: a packaged copy of the app together with Python, every
  library, and the trained model, so it runs the same everywhere. It is
  described by `deploy/reco-api.Dockerfile`.
- **Cloud Build**: Google's machines that build the image for you, so your
  laptop does not have to download several GB of TensorFlow and PyTorch.
- **Artifact Registry**: where the built image is stored.
- **Cloud Run**: runs the image when a request arrives, and shuts it down
  when nobody is using it. You pay only while it is handling requests.
- **Secret Manager**: stores passwords (the Neon connection string, the
  OpenAI key) so they are never in the code or the image.
- **Service account**: a robot user that the running app logs in as. We give
  it permission to read the secrets and nothing else.

### What the server needs, and what it does not

I checked this against the code (`song_recommendation/predict_ml.py`):

| File from the model bucket | Needed by the server? |
|---|---|
| `ml_vector_reduction.keras` | **Yes.** The trained model. |
| `model_metadata.json` | **Yes.** Tells the server which sentence encoder the model was trained with. |
| `embedding_cache/` (both folders) | **No.** Training only. It saves re-encoding descriptions between training runs. |
| `evaluation_*` and `manual_*` files | **No.** Training reports for reading, never loaded by the server. |

The server also needs two database tables in Neon: `song_vector` (one vector
per song, written by training) and `acousticbrainz_data` (song names and
artists).

## 2. What it costs

Short version: for a prototype with light traffic, **about $0 to $0.30 a month**.

Cloud Run has a free allowance every month, on any paid billing account
([source](https://cloud.google.com/run/pricing)):

- 180,000 vCPU-seconds, 360,000 GiB-seconds of memory, 2 million requests.
- We run 1 vCPU and 2 GiB of memory, so the memory allowance runs out first:
  360,000 / 2 = 180,000 seconds, which is **about 50 hours of active request
  time per month**. You are billed only while a request is being handled (and
  while the container starts), not while it sits idle.

Other free allowances we use
([source](https://docs.cloud.google.com/free/docs/free-cloud-features)):
Cloud Build 2,500 build-minutes a month, Secret Manager 6 secret versions,
Artifact Registry 0.5 GB of storage.

The one thing that will probably cost a little: the image is roughly 2 to 3 GB
(TensorFlow is large), which is over the 0.5 GB free storage. Artifact Registry
storage is about $0.10 per GB a month, so expect about $0.20 to $0.30 a month.
Step 10 sets up automatic deletion of old images so this does not grow.

### "The free trial only lasts 90 days. Won't this stop working?"

No, as long as you **upgrade to a paid billing account**. The $300 trial is
separate from the always-free allowances above. Google's FAQ says that when
you upgrade, "you continue to have access to the Free Tier". If you do not
upgrade, your projects are shut down when the trial ends.

Upgrading does not mean you will be charged, only that charges above the free
allowances would go to your card. That is why Step 4 sets a **budget alert**,
and Step 11 caps the service at **one instance**, so a traffic spike cannot run
up a large bill.

## 3. Install the gcloud CLI

`gcloud` is the command-line tool for Google Cloud. Every step below uses it.

1. Download and run the Windows installer from
   <https://cloud.google.com/sdk/docs/install>. Keep the default options.
2. Open a **new** PowerShell window (so it picks up the new program) and run:

   ```powershell
   gcloud init
   ```

   This opens a browser to log in with your Google account, then asks which
   project to use. Choose **Create a new project** if asked, or skip it and do
   Step 4 first.

3. Also log in for "application default credentials". Some tools use this
   second login, so doing it now avoids confusing errors later:

   ```powershell
   gcloud auth application-default login
   ```

## 4. Create a project, billing and a budget alert

A **project** is a container for everything you create in Google Cloud. It
keeps this app's resources and bills separate from anything else.

1. Pick a project ID. It must be unique across all of Google Cloud, lowercase,
   for example `beattheblues-yc`. Save it in a PowerShell variable so you can
   paste the later commands unchanged:

   ```powershell
   $PROJECT_ID = "beattheblues-yc"   # change this to your own ID
   gcloud projects create $PROJECT_ID --name="beattheblues"
   gcloud config set project $PROJECT_ID
   ```

   PowerShell variables disappear when you close the window. If you open a new
   one later, run the `$PROJECT_ID = ...` line (and `$REGION` from Step 6)
   again.

2. **Link billing.** Cloud Run needs a billing account even for free usage.
   Open <https://console.cloud.google.com/billing/linkedaccount>, make sure
   your new project is selected at the top, and link your billing account
   (create one if you have none; this is where the free trial starts).

3. **Set a budget alert.** This emails you if spending passes an amount you
   choose. Open <https://console.cloud.google.com/billing/budgets>, click
   **Create budget**, then:
   - Scope: your `beattheblues` project.
   - Amount: a specified amount, for example **$5**.
   - Alert thresholds: keep 50%, 90%, 100%.
   - Tick "Email alerts to billing admins and users".

   Important: a budget alert only *warns* you. It does not stop spending. The
   real protection is the instance cap in Step 11.

4. (When the trial ends, or now if you prefer) upgrade to a paid account from
   the banner at the top of the console, or from
   <https://console.cloud.google.com/billing>.

## 5. Turn on the services we use

Google Cloud services are switched off in a new project until you enable them.

```powershell
gcloud services enable run.googleapis.com cloudbuild.googleapis.com `
  artifactregistry.googleapis.com secretmanager.googleapis.com
```

This takes a minute or two.

## 6. Choose a region

The region is the data centre the API runs in. Choose one **close to your Neon
database**, because every recommendation queries the database, and a long
distance adds delay to each query.

1. Open your Neon project, go to **Connection details**, and look at the host
   name. It contains the region, for example
   `ep-cool-name-123456.ap-southeast-1.aws.neon.tech` is in `ap-southeast-1`.
2. Pick the matching Cloud Run region:

   | Neon region (in the host name) | Cloud Run region |
   |---|---|
   | `us-east-1`, `us-east-2` | `us-east1` |
   | `us-west-2` | `us-west1` |
   | `eu-central-1` | `europe-west3` |
   | `ap-southeast-1` (Singapore) | `asia-southeast1` |
   | `ap-southeast-2` (Sydney) | `australia-southeast1` |

3. Save it:

   ```powershell
   $REGION = "asia-southeast1"   # change to match your Neon region
   gcloud config set run/region $REGION
   ```

The free allowance is the same in every region; `asia-southeast1` just costs a
little more per second once you go over it.

## 7. Put the model files in place and check they match the database

The model is not stored in git (it is too large and changes with every
training run). The image build copies it from your local repo folder instead.

1. Copy these two files from where you downloaded the bucket into
   `song_recommendation/` in your repo:

   ```
   song_recommendation/ml_vector_reduction.keras
   song_recommendation/model_metadata.json
   ```

   Do not copy `embedding_cache/` or the `evaluation_*` files. They are not
   used by the server and would only make the upload slower.

   Git ignores both files on purpose (`*.keras` and `*.json` in `.gitignore`),
   so they will not be committed by accident. The `.gcloudignore` file is what
   makes sure they *are* uploaded to Cloud Build.

2. **Check the model and the database come from the same training run.** The
   model outputs a vector of some length, and every row of the `song_vector`
   table must have the same length, because the server compares them directly.
   Training writes both, but a run with `--no-write-db` updates only the model.

   - Open `model_metadata.json` and find `"output_dimensions"` (for example 72).
   - In the Neon console, open the **SQL Editor** and run:

     ```sql
     SELECT count(*) - 1 AS vector_columns
     FROM information_schema.columns
     WHERE table_name = 'song_vector';
     ```

     (`- 1` skips the `id` column.)

   The two numbers must be equal. If they are not, the server will start, but
   `/recommend` returns a clear error saying they do not match. The fix is to
   use the model from the training run that last wrote `song_vector`, or to
   rerun training without `--no-write-db`.

## 8. Store the secrets

The app needs two passwords. We keep them in Secret Manager so they never
appear in the code, the image, or the deploy command.

1. **Neon connection string.** In Neon, open **Connection details**, choose
   the database that holds `song_vector`, and copy the connection string. It
   looks like `postgresql://user:password@ep-...neon.tech/neondb?sslmode=require`.

   Write it to a temporary file *without* a trailing newline (a hidden newline
   at the end would break the connection), store it, then delete the file:

   ```powershell
   "postgresql://PASTE-YOUR-STRING-HERE" | Out-File -NoNewline -Encoding ascii neon.txt
   gcloud secrets create neon-connection-string --data-file=neon.txt
   Remove-Item neon.txt
   ```

2. **OpenAI API key** (used only by the personality test). If you do not have
   one, skip this. Everything except the personality description still works.

   ```powershell
   "sk-PASTE-YOUR-KEY-HERE" | Out-File -NoNewline -Encoding ascii openai.txt
   gcloud secrets create openai-api-key --data-file=openai.txt
   Remove-Item openai.txt
   ```

The search and personality code used to read four separate variables
(`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`). They now fall back to
`NEON_CONNECTION_STRING`, so this one secret covers all three features. This
assumes all three use the same Neon database, which is how Render was set up.

## 9. Create a service account for the API

Without this, Cloud Run would run the app as the project's default account,
which can change almost anything in the project. A dedicated account that can
only read its two secrets limits the damage if the app were ever compromised.
This is the "least privilege" habit.

```powershell
gcloud iam service-accounts create reco-api --display-name="beattheblues reco API"
$SA = "reco-api@$PROJECT_ID.iam.gserviceaccount.com"

gcloud secrets add-iam-policy-binding neon-connection-string `
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

# Only if you created the OpenAI secret:
gcloud secrets add-iam-policy-binding openai-api-key `
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

## 10. Build the container image

1. Create a repository in Artifact Registry to hold the image:

   ```powershell
   gcloud artifacts repositories create beattheblues `
     --repository-format=docker --location=$REGION
   ```

2. Keep only the two newest images, so storage cost does not grow with every
   deploy. Create a file called `cleanup-policy.json` (anywhere, not in the
   repo) containing:

   ```json
   [
     {"name": "keep-latest-2", "action": {"type": "Keep"},
      "mostRecentVersions": {"keepCount": 2}},
     {"name": "delete-older", "action": {"type": "Delete"},
      "condition": {"tagState": "any"}}
   ]
   ```

   Then apply it:

   ```powershell
   gcloud artifacts repositories set-cleanup-policies beattheblues `
     --location=$REGION --policy=cleanup-policy.json --no-dry-run
   ```

3. From the **root of the repo** (the folder with `master_app.py`), build:

   ```powershell
   $IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/beattheblues/reco-api"
   gcloud builds submit --config deploy/cloudbuild.reco-api.yaml `
     --substitutions="_IMAGE=$IMAGE"
   ```

   This uploads the repo (minus what `.gcloudignore` excludes, including your
   `.env`) and builds the image on Google's machines. It takes about 10 to 15
   minutes the first time. Your laptop only uploads a few MB plus the model.

   If it stops with `Missing song_recommendation/ml_vector_reduction.keras`,
   Step 7 was skipped.

Why not `gcloud run deploy --source .`? That shortcut only builds a file
named `Dockerfile` at the repo root, and that file is the *training* job image.
The recipe in `deploy/cloudbuild.reco-api.yaml` builds the server image
instead, so the two do not get in each other's way.

## 11. Deploy to Cloud Run

```powershell
gcloud run deploy beattheblues-reco `
  --image=$IMAGE `
  --region=$REGION `
  --service-account=$SA `
  --set-secrets="NEON_CONNECTION_STRING=neon-connection-string:latest,API_KEY=openai-api-key:latest" `
  --memory=2Gi --cpu=1 --cpu-boost `
  --concurrency=8 --min-instances=0 --max-instances=1 `
  --timeout=300 `
  --allow-unauthenticated
```

(If you skipped the OpenAI secret, remove `,API_KEY=openai-api-key:latest`.)

What each setting does, and why:

| Setting | Why |
|---|---|
| `--memory=2Gi --cpu=1` | TensorFlow, PyTorch, the sentence encoder and the song vectors need roughly 1.5 GB together. 2 GiB leaves headroom. Cloud Run's default (512 MiB) would crash. |
| `--cpu-boost` | Gives extra CPU while the container starts, which shortens cold starts. |
| `--concurrency=8` | Up to 8 requests at once per instance, matching the 8 gunicorn threads in the image. |
| `--min-instances=0` | Shuts down when idle, so you pay nothing between visits. The cost: the first request after a quiet spell waits for a **cold start** (see below). |
| `--max-instances=1` | Never more than one copy. This is your hard cost cap, and it also keeps the "same query gives the next song" behaviour consistent, because that state lives in one process's memory. |
| `--timeout=300` | The first `/recommend` after a cold start loads the model, which can take a while. 5 minutes is generous. |
| `--allow-unauthenticated` | The API is called directly from visitors' browsers, so it must be public, just like on Render. |
| `--set-secrets` | Passes each secret to the app as an environment variable at start-up. |

**About cold starts.** After about 15 minutes with no traffic, Cloud Run shuts
the instance down. The next visitor waits for it to start again, and the first
`/recommend` also loads the model and song vectors. Expect the first
recommendation to take roughly 20 to 60 seconds, and later ones a second or
two. This is similar to Render's free tier. Setting `--min-instances=1` removes
cold starts but keeps an instance billed all the time, which would use up the
free allowance in about two days, so it is not recommended for now.

At the end, gcloud prints a **Service URL** like
`https://beattheblues-reco-abc123xyz-as.a.run.app`. Copy it.

## 12. Test it

```powershell
$URL = "https://beattheblues-reco-...run.app"   # paste your Service URL

# Health check: should say the backend is live
Invoke-RestMethod "$URL/"

# A recommendation (the first one is slow, see cold starts above)
Invoke-RestMethod -Method Post -Uri "$URL/recommend" `
  -ContentType "application/json" -Body '{"query": "rainy sunday morning"}'

# Search
Invoke-RestMethod -Method Post -Uri "$URL/search" `
  -ContentType "application/json" -Body '{"query": "love"}'
```

If something fails, look at the logs (Step 14).

## 13. Point the Vercel frontend at the new URL

The frontend reads the backend addresses from environment variables
(`my-frontend/src/config.ts`). Create React App puts them into the JavaScript
**when the site is built**, so after changing them you must redeploy.

1. Merge the branch with this change into `main` first. Until then the
   deployed frontend still has the Render addresses written into the code.
2. In Vercel, open the project, go to **Settings > Environment Variables**, and
   add:
   - Name: `REACT_APP_RECO_API_URL`
   - Value: your Cloud Run Service URL, with no trailing slash.
   - Environments: Production (and Preview if you like).
3. Go to **Deployments**, open the latest production deployment, and click
   **Redeploy**.
4. Open <https://beattheblues.vercel.app> and try a search and a
   recommendation.

`REACT_APP_API_URL` does the same for the accounts backend (`my-backend`). Leave
it unset to keep using `https://beattheblues.onrender.com`.

CORS note: the API only accepts browser requests from
`https://beattheblues.vercel.app` and `http://localhost:3000` (see
`master_app.py`). Vercel preview URLs are not on that list, so test previews
locally or on the production URL.

## 14. Day-to-day: redeploying, logs, shutting down Render

- **Deploy a new version** (new code or a newly trained model): repeat Step 10
  part 3 and Step 11. Cloud Run switches traffic to the new version only once
  it starts successfully.
- **Roll back**: in the console, open Cloud Run > `beattheblues-reco` >
  **Revisions**, and send 100% of traffic to the previous revision.
- **Logs**: Cloud Run > `beattheblues-reco` > **Logs**, or:

  ```powershell
  gcloud run services logs read beattheblues-reco --region=$REGION --limit=100
  ```

- **Shut down Render's `beattheblues-reco`** only after the Vercel site works
  against Cloud Run for a day or two, so you have a fallback.

## 15. Optional: move the accounts backend too

Only needed if `https://beattheblues.onrender.com` (logins, playlists) is also
down. It is a small Node app, so it is cheap to run and can be built directly
from its folder:

```powershell
"postgresql://PASTE-YOUR-STRING-HERE" | Out-File -NoNewline -Encoding ascii db.txt
gcloud secrets create database-url --data-file=db.txt
Remove-Item db.txt
gcloud secrets add-iam-policy-binding database-url `
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

gcloud run deploy beattheblues-api --source my-backend --region=$REGION `
  --service-account=$SA --set-secrets="DATABASE_URL=database-url:latest" `
  --memory=512Mi --max-instances=1 --allow-unauthenticated
```

Then set `REACT_APP_API_URL` in Vercel to its URL and redeploy. (Google sign-in
also needs the new frontend/backend URLs allowed in the Google OAuth client, if
they change.)

## 16. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Build fails: `Missing song_recommendation/ml_vector_reduction.keras` | Copy the model files (Step 7) and build again. |
| Build fails with a permission error on Artifact Registry or storage | New projects sometimes give Cloud Build's account too few rights. Grant it the **Artifact Registry Writer** and **Storage Object Viewer** roles on IAM, or ask me. |
| Deploy fails: "Permission denied on secret" | Step 9's `add-iam-policy-binding` was skipped for that secret. |
| `/recommend` returns "Memory limit exceeded" in logs | Raise `--memory` to `4Gi` (also needs `--cpu=2`). |
| `/recommend` error: "Model outputs ...D vectors but the song_vector table has ... columns" | The model and the database are from different training runs. See Step 7 part 2. |
| `/recommend` error mentions `NEON_CONNECTION_STRING` or a connection failure | Check the secret has no newline or quotes, and the string starts with `postgresql://`. Update it with `gcloud secrets versions add neon-connection-string --data-file=neon.txt`, then redeploy. |
| Site shows CORS errors in the browser console | The page origin is not in `master_app.py`'s allowed list, or the frontend still calls Render because it was not redeployed after setting the variable. |
| First request is very slow | Cold start, expected with `--min-instances=0`. |
