FROM node:22-bookworm-slim

WORKDIR /app

# Node runs yt-dlp-ejs; FFmpeg merges media streams and converts audio.
RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-venv ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade -r requirements.txt

COPY . ./
RUN mkdir -p downloads

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8001}"]
