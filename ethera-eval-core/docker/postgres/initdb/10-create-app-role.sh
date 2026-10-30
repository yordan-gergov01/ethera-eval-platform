#!/bin/sh
# Runs once, on the first start with an empty data volume.
#
# Creates the non-superuser role the backend connects with, hands it ownership
# of the application database, and enables pgvector as the superuser so the
# application role never needs superuser rights.
#
# The official entrypoint sources *.sh files that are not executable, so this
# script does not depend on the executable bit being preserved on checkout.
# Because it is sourced, it sets no shell options of its own: the entrypoint
# already runs with errexit, and ON_ERROR_STOP makes any SQL error fatal.

psql --no-psqlrc -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set app_user="$POSTGRES_APP_USER" \
    --set app_password="$POSTGRES_APP_PASSWORD" \
    --set app_db="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
ALTER DATABASE :"app_db" OWNER TO :"app_user";
REVOKE ALL ON DATABASE :"app_db" FROM PUBLIC;
CREATE EXTENSION IF NOT EXISTS vector;
SQL
