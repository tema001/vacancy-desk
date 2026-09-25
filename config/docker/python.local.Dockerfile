FROM python:3.13-slim-trixie AS base

WORKDIR /app

ENV TZ=Europe/Kyiv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV UV_NO_CACHE=1

COPY pyproject.toml uv.lock /app/

RUN --mount=from=ghcr.io/astral-sh/uv:0.11.7,source=/uv,target=/bin/uv \
    uv sync --frozen --no-install-project --no-default-groups

FROM base AS http-service
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.7,source=/uv,target=/bin/uv \
    uv sync --frozen --no-install-project --no-default-groups --group http-service

FROM base AS worker
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.7,source=/uv,target=/bin/uv \
    uv sync --frozen --no-install-project --no-default-groups --group worker

FROM base AS dev
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.7,source=/uv,target=/bin/uv \
    uv sync --frozen --no-install-project --no-default-groups --group worker --group dev

FROM base AS pre_build

ENV UV_COMPILE_BYTECODE=1

# Copy only the required data
#COPY ./alembic.ini /app/alembic.ini
#COPY ./config/config.yaml /app/config/config.yaml
COPY ./src /app/src
