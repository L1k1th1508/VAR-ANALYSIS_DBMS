#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v owner_password="$DB_OWNER_PASSWORD" -v reader_password="$APP_READER_PASSWORD" \
  -v admin_password="$APP_ADMIN_PASSWORD" -v dbname="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE db_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'owner_password') \gexec
SELECT format('CREATE ROLE app_reader LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'reader_password') \gexec
SELECT format('CREATE ROLE app_admin LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', :'admin_password') \gexec
SELECT format('ALTER DATABASE %I OWNER TO db_owner', :'dbname') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', :'dbname') \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO app_reader, app_admin', :'dbname') \gexec
SQL
