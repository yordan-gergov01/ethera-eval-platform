# syntax=docker/dockerfile:1
# Build from the repository root: docker build -t ethera-eval-web .
#
# Stages:
#   build    installs the pinned dependencies with npm ci and builds the static app
#   runtime  the production image: non-root nginx serving the built files; /config.js
#            is written from BACKEND_URL when the container starts

ARG NODE_IMAGE=node:24.19.0-alpine3.24@sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.30.5-alpine3.24@sha256:15c994d10d6d78658721c3bcafff14cb281fba2a4bdf9d5ba92c416a472516e3

FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
# The image's entrypoint renders /etc/nginx/templates into this directory and
# substitutes only BACKEND_ORIGIN, which 10-runtime-config.envsh exports.
ENV NGINX_ENVSUBST_OUTPUT_DIR=/tmp/nginx/conf.d \
    NGINX_ENVSUBST_FILTER=^BACKEND_ORIGIN$
USER root
RUN rm -f /etc/nginx/conf.d/default.conf
USER 101
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/templates/ /etc/nginx/templates/
COPY --chmod=0755 docker/entrypoint.d/10-runtime-config.envsh /docker-entrypoint.d/
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
# Fetching index.html proves the built app is served, not only that nginx runs.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/index.html || exit 1
