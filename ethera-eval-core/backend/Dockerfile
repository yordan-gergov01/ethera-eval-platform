# Build from the repository root: docker build -f backend/Dockerfile .
#
# Stages:
#   deps     virtual environment with the backend's pinned, hash-checked dependencies
#   runtime  the production image: only common_lib, backend and migrations, non-root
#   test     test runner: adds the development dependencies and the tests; the
#            runtime image never contains them

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
COPY requirements/backend.txt /tmp/requirements/backend.txt
RUN python -m venv /opt/venv \
    && pip install --require-hashes -r /tmp/requirements/backend.txt

FROM base AS runtime
COPY --from=deps /opt/venv /opt/venv
COPY common_lib ./common_lib
COPY backend ./backend
COPY evals ./evals
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["uvicorn", "evals.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

FROM deps AS test
COPY requirements/dev.txt /tmp/requirements/dev.txt
RUN pip install --require-hashes -r /tmp/requirements/dev.txt
# The packages are used from the source tree, without installing the project.
ENV PYTHONPATH=/app
COPY pyproject.toml docker-compose.yml .env.example .dockerignore ./
COPY docker/rabbitmq/provision-entrypoint.sh ./docker/rabbitmq/provision-entrypoint.sh
COPY common_lib ./common_lib
COPY backend ./backend
COPY runner ./runner
COPY evals ./evals
COPY migrations ./migrations
# The demo target's tests run in the suite; its own runtime image arrives in slice 003 (D-024).
COPY demo_target ./demo_target
COPY tests ./tests
# ruff, mypy, import-linter and pytest keep their caches in the working directory; the
# sources stay owned by root and read-only for the test user.
RUN chown app:app /app
USER app
CMD ["pytest", "-p", "no:cacheprovider"]
