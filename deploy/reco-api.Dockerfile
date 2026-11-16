# Container image for the recommendation API (master_app.py: /search,
# /recommend and /personality). This is the web server, not the training job;
# the training job keeps using the Dockerfile at the repository root.
#
# Build and deploy it with deploy/cloudbuild.reco-api.yaml, as described in
# docs/deploy-cloud-run.md. To build locally from the repository root:
#   docker build -f deploy/reco-api.Dockerfile -t reco-api .
#
# The trained model is NOT in git. Before building, copy these two files from
# the model bucket into song_recommendation/:
#   ml_vector_reduction.keras
#   model_metadata.json
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TF_CPP_MIN_LOG_LEVEL=2 \
    CUDA_VISIBLE_DEVICES=-1 \
    HF_HOME=/opt/huggingface \
    PORT=8080

WORKDIR /app

# libgomp is needed by scikit-learn and faiss.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install the CPU-only build of PyTorch first. sentence-transformers depends on
# PyTorch, and the default Linux wheel bundles several GB of NVIDIA GPU
# libraries that Cloud Run cannot use. Installing the CPU wheel first keeps the
# image much smaller, which means faster deploys and cheaper image storage.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Download the sentence-embedding model at build time, so a cold start does
# not have to fetch it from Hugging Face. It must match "encoder" in
# model_metadata.json (all-MiniLM-L6-v2 for every model trained so far).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY master_app.py /app/
COPY personality_test /app/personality_test
COPY song_searcher /app/song_searcher
COPY song_recommendation /app/song_recommendation

# Fail the build early, with a clear message, if the model files were not
# copied in. Without them /recommend would only fail at runtime.
RUN for f in ml_vector_reduction.keras model_metadata.json; do \
      if [ ! -f "song_recommendation/$f" ]; then \
        echo "Missing song_recommendation/$f. See docs/deploy-cloud-run.md."; exit 1; \
      fi; \
    done

# One worker process keeps a single copy of the model in memory. Threads let
# that worker serve several requests at once. --timeout 0 lets Cloud Run's own
# request timeout apply instead of gunicorn's.
CMD ["sh", "-c", "exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 master_app:master_app"]
