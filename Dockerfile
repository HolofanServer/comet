FROM python:3.10-bookworm

# 依存だけ先にコピー
COPY requirements.txt /tmp/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 libopus-dev ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install -r /tmp/requirements.txt

WORKDIR /app
COPY . /app
