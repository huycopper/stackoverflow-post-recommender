# Spark image for the cleaning pipeline (python -m so_recommender.clean).
# The repo is mounted at /app at run time (see docker-compose.clean.yml), so code changes need
# no rebuild. Only Python, Java and pinned libraries live in the image.
FROM python:3.11-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyspark==3.5.3 pytest==8.3.3

WORKDIR /app
ENV PYTHONPATH=/app/src \
    PYSPARK_PYTHON=python \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "so_recommender.clean", "--config", "config/clean.toml"]
