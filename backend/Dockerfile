# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (build essentials kept minimal)
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential curl ca-certificates git  && rm -rf /var/lib/apt/lists/*

# Copy backend only (bind mount at runtime for dev)
COPY requirements-docker.txt ./requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel &&     pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

# Default command expects main.py to live in /app (we bind-mount)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
