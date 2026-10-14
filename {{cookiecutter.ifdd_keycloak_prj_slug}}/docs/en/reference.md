(ifdd-keycloak-reference)=
# Reference

The variables of the template and their values in this instance are listed
in {ref}`ifdd-instances-keycloak`. This page lists what is not a template
variable.

## Layout

| Path | Purpose |
|---|---|
| `docker-compose-production.yml` | Keycloak behind the proxy, PostgreSQL |
| `docker-compose-development.yml` | `start-dev` on 127.0.0.1, without the proxy |
| `dotenv.dist` → `.env` | generated secrets and the host, never committed |
| `realm/values.toml` | values of the realm, written by cruft |
| `realm/build_realm.py`, `realm/ifdd_realm/` | the script and its model |
| `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json` | generated import file, mounted read-only into Keycloak |
| `realm/OVERVIEW.md` | generated: the realm as tables |

## Environment (`.env`)

| Variable | Default here | Used by |
|---|---|---|
| `IFDD_KEYCLOAK_HOST` | `{{ cookiecutter.ifdd_keycloak_host }}` | router rule, `KC_HOSTNAME` |
| `IFDD_KEYCLOAK_DEV_PORT` | `{{ cookiecutter.ifdd_keycloak_dev_port }}` | development port on 127.0.0.1 |
| `IFDD_KEYCLOAK_ADMIN_USER`, `IFDD_KEYCLOAK_ADMIN_PASSWORD` | `{{ cookiecutter.ifdd_keycloak_admin_user }}`, generated | temporary admin of the master realm, first start only |
| `IFDD_KEYCLOAK_DB_PASSWORD` | generated | PostgreSQL and Keycloak |
| `IFDD_KEYCLOAK_API_CLIENT_SECRET` | generated | client `{{ cookiecutter.ifdd_keycloak_api_client_id }}` |
| `IFDD_KEYCLOAK_CT_CLIENT_SECRET` | generated | client `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` |
| `IFDD_KEYCLOAK_USERADMIN_CLIENT_ID`, `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` | `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}`, generated | client `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}`; the ID is for the scripts of the meta repository |
| `IFDD_KEYCLOAK_TS_CLIENT_SECRET` | generated | client `{{ cookiecutter.ifdd_ts_oidc_client_id }}` |
| `IFDD_KEYCLOAK_PROXY_CLIENT_SECRET` | generated | client `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` |

The client secrets reach the Keycloak container as environment variables of
the same name; the realm file refers to them as placeholders.

## Endpoints

| Endpoint | URL |
|---|---|
| issuer | `{{ cookiecutter.ifdd_oidc_realm }}` |
| discovery | `{{ cookiecutter.ifdd_oidc_realm }}/.well-known/openid-configuration` |
| authorization | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/auth` |
| token | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/token` |
| signing keys (JWKS) | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/certs` |
| userinfo | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/userinfo` |
| admin console | `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` |

## Containers, ports and networks

| Container | Port | Network |
|---|---|---|
| `keycloak` | 8080 HTTP (routed by the proxy), 9000 management (`/health`, `/metrics`, not routed) | `db`, `{{ cookiecutter.ifdd_proxy_network }}` |
| `postgres` | 5432 | `db` |

| Volume | Content |
|---|---|
| `postgres-data` | the database, mounted at `/var/lib/postgresql` (PostgreSQL 18 keeps its data in a versioned subdirectory) |

Labels: the router `{{ cookiecutter.ifdd_keycloak_prj_slug }}` with the rule
`Host(<IFDD_KEYCLOAK_HOST>)`, service port 8080, middleware
`security-headers@file`, network `{{ cookiecutter.ifdd_proxy_network }}`.
