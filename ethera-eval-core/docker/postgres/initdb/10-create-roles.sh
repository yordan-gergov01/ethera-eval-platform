#!/bin/sh
# Runs once, on the first start with an empty data volume.
#
# Creates the two non-superuser roles of D-021 and enables pgvector as the
# superuser, so neither role ever needs superuser rights:
#   - the migration owner (LOGIN, BYPASSRLS) owns the database and its public
#     schema; the backend uses it only at startup, under the startup lock, to
#     assert the role attributes, migrate, grant and seed;
#   - the runtime role (LOGIN, NOBYPASSRLS) serves every request. It may only
#     connect here; its data grants are applied by the owner at every startup
#     (backend/core/startup.py), so they also cover tables created later.
#
# The official entrypoint sources *.sh files that are not executable, so this
# script does not depend on the executable bit being preserved on checkout.
# Because it is sourced, it sets no shell options of its own: the entrypoint
# already runs with errexit, and ON_ERROR_STOP makes any SQL error fatal.

psql --no-psqlrc -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set owner_user="$POSTGRES_OWNER_USER" \
    --set owner_password="$POSTGRES_OWNER_PASSWORD" \
    --set app_user="$POSTGRES_APP_USER" \
    --set app_password="$POSTGRES_APP_PASSWORD" \
    --set app_db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"owner_user" LOGIN BYPASSRLS PASSWORD :'owner_password';
CREATE ROLE :"app_user" LOGIN NOBYPASSRLS PASSWORD :'app_password';
ALTER DATABASE :"app_db" OWNER TO :"owner_user";
REVOKE ALL ON DATABASE :"app_db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"app_db" TO :"app_user";
CREATE EXTENSION IF NOT EXISTS vector;
SQL
