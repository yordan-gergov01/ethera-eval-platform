# Build from the repository root: docker build -f runner/Dockerfile .
#
# Stages:
#   deps     virtual environment with the runner's pinned, hash-checked dependencies
#   runtime  the production image: only common_lib and runner, non-root, no ports
# The tests run in the backend's test image, which contains both services.

ARG PYTHON_IMAGE=python:3.12.15-slim-trixie@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d

FROM ${PYTHON_IMAGE} AS base
# No .pyc files: the runtime filesystem is read-only. Unbuffered output for logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:$PATH
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app

FROM base AS deps
COPY requirements/runner.txt /tmp/requirements/runner.txt
RUN python -m venv /opt/venv \
    && pip install --require-hashes -r /tmp/requirements/runner.txt

FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
COPY common_lib ./common_lib
COPY runner ./runner
USER app
CMD ["python", "-m", "runner.main"]
