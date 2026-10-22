# ifdd-de/keycloak

cookiecutter/cruft template for the identity provider of IFDD: Keycloak with
its own PostgreSQL, behind the `ifdd-de/proxy` instance of the same
`cookiecutter_all.yaml` (network `ifdd_proxy_network`). The realm with the
clients of the IFDD services is created once by Keycloak's start import
(`--import-realm`); afterwards the database is authoritative (keep it simple:
no reconciliation tool).

The realm import file is generated: cruft writes `realm/values.toml`, and the
post-generation hook runs `realm/build_realm.py`, which turns it into
`realm/import/<realm>-realm.json`. The script models roles, groups, scopes,
clients and service accounts in separate modules and stays in the instance,
so the file can be rebuilt and reviewed there.

The generated instance runs upstream images only (no image of its own, no
`release.yml`). See the instance documentation (`docs/`) for setup and
operation.

## Generate an instance

```bash
cruft create --no-input --checkout <tag> \
  --config-file cookiecutter_all.yaml \
  --skip .env \
  --output-dir ../instances https://github.com/ifdd-de/keycloak
```

`.env` holds the generated secrets; the skip list keeps it out of every
later `cruft update`. Run it as the user who is to own the database dumps,
not as root (see "Backup and restore").

## Variables

Variables without the `ifdd_keycloak_` prefix are the shared ones of
`cookiecutter_all.yaml`; with them the realm matches what the other services
expect without repeating values.

