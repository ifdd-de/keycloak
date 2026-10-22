# Changelog

## [Unreleased]

- Backup of the database: a service `backup` in the production compose file
  (image `prodrigestivill/postgres-backup-local`) runs `pg_dump` on a schedule
  and on every start, and keeps daily, weekly and monthly dumps in `backups/`
  of the instance, a bind mount, not a volume. Its health check (503 after a
  failed dump) probes every 5 s in the first two minutes, so `up --wait` of
  the meta repository does not time out; the image's own check would wait
  5 minutes. New variables
  `ifdd_keycloak_backup_image` (default
  `prodrigestivill/postgres-backup-local:18`, same major version as
  `ifdd_keycloak_postgres_image`, checked by the pre-generation hook),
  `ifdd_keycloak_backup_schedule` (`@daily`), `ifdd_keycloak_backup_timezone`
  (`UTC`), `ifdd_keycloak_backup_keep_days`, `_keep_weeks`, `_keep_months`
  (`7`, `4`, `6`).
- The backup service runs as the host user of the new `.env` entries
  `IFDD_KEYCLOAK_BACKUP_UID` and `IFDD_KEYCLOAK_BACKUP_GID`. The
  post-generation hook writes the ids of the user who generates the instance
  (new placeholders `<<host:uid>>`, `<<host:gid>>`), refuses to run as root,
  and creates `backups/` with mode 0700. `backups/` is in the instance's
  `.gitignore`.
- `adm_backup_restore.sh DUMP_FILE` restores a dump: confirmation, safety dump
  of the current database in `backups/pre-restore/`, new database, Keycloak
  stays stopped if loading fails.
- Documentation: backup and restore in `operations`, new section in
  `troubleshooting`, entries in `setup`, `security`, `reference`, `index` and
  `build-release`. The former note that a restore needs the database password
  of the old `.env` was wrong: a dump of one database holds no roles or
  passwords.
- Instance CI: the compose check replaces the new placeholders and creates an
  empty `backups/`.
- READMEs: a section on the use of large language models; the instance README
  has no honesty notes any more, the template README no test reports.
- Upgrade: `cruft update` leaves `.env` alone and Git keeps no empty
  directory. Before the next `docker compose up` add
  `IFDD_KEYCLOAK_BACKUP_UID` and `IFDD_KEYCLOAK_BACKUP_GID` (values of `id -u`
  and `id -g`) to `.env`, and run `mkdir -m 700 backups`.
- Time series API (ifdd-ts-api): new client `ifdd_ts_api_oidc_client_id`
  (default `ifdd-ts-api`) that only carries roles and is the audience of the
  tokens of ifdd-ts-api: `ifdd_ts_api_role_read` (`ifdd_ts_ro`),
  `ifdd_ts_api_role_write` (`ifdd_ts_rw`) and the context root as store
  pattern. New client `ifdd_keycloak_ts_ingest_client_id` (`ifdd-ts-ingest`)
  with client credentials, write role and root. The service accounts of ct
  (write, root) and of the api client (read, root) get roles of ifdd-ts-api
  too; ct also in its scope mapping. Values files without `[clients.ts_api]`
  still load and give a realm without these clients.
- New `.env` entries `IFDD_KEYCLOAK_TSAPI_CLIENT_SECRET` (required by
  Keycloak for the client, used by nobody) and
  `IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET`; the compose files require both. The
  pre-generation hook checks the new names (roles without a dot, distinct).
- Documentation: `realm` (clients, section "Time series API", adding the
  clients to an existing realm with `kcadm.sh`), `reference`, `setup`.
- Upgrade of a running realm: see `realm`, "Adding the clients of ts-api";
  it prints the two secrets for `.env`.

## [26.10.2] - 2026-10-14

- `realm/OVERVIEW.md` is a Sphinx page: it starts with the MyST label
  `ifdd-keycloak-realm-overview`. The page `realm` of the documentation says
  how to put it into the full documentation. Template CI builds it with
  `sphinx -W` for every fixture.
- Description of the realm role `ifdd_public`: names `/prot_version` (the
  endpoint ifdd-be has), not `/version_protected`. Existing realms keep the
  old text until it is changed in the admin console; Keycloak imports the
  file on the first start only.
