(ifdd-keycloak-security)=
# Security

Keycloak decides who signs in and which roles their tokens carry. Every
service of the node trusts its tokens, so a weakness here is a weakness
everywhere.

## Transport and proxy

- TLS ends at the proxy. Keycloak serves plain HTTP inside
  (`KC_HTTP_ENABLED`) and builds its public URLs from
  `KC_HOSTNAME=https://{{ cookiecutter.ifdd_keycloak_host }}`; the issuer of
  the tokens is therefore `{{ cookiecutter.ifdd_oidc_realm }}`.
- `KC_PROXY_HEADERS=xforwarded`: Keycloak takes client address and scheme
  from the `X-Forwarded-*` headers. It trusts them from every container on
  `{{ cookiecutter.ifdd_proxy_network }}`; `KC_PROXY_TRUSTED_ADDRESSES` can
  restrict this once the address range of that network is fixed.
- The router attaches `security-headers` of the proxy only, no `csp-*`:
  Keycloak sets its own Content-Security-Policy for the admin console and
  the login pages, which the strict `csp-api` would break.
- The realm requires TLS for external addresses (`sslRequired: external`).

## Administration

- The admin from `.env` (`IFDD_KEYCLOAK_ADMIN_USER`) is a temporary
  bootstrap admin of the master realm. Create a permanent admin, then delete
  it.
- The admin console is reachable through the proxy like everything else, at
  `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/`. Protect the admin
  accounts accordingly.
- The client `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` holds
  `manage-users` of `realm-management`: whoever has its secret can create,
  change, disable and delete users, put anyone into any group (including
  `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}`) and create groups. Keep
  its secret like an admin password.

## Secrets

| Secret | Where | Note |
|---|---|---|
| admin password | `.env` | for the first start only |
| database password | `.env` | set once; the database keeps it |
| client secrets | `.env`, then in Keycloak and in the services | read by the first import; rotate in the admin console |
| database dumps | `backups/` | hold password hashes, sessions and the client secrets of the database; mode 0700, owned by the backup user |

`.env` is created with generated values (32 to 48 characters with lower and
upper case letters and digits), is never committed and is on the skip
list. The compose files require every secret (`${...:?}`): an unset variable
would otherwise become the literal secret in the realm. `realm/` holds no
passwords and no personal users. `backups/` is not committed either; a copy
of it on another system needs the same protection as the database.

## Rules of the realm

The realm follows RFC 9700 (OAuth 2.0 Security Best Current Practice):

| Topic | Rule |
|---|---|
| public client `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | authorization code with PKCE S256 required, no implicit flow; exact redirect URIs, no patterns |
| confidential clients for scripts and ct | client credentials only, no browser login, no password grant |
| offline tokens | no client offers the scope `offline_access` |
| audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}` | only in the tokens of the clients that call the backend |
| full scope | off for the backend client, ts, ct and the user admin client; they get scope mappings for the roles they need |
| rights | the default role only grants `{{ cookiecutter.ifdd_keycloak_role_public }}`; reading, writing and privileged access come from groups |
| refresh tokens | rotated: each is valid once |
| logins | brute force protection with Keycloak's thresholds; password policy: at least 12 characters, not the user name |
| events | login events kept 30 days; admin events without representations |

The tests of the template check these rules in the generated realm file.
Details per client are in {ref}`ifdd-keycloak-realm` and in
`realm/OVERVIEW.md`.

## Containers

Keycloak runs with all capabilities dropped (`cap_drop: ALL`) and
`no-new-privileges`, PostgreSQL with `no-new-privileges`. PostgreSQL is only
on the network `db`, which the proxy does not reach. The backup service runs
as the host user of `IFDD_KEYCLOAK_BACKUP_UID`, not as root, without
capabilities and with `no-new-privileges`, on the network `db` only; it
knows the database password.

The management port 9000 (`/health`, `/metrics`) is not routed by the proxy,
but containers on the same networks can reach it.
