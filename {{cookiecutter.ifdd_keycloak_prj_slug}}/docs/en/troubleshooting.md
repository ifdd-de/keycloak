(ifdd-keycloak-troubleshooting)=
# Troubleshooting

Known failure patterns, from setups of IFDD nodes. Start with
`docker compose -f docker-compose-production.yml logs keycloak` and the
events of the realm in the admin console.

## Start

| Symptom | Cause | Remedy |
|---|---|---|
| `docker compose` stops with `... set in .env` | a required variable is missing in `.env`, for example `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` after a template update (`.env` is on the skip list) | add the entry; for the user admin client also create the client ({ref}`ifdd-keycloak-realm`) |
| the container is `starting` for minutes | the first start builds Keycloak and imports the realm | wait; the health check allows 180 s |
| Keycloak cannot connect to the database after `.env` was changed | the database keeps the password it was created with | restore the old `IFDD_KEYCLOAK_DB_PASSWORD`, or change the password inside PostgreSQL as well |
| `unhealthy`, but Keycloak runs | the database is gone (readiness includes it); Docker does not restart unhealthy containers | bring the database back; `docker compose ps` shows both |
| `build_realm.py` fails with an unknown Keycloak version | there is no file of built-in scopes for that image tag | use a Keycloak version the template knows |

## Backup and restore

| Symptom | Cause | Remedy |
|---|---|---|
| `docker compose` stops with `IFDD_KEYCLOAK_BACKUP_UID ... set in .env` | the instance is older than the backup service; `cruft update` leaves `.env` alone | add `IFDD_KEYCLOAK_BACKUP_UID` and `IFDD_KEYCLOAK_BACKUP_GID` with the values of `id -u` and `id -g` of the user who is to own the dumps |
| `bind source path does not exist: .../backups` | `backups/` is missing, for example in a fresh clone or after the template update that brought the backup service (Git keeps no empty directory) | `mkdir -m 700 backups` as the user of `IFDD_KEYCLOAK_BACKUP_UID` |
| `backup` restarts, its log says `BACKUP_DIR points to a file or folder with insufficient permissions` | `backups/` belongs to another user than `IFDD_KEYCLOAK_BACKUP_UID`, for example to root | give it to that user: `chown -R <uid>:<gid> backups` |
| `backup` is `unhealthy` | the last dump failed, for example while the database was gone | `docker compose -f docker-compose-production.yml logs backup`; the next successful dump makes it healthy again |
| the dumps are made at an unexpected hour | the schedule runs in the time zone `TZ` of the container; an unknown name falls back to UTC | check `TZ` in the compose file and the dates in the file names |
| the post-generation hook stops with `refusing to run as root` | the instance was generated as root | generate it as the user who is to own the dumps |
| `adm_backup_restore.sh` says `needs a terminal to confirm` | it ran without a terminal, for example from cron or a pipe | run it in an interactive shell |
| the restore stops with `the restore failed; Keycloak stays stopped` | the dump could not be loaded (see the message of `psql` above it) | restore the safety dump the script names, with the same script |

## Realm

| Symptom | Cause | Remedy |
|---|---|---|
| a change in `values.toml` or after `cruft update` has no effect | the import runs only while the realm does not exist | make the change in the admin console ({ref}`ifdd-keycloak-operations`) |
| `realm/build_realm.py --check` fails in CI | `values.toml` or `realm/ifdd_realm/` changed without rebuilding | run `python3 realm/build_realm.py`, commit the generated files |
| the login page shows Keycloak's default look | the realm was imported before the theme, or `themes/ifdd` is not mounted | set the theme in the admin console ({ref}`ifdd-keycloak-realm`); check the volumes of the compose file |
| a change of the theme has no effect | Keycloak caches themes outside `start-dev` | restart Keycloak |
| `build_realm.py` stops with `realm '...' is named in ...` | two values files name the same realm | give each further realm its own `name` |
| the first `cruft update` after the template of 2026-10-20 reports patch errors for `realm/ifdd_realm/__pycache__/*.pyc` | the older template wrote byte code when its hook ran `build_realm.py`; it differs in every rendering | run that update as `PYTHONDONTWRITEBYTECODE=1 cruft update`, or remove `realm/ifdd_realm/__pycache__` first; later updates need nothing |
| a client secret in `.env` does not work | the realm was imported with another value, or the secret was rotated in Keycloak | take the secret from the admin console (client, "Credentials") |

## Logins

| Symptom | Cause | Remedy |
|---|---|---|
| `Invalid parameter: redirect_uri` | the redirect URI of the service is not exactly one of the client's | compare with {ref}`ifdd-keycloak-realm`; fix the service URL or the client in the admin console |
| tokens are refused by the backend (issuer) | `IFDD_KEYCLOAK_HOST` does not match the host of `{{ cookiecutter.ifdd_oidc_realm }}` | set the host from `ifdd_oidc_realm`, restart |
| users are signed out when several tabs are open | refresh token rotation: each refresh token is valid once | expected |
| an account is locked after failed logins | brute force protection | wait, or unlock the user in the admin console |
| "Account is not fully set up" for the password grant, or a form at the first login | Keycloak's user profile requires e-mail, first and last name | fill them in; the password grant is not offered to the IFDD clients anyway |
| login against the development instance fails for the other services | the redirect URIs name the production hosts | use the production instance |

## Rights

| Symptom | Cause | Remedy |
|---|---|---|
| 403 from the backend although the login works | the user is in no node group | add the user to `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` or another node group |
| 403 for domain contexts only | the user or service account has no context pattern | group `ifdd_ctx_<pattern>`; for an older realm see {ref}`ifdd-keycloak-realm` |
| the login gate of the proxy refuses a user | no verified e-mail address, or not in the group the service requires | set and verify the address; add the group |
