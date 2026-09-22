# Build from the repository root:
#   docker build -t song-recommendation-trainer .
# A Cloud Run Job can supply NEON_CONNECTION_STRING as a Secret Manager
# environment variable and override/add training flags with --args.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TF_CPP_MIN_LOG_LEVEL=2 \
    HF_HOME=/opt/huggingface

WORKDIR /app

# libgomp is required by scikit-learn; libpq supports PostgreSQL connections.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY song_recommendation/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY song_recommendation /app/song_recommendation

# Cache the model that train_ml.py uses so the job does not need to download it
# when it starts. Set HF_HOME above so the cache is in a predictable location.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

ENTRYPOINT ["python", "-m", "song_recommendation.train_ml"]
