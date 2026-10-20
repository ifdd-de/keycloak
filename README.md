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
later `cruft update`.

## Variables

Variables without the `ifdd_keycloak_` prefix are the shared ones of
`cookiecutter_all.yaml`; with them the realm matches what the other services
expect without repeating values.

| Variable | Default | Meaning |
|---|---|---|
| `ifdd_keycloak_prj_name`, `ifdd_keycloak_prj_slug` | `IFDD Keycloak`, derived | name, also the title of the login pages (`display_name` in `realm/values.toml`); the slug names the directory and the Traefik router |
| `ifdd_keycloak_image` | `quay.io/keycloak/keycloak:26.8.0` | Keycloak image; its tag selects the built-in scopes (`realm/ifdd_realm/builtin/keycloak-<tag>.json`) |
| `ifdd_keycloak_postgres_image` | `postgres:18` | PostgreSQL image (Keycloak 26.8 supports 14 to 18) |
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

Checked against Keycloak 26.8.0 (start import, real code flow with PKCE,
client credentials, admin API): 28 checks, including refused requests
without PKCE, with `response_type=token`, with other redirects, with the
password grant and with `scope=offline_access`; roles in the tokens for
users without group and in each node group and for each service account;
rejected reuse of a refresh token; lockout after quick failures; stored
login and admin events.

Found while testing against Keycloak 26.8.0 (start import):

- A `js` policy stops the server and rolls back the whole import.
- A `clientScopes` list without the built-in scopes makes Keycloak create
  none of them; hence the data file per Keycloak version.
- Without `defaultRole` Keycloak creates `default-roles-<realm>-1`.
- Keycloak adds `offline_access`, `uma_authorization` and two account roles
  to the default role on import.
- An unset `${VAR}` stays literal; the compose files require each secret.
- The built-in scope `roles` puts the client roles (`resource_access`) into
  the access token only; the backend client therefore has its own mapper for
  ID token and userinfo, which ifdd-ui reads (`user.profile`).
- An ID token of the backend client carries the same `aud` as its access
  token; resource servers must tell them apart by `typ` (`ID` / `Bearer`).

Not verified: the container images themselves, PostgreSQL 18 (tests used 16).

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

Dotted names were checked against the Keycloak 26.8.0 distribution: a client
role `grid.example.ifdd.de` and a group `ifdd_ctx_grid.example.ifdd.de`
were created through the admin API, and a member's access token carried the
role in `resource_access.<backend client>.roles`. The realm of this template
(fixture `ifddtest`) was imported: the client-credentials tokens of
`ifdd-ct`, `ifdd-ts` and `ifdd-api-script` carry `ifdd.de` there, the token
of `ifdd-user-admin` does not.
The template tests (120) pass; the new ones (`test_context_root`,
`test_another_context_root`, three pre-hook cases) fail against the previous
template. Not checked: the container image.

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

### Honesty notes

Documentation `docs/` (2026-10-13): rendered with cookiecutter 2.7.1 for the
three fixtures and with the `cookiecutter_all.yaml` of the meta repository;
`tests/check_docs.py` passes for each (Sphinx 9.1.0, myst-parser 5.1.0,
sphinxcontrib-mermaid 2.1.1, Python 3.13), no rendered page contains a
placeholder, and the template tests pass (123). The workflow file passes
actionlint 1.7.12; the workflow itself has not run. Content: taken from the
previous instance README, this README, the compose files and the realm
model; what has not been tested is marked as such in the pages (backup and
restore, upgrades with existing data, the admin console steps for existing
realms). Also checked (2026-10-13): one Sphinx project per language with the
pages of all ten service templates (rendered with `cookiecutter_all.yaml`), the
instance chapter of the meta repository and ifdd-be-core with its OpenAPI
document builds with `-W` and no suppressed warnings, so every cross
reference resolves; the Mermaid diagrams of all services, and of the option
variants of the fixtures, render in headless Chromium 141.0.7390.37
(Playwright 1.56.0, Mermaid 11.12.1 served locally).

Backend redirect (2026-10-13): the realm file of `tests/fixtures/ifddtest.yaml`
with the exact redirect `https://rest/docs/oauth2-redirect` was imported into
the Keycloak 26.8.0 distribution (`start-dev`, behind Traefik v3.7.13);
"Authorize" in the Swagger UI of ifdd-be-core completed the code flow with
PKCE through that URI in headless Chromium. Not checked: the admin console
steps for an existing realm.

Tested against the Keycloak 26.8.0 distribution (`start-dev`, realm
imported from this template, admin REST API):

- `manage-users` alone is enough to find users and groups, create a user
  with a password, reset a password and add a user to a group. With
  `query-groups` alone, the group search returns an empty list; `view-users`,
  `query-users` and `query-groups` add nothing the script needs.
- The token of the client carries `resource_access.realm-management.roles =
  ["manage-users"]` and no realm roles; the password grant is refused.
- With `manage-users`, the client could also change, disable and delete a
  user and create a group (204/201); reading clients or realm roles was
  refused (403). Not tested: whether it can map roles to users or groups.
- Keycloak 26's declarative user profile requires e-mail, first and last
  name for users: a user created without them cannot finish a login before
  entering them ("Account is not fully set up" for the password grant).
- The `kcadm.sh` commands for the user admin client in an existing realm
  (instance documentation, page `realm`) were run with `kcadm.sh` of the distribution against
  `http://localhost:8080`; the result matched the imported client (same
  token content, password grant refused). Not tested: running them inside
  the container, with `KC_HOSTNAME` set.

Not verified: the container images.

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

Realm overview as a Sphinx page and role description (2026-10-14): rendered
with cookiecutter 2.7.1 for the three fixtures and the `cookiecutter_all.yaml`;
`realm/OVERVIEW.md` of each builds with Sphinx 9.1.0 and myst-parser 5.1.0
with `-W` on its own, and inside the full documentation of all services in en
and de; the `<br>` in table cells survive into the HTML. The template tests
(123) pass after regenerating the golden files; before, six golden
comparisons failed on the new label and the corrected description. The
description change is not checked against a running Keycloak (the
`ifddtest.json` golden file differs from the imported one only in that
text). The workflow passes actionlint 1.7.12; it has not run.

## Tests

```bash
pytest -q tests                      # render fixtures, build, validate, hooks, compose
IFDD_UPDATE_GOLDEN=1 pytest -q tests # after an intended change of the realm
```

`tests/golden/` holds the realm files and overviews of the fixtures; `ifddtest.json` is the
file that was imported into Keycloak 26.8.0 and checked with real tokens.

The login theme was checked with the realm of the fixture `ifddtest` in the
Keycloak 26.8.0 distribution, in `start-dev` and in `start` (dev-file database):
headless Chromium 141 (Playwright), light and dark mode, `ifdd.css` and the
parent's styles loaded, heading from the display name, no console errors. A
second realm without `loginTheme`, imported from a further values file, showed
the default theme. Not checked: the container image, the proxy in front, other
browsers, and the realm with real tokens after the change.
