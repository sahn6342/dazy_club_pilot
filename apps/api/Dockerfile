FROM python:3.12-alpine
RUN pip install uv
WORKDIR /app

# Copy only the dependency manifests first so this layer caches across
# source-only changes. --frozen requires uv.lock to be present.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# dazy.db and uploaded media persist in /data — mount a volume there in
# production (see docker-compose.yml). init_db()/seed_if_empty() run on
# startup via the FastAPI lifespan (main.py) — no separate migrate step.
ENV DAZY_DB_PATH=/data/dazy.db
ENV DAZY_MEDIA_DIR=/data/media
RUN mkdir -p /data

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app /data
USER app

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