| Variable | Default | Meaning |
|---|---|---|
| `ifdd_keycloak_prj_name`, `ifdd_keycloak_prj_slug` | `IFDD Keycloak`, derived | name, also the title of the login pages (`display_name` in `realm/values.toml`); the slug names the directory and the Traefik router |
| `ifdd_keycloak_image` | `quay.io/keycloak/keycloak:26.8.0` | Keycloak image; its tag selects the built-in scopes (`realm/ifdd_realm/builtin/keycloak-<tag>.json`) |
| `ifdd_keycloak_postgres_image` | `postgres:18` | PostgreSQL image (Keycloak 26.8 supports 14 to 18) |
| `ifdd_keycloak_backup_image` | `prodrigestivill/postgres-backup-local:18` | image of the backup service; its tag must start with the major version of the PostgreSQL image |
| `ifdd_keycloak_backup_schedule` | `@daily` | when the backup service dumps the database: a cron expression (five fields, or six with seconds first) or a descriptor such as `@daily`, `@every 6h` |
| `ifdd_keycloak_backup_timezone` | `UTC` | time zone of the schedule and of the dates in the file names |
| `ifdd_keycloak_backup_keep_days`, `_keep_weeks`, `_keep_months` | `7`, `4`, `6` | how long the daily, weekly and monthly dumps are kept |
| `ifdd_oidc_realm` | `https://keycloak.example.org/realms/ifdd` | realm URL the services use (issuer) |
| `ifdd_keycloak_host`, `ifdd_keycloak_realm` | derived from `ifdd_oidc_realm` | public host (default for `IFDD_KEYCLOAK_HOST`) and realm name |
| `ifdd_keycloak_dev_port` | `8096` | port on 127.0.0.1 in development |
| `ifdd_keycloak_admin_user` | `admin` | temporary admin of the master realm |
| `ifdd_proxy_network` | `proxy-net` | network of the proxy (the same instance as for the other services) |
| `ifdd_oidc_backend_client_id` | `ifdd` | public client of ifdd-ui and ifdd-be |
| `ifdd_oidc_jwks_audience` | = backend client | audience ifdd-be checks; added to the tokens of all service clients |
| `ifdd_be_url`, `ifdd_ui_url` | `https://be.example.org`, `https://ui.example.org` | redirect URIs of the backend client; no trailing slash |
| `ifdd_be_role_nodes_read` | `ifdd_nodes_ro` | read role (realm and backend client role, also the client scope that adds the audience) |
| `ifdd_keycloak_role_nodes_write`, `ifdd_keycloak_role_public`, `ifdd_keycloak_role_nodes_priv` | `ifdd_nodes_rw`, `ifdd_public`, `ifdd_nodes_priv` | further node roles (realm and backend client roles) |
| `ifdd_keycloak_group_nodes_readers`, `_writers`, `_privileged` | `ifdd_nodes_readers`, `ifdd_nodes_writers`, `ifdd_nodes_privileged` | groups granting read, read and write, read and privileged |
| `ifdd_keycloak_api_client_id` | `ifdd-api-script` | confidential client for scripts |
| `ifdd_keycloak_ct_client_id` | `ifdd-ct` | ifdd-ct, client credentials, has the write role |
| `ifdd_keycloak_useradmin_client_id` | `ifdd-user-admin` | client credentials for scripts that create users and add them to groups (see below) |
| `ifdd_ts_oidc_client_id`, `ifdd_ts_host` | `ifdd-ts`, `ts.example.org` | Grafana of ifdd-ts (redirect `https://<host>/login/generic_oauth`) |
| `ifdd_ts_role_admin`, `_editor`, `_viewer` | `admin`, `readwrite`, `readonly` | realm roles for Grafana Admin, Editor, Viewer |
| `ifdd_ts_api_oidc_client_id` | `ifdd-ts-api` | client of ifdd-ts-api: carries its roles, audience of its tokens, no login |
| `ifdd_ts_api_role_read`, `ifdd_ts_api_role_write` | `ifdd_ts_ro`, `ifdd_ts_rw` | client roles of that client: read and write samples (no dot) |
| `ifdd_keycloak_ts_ingest_client_id` | `ifdd-ts-ingest` | client credentials for services that write samples through ifdd-ts-api |
| `ifdd_proxy_oidc_client_id`, `ifdd_wf_host` | `ifdd-proxy`, `wf.example.org` | oauth2-proxy of ifdd-proxy (redirect `https://<wf host>/oauth2/callback`) |
| `ifdd_keycloak_wf_admin_group` | `ifdd_wf_admins` | group admitted to ifdd-wf; keep equal to `ifdd_wf_sso_group` |
| `ifdd_keycloak_proxy_gate_hosts` | `ifdd_wf_host` | comma-separated hosts behind the oauth2-proxy gate (its redirect URIs) |
| `ifdd_context_root` | `ifdd.de` | root of the context names: a context pattern (client role of the backend client) for every domain context, its group `ifdd_ctx_<root>`, and granted to the service accounts of api, ct and ts |

The pre-generation hook rejects values that would render but not work (realm
or host not matching `ifdd_oidc_realm`, trailing slashes, duplicate client or
role names, quotes in names). Do not put `_copy_without_render` into
`cookiecutter_all.yaml`.

## The realm script

```
realm/
  values.toml            values, written by cruft (edit, then rebuild)
  values_<x>.toml        optional: further realms, copies of values.toml
  build_realm.py         python3 realm/build_realm.py [--check] [--values FILE ...]
  ifdd_realm/            the model, standard library only (Python >= 3.11)
    values.py            values.toml as typed data classes
    roles.py groups.py scopes.py clients.py users.py
    mappers.py           audience and group membership mappers
    realm.py             realm settings and assembly
    validate.py          consistency checks before writing
    overview.py          OVERVIEW.md: the realm as tables
    model.py             data classes and their Keycloak JSON form
    builtin/keycloak-26.8.0.json   Keycloak's built-in client scopes
  import/<realm>-realm.json        generated, committed, mounted into Keycloak
  OVERVIEW.md                      generated, committed: settings, roles, groups,
                                   scopes, clients, service accounts as tables
  OVERVIEW-<realm>.md              generated for each further values file
themes/ifdd/login/                login theme (styles on top of keycloak.v2),
                                   copied without rendering, mounted read-only
```

