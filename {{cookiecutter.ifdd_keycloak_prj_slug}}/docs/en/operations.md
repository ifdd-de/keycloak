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

With `KC_METRICS_ENABLED` the readiness includes the database, so Keycloak
turns unhealthy while the database is gone. Docker does not restart an
unhealthy container by itself; `docker compose ps` shows the state. Both
containers restart with `restart: always` when they exit.

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

| What | How |
|---|---|
| the database (realm, users, sessions, events) | volume `postgres-data`, for example `docker compose -f docker-compose-production.yml exec postgres pg_dump -U keycloak keycloak > keycloak.sql` |
| `.env` | admin and database password, client secrets |

`realm/` is in Git; it does not contain users or anything changed in the
admin console. Restore the database dump into an empty database before
Keycloak starts, with the database password of the `.env` it was created
with.

```{note}
Not tested: backup and restore of the database.
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
