#!/usr/bin/env bash
# Restore the Keycloak database from a dump of the backup service.
#
#   ./adm_backup_restore.sh backups/daily/keycloak-YYYYMMDD.sql.gz
#
# 1. checks the dump (gzip -t) and asks to type "restore";
# 2. stops keycloak and backup (postgres keeps running);
# 3. saves the current database, if there is one, to backups/pre-restore/
#    (safety dump);
# 4. drops and recreates the database keycloak, loads the dump;
# 5. starts keycloak and backup again.
#
# Works on docker-compose-production.yml of this directory. Needs a terminal
# for the confirmation. A safety dump is restored with this script as well.
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose -f docker-compose-production.yml)
DB=keycloak
DB_USER=keycloak
SAFETY_DIR=backups/pre-restore

die() {
    printf 'adm_backup_restore: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf 'usage: %s DUMP_FILE\n  DUMP_FILE: a .sql.gz file of the backup service, e.g. from backups/daily/\n' "$0" >&2
    exit 2
}

pg() {
    # A command inside the postgres container; local connections need no password.
    "${COMPOSE[@]}" exec -T postgres "$@"
}

[ "$#" -eq 1 ] || usage
dump=$1
[ -f "$dump" ] && [ -r "$dump" ] || die "cannot read $dump"
gzip -t -- "$dump" 2>/dev/null || die "$dump is not a complete gzip file"
[ -t 0 ] || die "needs a terminal to confirm"

pg pg_isready -q -U "$DB_USER" -d postgres \
    || die "the postgres container does not answer; start it with: ${COMPOSE[*]} up -d postgres"

printf 'This replaces the database %s with\n  %s\n' "$DB" "$dump"
printf 'Keycloak and the backup service are stopped meanwhile; the current\n'
printf 'database is saved to %s/ first.\n' "$SAFETY_DIR"
printf 'Type "restore" to continue: '
answer=
read -r answer || true
[ "$answer" = "restore" ] || die "cancelled, nothing changed"

"${COMPOSE[@]}" stop keycloak backup

umask 077
exists=$(pg psql -X -tA -U "$DB_USER" -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$DB'")
if [ "$exists" = "1" ]; then
    mkdir -p "$SAFETY_DIR"
    safety="$SAFETY_DIR/$DB-$(date +%Y%m%d-%H%M%S).sql.gz"
    if ! pg pg_dump -U "$DB_USER" -d "$DB" | gzip > "$safety"; then
        rm -f -- "$safety"
        die "the safety dump failed; nothing changed. Keycloak is stopped: ${COMPOSE[*]} up -d keycloak backup"
    fi
    printf 'Saved the current database to %s\n' "$safety"
else
    # Left behind by an interrupted restore: nothing to save.
    safety=
    printf 'The database %s does not exist; no safety dump.\n' "$DB"
fi

on_error() {
    printf 'adm_backup_restore: the restore failed; Keycloak stays stopped.\n' >&2
    if [ -n "$safety" ]; then
        printf '  The previous database is in %s;\n  restore it with: %s %s\n' "$safety" "$0" "$safety" >&2
    fi
}
# From here on a failure leaves an empty or partial database behind.
trap on_error ERR

pg dropdb -U "$DB_USER" --if-exists --force "$DB"
pg createdb -U "$DB_USER" -O "$DB_USER" "$DB"
gzip -dc -- "$dump" | pg psql -X -q -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB" > /dev/null

trap - ERR
"${COMPOSE[@]}" up -d keycloak backup
printf 'Restored %s from %s. Keycloak starts now; sessions are those of the dump.\n' "$DB" "$dump"