Further values files give further import files for a one-off import:
`python3 realm/build_realm.py --values realm/values_aa.toml realm/values_dd.toml`
writes `import/<realm>-realm.json` and `OVERVIEW-<realm>.md` for each, named
after `[realm] name`. The script never removes files of other realms; it
lists them. `--check` covers only the given values files. All realm files
share the client secret placeholders of `.env`.

The instance CI runs `build_realm.py --check`, so a change to `values.toml`
or `ifdd_realm/` without the rebuilt files fails. `OVERVIEW.md` is rendered
from the finished realm, so it cannot disagree with the import file; in a
review, a changed client or role shows up as a changed table row. A template update through
cruft brings the new script and the regenerated file in one diff.

Origin: a partial export of Keycloak 26.5.0, compared with a fresh realm of
26.8.0; only what differs is modelled, then revised in the review of
2026-10-03 (following RFC 9700, OAuth 2.0 Security Best Current Practice):

| Topic | Rule |
|---|---|
| Backend client (public, ifdd-ui) | code flow with PKCE S256 required, no implicit flow; redirects exactly `/authentication/callback` and `/authentication/silent-callback` of the UI and `/docs/oauth2-redirect` of the backend (Swagger UI "Authorize"); no patterns |
| Script client | client credentials only (no browser login, no password grant); keeps refresh tokens for client credentials |
| Offline tokens | no client offers the scope `offline_access` |
| Backend audience | only for the clients that call ifdd-be, no longer a realm default |
| Full scope | off for ifdd-ts and ifdd-ct, which get scope mappings for the roles they need |
| Rights | node roles as realm roles and as client roles of the backend client (ifdd-be and ifdd-ui check `resource_access`); the default role only grants `ifdd_public`; reading, writing and privileged access come from groups |
| Roles for ifdd-ui | the backend client's own client roles also in the ID token and the userinfo response (mapper on the client); the access token is unchanged, ifdd-be keeps reading it and accepts only access tokens (`typ` = `Bearer`) |
| Realm | refresh token rotation, brute force protection, password policy (12 characters, not the user name), login events (30 days), admin events without representations; token lifespans unchanged |

## Context patterns

