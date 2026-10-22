(ifdd-keycloak-index)=
# {{ cookiecutter.ifdd_keycloak_prj_name }} (keycloak)

The identity provider of an IFDD node: Keycloak with its own PostgreSQL,
behind the proxy. It holds the realm with the clients of the IFDD services,
signs people and service accounts in and issues the access tokens that the
backend and the other services check. This chapter describes the instance
`{{ cookiecutter.ifdd_keycloak_prj_slug }}`, generated from the template
`ifdd-de/keycloak`, from the point of view of the people who set it up, run
and secure it.

| | |
|---|---|
| Public URL | `https://{{ cookiecutter.ifdd_keycloak_host }}` (routed by the proxy) |
| Realm | `{{ cookiecutter.ifdd_keycloak_realm }}`, issuer `{{ cookiecutter.ifdd_oidc_realm }}` |
| Admin console | `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` |
| Images | `{{ cookiecutter.ifdd_keycloak_image }}`, `{{ cookiecutter.ifdd_keycloak_postgres_image }}`, `{{ cookiecutter.ifdd_keycloak_backup_image }}` (upstream, no image of its own) |
| Network | `{{ cookiecutter.ifdd_proxy_network }}` (proxy) and `db` (Keycloak, PostgreSQL and the backup service only) |
| Development | `http://127.0.0.1:{{ cookiecutter.ifdd_keycloak_dev_port }}/admin/` |

## What the instance contains

Two compose files, `.env` with generated secrets, and the realm: the import
file `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json`, the
script that generates it from `realm/values.toml`, and `realm/OVERVIEW.md`,
the realm as tables. Keycloak imports the realm on its first start only;
afterwards its database is authoritative ({ref}`ifdd-keycloak-realm`). A
backup service dumps that database on a schedule into `backups/`, and
`adm_backup_restore.sh` restores a dump ({ref}`ifdd-keycloak-operations`).

## Architecture

```{mermaid}
flowchart LR
  Browser -->|HTTPS| Proxy[proxy: Traefik]
  Services[be, ct, ts, oauth2-proxy, scripts] -->|"{{ cookiecutter.ifdd_keycloak_host }}"| Proxy
  Proxy -->|HTTP 8080| KC[keycloak]
  KC -->|db network| PG[(PostgreSQL)]
  BK[backup] -->|db network| PG
  BK -->|dumps| DIR[(backups directory)]
```

TLS ends at the proxy; Keycloak serves plain HTTP inside and takes the public
URL from `KC_HOSTNAME`. Services reach it under its public host name too:
inside the proxy network that name is a network alias of Traefik.

| Who | Client | Uses Keycloak for |
|---|---|---|
| ui (browser) | `{{ cookiecutter.ifdd_oidc_backend_client_id }}` (public) | login with authorization code and PKCE |
| be | `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | checking access tokens (signing keys, issuer, audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}`); "Authorize" in its Swagger UI |
| ct | `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | client credentials for writing |
| ts (Grafana) | `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | login of people, client credentials |
| proxy (oauth2-proxy) | `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | the login gate in front of services without a login of their own |
| wf, scripts | `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | client credentials for reading |
| user scripts of the meta repository | `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | creating users and putting them into groups |

## Chapters

```{toctree}
:maxdepth: 2

setup
build-release
operations
security
troubleshooting
reference
realm
```

The values of the variables of this instance and how they relate to the
other services are listed in the chapter on the service instances
({ref}`ifdd-instances-keycloak`).
