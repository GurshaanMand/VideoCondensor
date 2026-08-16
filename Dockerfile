# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11.13
FROM python:${PYTHON_VERSION}-slim AS base

ARG DENO_VERSION=2.8.1

# Prevent Python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Prevent stdout/stderr buffering
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# FFmpeg renders the selected ranges. Deno runs yt-dlp's current YouTube
# JavaScript challenge solver. Both amd64 (AWS) and arm64 (Apple Silicon) work.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    unzip \
    && case "$(dpkg --print-architecture)" in \
        amd64) DENO_ARCH="x86_64-unknown-linux-gnu" ;; \
        arm64) DENO_ARCH="aarch64-unknown-linux-gnu" ;; \
        *) echo "Unsupported architecture" && exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-${DENO_ARCH}.zip" -o /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && deno --version \
    && rm -f /tmp/deno.zip \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with a real home directory
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    appuser

# Hugging Face cache location
ENV HF_HOME=/home/appuser/.cache/huggingface
ENV TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface
ENV DENO_DIR=/home/appuser/.cache/deno
ENV VIDEO_CONDENSER_DATA_DIR=/app/runtime/jobs

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install -r requirements.txt

# Bake the embedding model into the image so the first user job does not
# depend on a Hugging Face download or hold extra cold-start uncertainty.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Production workers use only the model baked into the image. This removes a
# runtime dependency on Hugging Face availability and avoids cold-start HEADs.
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

# Fail the image build if the baked cache cannot actually serve an embedding
# without network access.
RUN python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True); assert model.encode(['container smoke']).shape == (1, 384)"

# Copy application files
COPY --chown=appuser:appuser . .

# Ensure the home directory and cache exist and are owned by appuser
RUN mkdir -p /home/appuser/.cache/huggingface /home/appuser/.cache/deno /app/runtime/jobs && \
    chown -R appuser:appuser /home/appuser /app/runtime

# Run as non-root
USER appuser

# Expose FastAPI port
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8000/health >/dev/null || exit 1

# Start FastAPI
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
