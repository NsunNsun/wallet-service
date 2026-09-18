FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app app

COPY requirements.txt .
RUN pip install -r requirements.txt

# --- Image with dev dependencies, used to run tests and linters ---
FROM base AS test
# Tests run as a non-root user and need to write caches into /app.
RUN chown app:app /app
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY --chown=app:app . .
USER app
CMD ["sh", "-c", "ruff check . && ruff format --check . && pytest -v"]

# --- Production image ---
FROM base AS runtime
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini entrypoint.sh ./
RUN chmod +x entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
