(ifdd-keycloak-setup)=
# Setup

## Prerequisites

| What | Why |
|---|---|
| Docker with Compose | Keycloak and PostgreSQL run as two containers |
| the external network `{{ cookiecutter.ifdd_proxy_network }}` and a running proxy instance | Traefik routes `{{ cookiecutter.ifdd_keycloak_host }}` to Keycloak by the labels of this service |
| the proxy's certificate covers `{{ cookiecutter.ifdd_keycloak_host }}` | with own certificates the host must be among its names (`adm_01_certs.sh` of the proxy takes `ifdd_proxy_internal_hosts`) |
| the proxy lists `{{ cookiecutter.ifdd_keycloak_host }}` in `ifdd_proxy_internal_hosts` | services call Keycloak under its public host; inside the containers that name must lead to Traefik |

## Create the instance

Usually the meta repository creates every instance in one go
(`.adm_meta_01_all.sh`, step `.adm_01_create_services.sh`): it runs
`cruft create` with the shared variable file `.cookiecutter_all.yaml` and
afterwards copies the client secrets from this `.env` to the services that
use them.

By hand, from the directory that holds the instances:

```bash
cruft create --no-input --config-file .cookiecutter_all.yaml \
  --skip .env \
  https://github.com/ifdd-de/keycloak
```

`.env` holds the generated secrets; the skip list keeps it out of every
later `cruft update`.

## Configuration and secrets

The post-generation hook writes `.env` from `dotenv.dist` (an existing
`.env` is never touched) and replaces every placeholder by a random value:

| Entry | Content |
|---|---|
| `IFDD_KEYCLOAK_ADMIN_PASSWORD` | password of the temporary admin `IFDD_KEYCLOAK_ADMIN_USER` of the master realm |
| `IFDD_KEYCLOAK_DB_PASSWORD` | password of the database user `keycloak` |
| `IFDD_KEYCLOAK_*_CLIENT_SECRET` | the secrets of the confidential clients, read by the realm import |
| `IFDD_KEYCLOAK_BACKUP_UID`, `IFDD_KEYCLOAK_BACKUP_GID` | user and group id of the user who generates the instance; the backup service writes the dumps as that user |

It creates the directory `backups/` (mode 0700) for the dumps of the backup
service. As root the hook stops: the dumps would belong to root. Generate the
instance as the user who is to own them.

Then it runs `realm/build_realm.py`, which writes
`realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json` and
`realm/OVERVIEW.md` from `realm/values.toml`. Every other value comes from
the variables of the template; they are listed with their values and
meaning in {ref}`ifdd-instances-keycloak`. The entries of `.env` are listed
in {ref}`ifdd-keycloak-reference`.

## First start

```bash
docker compose -f docker-compose-production.yml up -d
docker compose -f docker-compose-production.yml logs -f keycloak
```

The first start builds Keycloak and imports the realm; the log reports
`Realm '{{ cookiecutter.ifdd_keycloak_realm }}' imported`. The health check
allows 180 seconds for it.

Then sign in to `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` with
`IFDD_KEYCLOAK_ADMIN_USER` and `IFDD_KEYCLOAK_ADMIN_PASSWORD` from `.env`.
That admin is temporary: create a permanent admin in the master realm, then
delete the temporary one.

## Client secrets for the services

Each confidential client has its secret in `.env`. The meta repository copies
them; by hand:

| Client | Service | Secret in this `.env` | Goes to |
|---|---|---|---|
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | wf, scripts | `IFDD_KEYCLOAK_API_CLIENT_SECRET` | `secrets/kestra.env` of wf (`IFDD_API_CLIENT_SECRET`), scripts |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | ct | `IFDD_KEYCLOAK_CT_CLIENT_SECRET` | `IFDD_CT_OIDC_CLIENT_SECRET` in the `.env` of ct |
| `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | `keycloak_add_user.py` of the meta repository | `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` | read from this `.env` |
| `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | ts (Grafana) | `IFDD_KEYCLOAK_TS_CLIENT_SECRET` | `secrets/oidc_client_secret` of ts |
| `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | proxy (oauth2-proxy) | `IFDD_KEYCLOAK_PROXY_CLIENT_SECRET` | `secrets/oauth2_proxy_client_secret` of the proxy |
| `{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` | services writing samples through ts-api | `IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET` | the service, by hand |

`{{ cookiecutter.ifdd_oidc_backend_client_id }}` is public and has no secret.
The import reads these secrets on the first start only; afterwards Keycloak
keeps its own copy ({ref}`ifdd-keycloak-operations`).

## People and groups

Create people in the admin console or with `keycloak_add_user.py` of the
meta repository, and put them into groups. A new user only has
`{{ cookiecutter.ifdd_keycloak_role_public }}` (signed in, no further
rights):

| Group | Rights |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` | read nodes |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_writers }}` | read and write nodes |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_privileged }}` | read and privileged access |
| `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}` | admitted to wf (login gate) |
| `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}` | every domain context (context pattern `{{ cookiecutter.ifdd_context_root }}`); together with a node group |

Base and aspect contexts need only a node group. A domain context such as
`sub1.dom1.{{ cookiecutter.ifdd_context_root }}` also needs a context pattern;
groups for further patterns are created with `keycloak_add_context_role.py`
of the meta repository ({ref}`ifdd-keycloak-realm`).

For Grafana assign the realm roles `{{ cookiecutter.ifdd_ts_role_admin }}`,
`{{ cookiecutter.ifdd_ts_role_editor }}` or `{{ cookiecutter.ifdd_ts_role_viewer }}`.
Keycloak asks for e-mail, first and last name at the first login if a user
lacks them. The login gate of the proxy only admits users whose e-mail
address is marked as verified.

## Local development

```bash
docker compose -f docker-compose-development.yml up -d
```

The admin console is at
`http://127.0.0.1:{{ cookiecutter.ifdd_keycloak_dev_port }}/admin/`
(`IFDD_KEYCLOAK_DEV_PORT`): `start-dev`, plain HTTP, no proxy, the same
database volume and realm import. The redirect URIs of the realm name the
production hosts, so the other services cannot sign in against it.
