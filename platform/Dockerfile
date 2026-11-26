# Production image: the API and the built frontend in one container (docker-compose.yml runs it with
# Postgres). Build with `make build`; CI publishes it (T012).

# --- Frontend build ---------------------------------------------------------------------------
FROM node:26-alpine AS frontend
ENV NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Runtime ----------------------------------------------------------------------------------
FROM python:3.14-slim
ARG APP_VERSION=dev
LABEL org.opencontainers.image.version="${APP_VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    APP_VERSION=${APP_VERSION} \
    STATIC_DIR=/app/static

RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent \
      --shell /usr/sbin/nologin app

WORKDIR /app
RUN --mount=type=bind,source=backend/requirements.txt,target=/tmp/requirements.txt \
    pip install --no-cache-dir --require-hashes -r /tmp/requirements.txt

# Code and assets stay owned by root: the app user can read them, not change them.
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --chmod=755 backend/entrypoint.sh /usr/local/bin/entrypoint
COPY --from=frontend /build/dist ./static

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
ENTRYPOINT ["entrypoint"]