ifdd-be-core gives domain contexts (dotted names such as
`sub1.dom1.ifdd.de`) only to clients with a matching **context pattern**:
a client role of the backend client whose name has a dot ("Contexts and
access" in `ifdd-be-core`). Base and aspect contexts need no pattern.

The realm brings one pattern, `ifdd_context_root` (default `ifdd.de`): a
client role only (no realm role), the group `ifdd_ctx_<root>` that grants it,
and the service accounts of api, ct and ts hold it (ct and ts with a scope
mapping, as their full scope is off). People get patterns only through
groups, together with a node group for read or write. Further patterns, each
with its group `ifdd_ctx_<pattern>`, are created in a running realm with
`keycloak_add_context_role.py` of the meta repository.

## The user admin client

`ifdd_keycloak_useradmin_client_id` is a confidential client with client
credentials only, for scripts that create users, set their passwords and add
them to existing groups (`keycloak_add_user.py`, which reads the client id
and secret from the instance's `.env`). Its service account gets, of
Keycloak's own client `realm-management`, the role `manage-users` and
nothing else; full scope is off, with a scope mapping for that role, so its
tokens carry only this role. `validate.py` knows `manage-users` as the only
built-in client role the realm may grant.

`manage-users` is broader than the script: whoever holds the secret can put
any user into any group (including the wf admin group), change, disable and
delete users, and create groups. Guard the secret like an admin password.

## Backup and restore

The production compose file has a service `backup` with the image
`prodrigestivill/postgres-backup-local`
([docker-postgres-backup-local](https://github.com/prodrigestivill/docker-postgres-backup-local),
MIT license). It runs `pg_dump` of the database on the schedule
`ifdd_keycloak_backup_schedule` and on every start, and keeps daily, weekly
and monthly dumps for the times of the `ifdd_keycloak_backup_keep_*`
variables. Its image is built on the official PostgreSQL image, so its
`pg_dump` has the version of its tag; the pre-generation hook requires the
same major version as `ifdd_keycloak_postgres_image`. Its health check is set
in the compose file: the image's own check probes first after 5 minutes,
longer than `up --wait` of the meta repository allows; a start interval of
5 s (Docker Engine 25 or later) makes the service healthy at once, and the
scheduler answers 503 after a failed dump. The development compose file has
no backup service.

The dumps go to `backups/` of the instance, a bind mount, not a Docker
volume. The service runs as the user and group of
`IFDD_KEYCLOAK_BACKUP_UID` and `IFDD_KEYCLOAK_BACKUP_GID` in `.env`, so the
dumps belong to a user of the host. The post-generation hook writes the ids
of the user who generates the instance (`<<host:uid>>`, `<<host:gid>>` in
`dotenv.dist`), refuses to run as root, and creates `backups/` with mode
0700. Compose does not create a missing `backups/`
(`create_host_path: false`), because Docker would create it for root.
`backups/` is in the instance's `.gitignore`.

`adm_backup_restore.sh DUMP_FILE` restores a dump: it checks the file, asks
to type `restore`, stops Keycloak and the backup service, saves the current
database to `backups/pre-restore/`, recreates the database, loads the dump
and starts both again. The instance documentation (page `operations`)
describes both.

Existing instances get the service with `cruft update`, but `.env` is on the
skip list and Git keeps no empty directory: add `IFDD_KEYCLOAK_BACKUP_UID`
and `IFDD_KEYCLOAK_BACKUP_GID` (values of `id -u` and `id -g`) to `.env`, and
create `backups/` with `mkdir -m 700 backups`.

## Documentation of the instance (`docs/`)

Every instance carries its operating documentation as Sphinx sources in
MyST Markdown, in English (`docs/en`) and German (`docs/de`), with the same
files, labels and headings in both. The pages follow the work around the
service: `index` (purpose, architecture), `setup`, `build-release`,
`operations`, `security`, `troubleshooting`, `reference`, plus `realm` (the
model, roles, groups, clients, context patterns, and the changes existing
realms need). cookiecutter fills in the values of the instance; the full
tables of the generated realm stay in `realm/OVERVIEW.md`. The instance
README is only an entry point that links to them.

The pages have no `conf.py` of their own: they are meant to be copied into a
Sphinx project that documents all services. That project needs `myst_parser`
and `sphinxcontrib.mermaid`. Labels start with `ifdd-keycloak-`; references
to `ifdd-instances-keycloak` (the instance chapter of the meta repository)
resolve only there.

Rules for editing the pages in the template:

- change both languages in the same commit;
- no Jinja syntax in examples (`{{`, `{%`, `{#`); wrap such text in
  `{% raw %}`;
- do not write the text `cookiecutter` followed by a dot literally; it would
  look like an unrendered placeholder.

`tests/check_docs.py` checks a rendered instance: same files, labels and
headings per level in both languages, every label with the prefix, every
reference to an own label resolvable, and a Sphinx build of each language
with `-W` (configuration `tests/docs/conf.py`, versions
`tests/docs/requirements.txt`). `template-test.yml` runs it for every
fixture.

## Tests

```bash
pytest -q tests                      # render fixtures, build, validate, hooks, compose
IFDD_UPDATE_GOLDEN=1 pytest -q tests # after an intended change of the realm
```

`tests/golden/` holds the realm files and overviews of the fixtures.

Run the tests as a normal user: as root, the post-generation hook refuses to
generate an instance (see "Backup and restore"), so every rendering fails.

## AI assistance

Some parts of this repository, in particular the tests, the test data and the
documentation, were developed or improved with the help of large language
models (LLMs). All changes were reviewed and released by the maintainer.
