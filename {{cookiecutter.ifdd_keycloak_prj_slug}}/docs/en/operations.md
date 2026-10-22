(ifdd-keycloak-operations)=
# Operations

## Start, stop, order

```bash
docker compose -f docker-compose-production.yml up -d
docker compose -f docker-compose-production.yml ps
docker compose -f docker-compose-production.yml down        # keeps the database volume
```

Start order across the node: Traefik first, then Keycloak and the other
services, then the full proxy with oauth2-proxy, which needs a reachable
realm at start. `.adm_03_up_services.sh` of the meta repository does exactly
that. Inside this project Keycloak waits for a healthy database.

## Health checks

| Container | Check | Interval |
|---|---|---|
| `keycloak` | `GET /health/ready` on the management port 9000, with bash (the image has no curl) | 15 s, 5 retries, start period 180 s |
| `postgres` | `pg_isready -d keycloak -U keycloak` | 10 s, 10 retries |
| `backup` | `curl` on port 8080, answered by the scheduler of the image: 503 once the last backup failed | every 5 s in the first 2 min, then 5 min, 3 retries |

With `KC_METRICS_ENABLED` the readiness includes the database, so Keycloak
turns unhealthy while the database is gone. Docker does not restart an
unhealthy container by itself; `docker compose ps` shows the state. All
containers restart with `restart: always` when they exit. The health check
of `backup` turns unhealthy when the last dump failed (also the one on
start); the log of the container shows why. Its short start interval lets
`up --wait` finish within seconds (Docker Engine 25 or later).

## Logs

```bash
docker compose -f docker-compose-production.yml logs -f keycloak
```

The realm stores login events for 30 days and admin events without
representations; they are in the admin console under "Events" of the realm.

## The realm after the first start

The import runs only while the realm does not exist. Afterwards the database
is authoritative:

- Changes of the realm file, also through `cruft update`, do not reach the
  running realm; make them in the admin console, and keep `values.toml` in
  step so that a new realm would match. {ref}`ifdd-keycloak-realm` describes
  the changes that existing realms need.
- The client secrets in `.env` are read by the first import only. Rotating a
  secret happens in the admin console (client, "Credentials"), then in the
  service that uses it.
- To create the realm again from the file, delete it in the admin console and
  restart Keycloak. All users and sessions of the realm are lost.

## Backup

The service `backup` (`{{ cookiecutter.ifdd_keycloak_backup_image }}`)
dumps the database `keycloak` with `pg_dump` while Keycloak keeps running.
The dumps go to the directory `backups/` of this instance, a plain directory
on the host, not a Docker volume:

| | Here |
|---|---|
| schedule | `{{ cookiecutter.ifdd_keycloak_backup_schedule }}`, time zone `{{ cookiecutter.ifdd_keycloak_backup_timezone }}`; also on every start of the container |
| kept | the daily dumps for {{ cookiecutter.ifdd_keycloak_backup_keep_days }} days, the weekly ones for {{ cookiecutter.ifdd_keycloak_backup_keep_weeks }} weeks, the monthly ones for {{ cookiecutter.ifdd_keycloak_backup_keep_months }} months; every single dump for 24 hours |
| owner | the host user with the ids `IFDD_KEYCLOAK_BACKUP_UID` and `IFDD_KEYCLOAK_BACKUP_GID` of `.env`; the hook wrote those of the user who generated the instance |

```text
backups/                                  mode 0700, created by the hook
  last/keycloak-YYYYMMDD-HHMMSS.sql.gz    every dump, kept for 24 hours
  daily/keycloak-YYYYMMDD.sql.gz          the last dump of each day
  weekly/keycloak-YYYYWW.sql.gz           the last dump of each ISO week
  monthly/keycloak-YYYYMM.sql.gz          the last dump of each month
  */keycloak-latest.sql.gz                link to the newest file of the folder
  pre-restore/keycloak-*.sql.gz           safety dumps of the restore script, never removed
```

The files in `daily/`, `weekly/` and `monthly/` are hard links to a dump in
`last/`, so a dump takes its disk space once. Old files are removed only after
a successful dump. A dump is plain SQL, compressed with gzip; it holds the
realms, users, sessions and events of the database, but not the database
user `keycloak` and its password.

A dump at once, for example before a change in the admin console:

```bash
docker compose -f docker-compose-production.yml exec backup sh -c 'umask 077 && /backup.sh'
```

Without the `umask`, the files of such a call are writable for everyone; the
scheduled dumps are not. `backups/` itself is open to its owner only.

Not in the dumps, and worth a copy of their own:

| What | Why |
|---|---|
| `.env` | admin and database password, client secrets, the ids of the backup user |
| `realm/` | in Git; it does not contain users or anything changed in the admin console |

The dumps stay on this host: against the loss of the host, copy `backups/`
to another system. The instance does not do that.

### Restore

```bash
./adm_backup_restore.sh backups/daily/keycloak-YYYYMMDD.sql.gz
```

The script checks the file (`gzip -t`) and asks to type `restore`. Then it
stops `keycloak` and `backup`, saves the current database to
`backups/pre-restore/`, drops and recreates the database `keycloak`, loads
the dump and starts both services again. PostgreSQL keeps running. It needs a
terminal and the containers of `docker-compose-production.yml`.

- If loading fails, Keycloak stays stopped and the script names the safety
  dump; restore that one with the same script.
- The database user and its password are not in the dump: the restore works
  with the password of the current `.env`.
- Keycloak takes the client secrets from the restored database. Into a new
  instance, the services keep needing the secrets of the old one (its `.env`,
  or the admin console).
- Users, sessions and the changes made in the admin console are those of the
  dump.

```{note}
Tested with locally built images: PostgreSQL 18.6 with the entrypoint of the
official image, the backup image built from its Dockerfile, the Keycloak
26.8.0 distribution. Not tested: the published images themselves, the time
zone in the published backup image, and Docker on macOS.
```

## Updates

Template updates arrive with `cruft update`; `.env` is on the skip list. After
any `cruft update` run `python3 realm/build_realm.py` once more, so that
local edits of `values.toml` and the template's version of the file agree.
Shared values (hosts, client IDs, role names) are best changed in
`.cookiecutter_all.yaml` and applied with
`cruft update --variables-to-update '{...}'`; for a running realm they also
need the admin console.

The database keeps the password it was created with: changing
`IFDD_KEYCLOAK_DB_PASSWORD` in `.env` alone locks Keycloak out.

```{note}
Not tested: a major upgrade of PostgreSQL with data in the volume, and an
upgrade of Keycloak with an existing database.
```