- Documentation of the instance in `docs/en` and `docs/de` (Sphinx sources,
  MyST Markdown): index, setup, build and release, operations, security,
  troubleshooting, reference, realm. The instance README is now an entry
  point with a quick start, the links, honesty notes and the license; its
  former sections moved into the documentation (the steps for existing
  realms into the page `realm`).
- `docs/_build/` in `.gitignore` of the instance.
- Template CI: `tests/check_docs.py` checks for every fixture that both
  languages match and build without warnings (`tests/docs/conf.py`,
  `tests/docs/requirements.txt`).

- Backend client: the redirect URI of the backend is exactly
  `<ifdd_be_url>/docs/oauth2-redirect` (Swagger UI of ifdd-be-core) instead
  of the pattern `<ifdd_be_url>/*` (RFC 9700, 2.1). New test: no redirect
  pattern in the backend client. Golden files regenerated. Existing realms:
  see the instance README, "Restricting the backend redirect in an existing
  realm".

- Context patterns (ifdd-be-core "Contexts and access"): new shared variable
  `ifdd_context_root` (default `ifdd.de`). The backend client gets a client
  role of that name (no realm role), a group `ifdd_ctx_<root>` grants it,
  and the service accounts of api, ct and ts hold it (ct and ts also in
  their scope mapping). The pre-hook requires a dotted lower-case name.
  Existing realms: see the instance README, "Adding the context root to an
  existing realm".

- Backend client: its own client roles also in the ID token and the userinfo
  response, for ifdd-ui (`user.profile`); the access token is unchanged.
- New client `ifdd_keycloak_useradmin_client_id` (default `ifdd-user-admin`):
  client credentials only, for scripts that create users, set their
  passwords and add them to groups (`keycloak_add_user.py`). Its service
  account has `manage-users` of `realm-management` and nothing else; full
  scope off. `.env` gets `IFDD_KEYCLOAK_USERADMIN_CLIENT_ID` and
  `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET`.
- Upgrade: the compose files now require
  `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET`, and `cruft update` leaves `.env`
  alone. Before the next `docker compose up`, add the client to the running
  realm and both lines to `.env` (instance README, "Adding the user admin
  client to an existing realm").

## [26.10.1]

Review of 2026-10-03 (RFC 9700), checked against Keycloak 26.8.0:

- Backend client: PKCE S256 required, implicit flow off, exact UI redirect
  URIs (`/authentication/callback`, `/authentication/silent-callback`).
- Script client: client credentials only.
- No client offers `offline_access`; the backend audience scope is no longer
  a realm default; ifdd-ts and ifdd-ct without full scope.
- Node roles also as client roles of the backend client; new role
  `ifdd_nodes_priv`; groups `ifdd_nodes_readers`, `ifdd_nodes_writers`,
  `ifdd_nodes_privileged`; the default role only grants `ifdd_public`.
- Refresh token rotation, brute force protection, password policy, login
  and admin events.
- Health check of the Keycloak container (readiness incl. database).

### Initial

First release of `ifdd-de/keycloak`.

- Keycloak 26.8.0 with PostgreSQL 18 in one compose project, behind an
  `ifdd-de/proxy` instance; realm created once by the start import
  (`--import-realm`), the database is authoritative afterwards.
- Realm derived from a Keycloak 26.5.0 export: only what differs from a fresh
  realm is kept; the built-in client scopes are those of a fresh 26.8.0
  realm. `d5_*` names became `ifdd_*`; the custom login theme was dropped;
  the authorization services of the script client (a js policy that 26.8
  can no longer import) were switched off.
- Clients for the other services: ifdd-ct (client credentials, write role),
  ifdd-ts (Grafana login and client credentials, roles admin, readwrite,
  readonly), ifdd-proxy (oauth2-proxy, group claim, group `ifdd_wf_admins`).
- Secrets generated into `.env` by the post-generation hook and handed to
  the realm import as environment variables.
- The realm import file is generated by `realm/build_realm.py` from
  `realm/values.toml` (written by cruft); roles, groups, scopes, clients and
  service accounts are modelled in separate modules, built-in scopes come
  from a data file per Keycloak version. The file is committed and checked
  by the instance CI, together with `realm/OVERVIEW.md`, a generated
  overview of the realm as Markdown tables.
- `ifdd_public` (signed in, no further rights) is in the default role and
  reaches the tokens of the backend client; redundant session note mappers
  removed; oauth2-proxy redirect URIs from `ifdd_keycloak_proxy_gate_hosts`.
