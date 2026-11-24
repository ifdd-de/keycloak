(ifdd-keycloak-realm)=
# Realm
{%- set gate_hosts = cookiecutter.ifdd_keycloak_proxy_gate_hosts.split(",") | map("trim") | reject("equalto", "") | list %}

The realm `{{ cookiecutter.ifdd_keycloak_realm }}` is generated, not clicked
together: cruft writes `realm/values.toml` from the template variables, and
`realm/build_realm.py` turns it into the import file and `realm/OVERVIEW.md`.
Keycloak imports the file on its first start only.

`realm/OVERVIEW.md` shows the generated realm as tables: settings (token
lifespans, sessions, password policy, events), roles, groups, client scopes,
clients and service accounts. Start reading there; it is rendered from the
finished realm, so it cannot disagree with the import file.

The overview is also a page for Sphinx (MyST Markdown, English only, label
`ifdd-keycloak-realm-overview`). To show it in the full documentation, copy
`realm/OVERVIEW.md` into both language projects, for example as
`services/keycloak/realm-overview.md`, and add it to a toctree. Copy it again
after every rebuild.

## The model

Roles, groups, client scopes, clients and service accounts each have their
own module in `realm/ifdd_realm/`; `validate.py` checks the result before it
is written. Commit `values.toml`, the modules and the generated files
together. No personal users and no passwords belong there.

```bash
python3 realm/build_realm.py          # rebuild after editing values.toml or ifdd_realm/
python3 realm/build_realm.py --check  # what CI runs
```

## Login theme

The login pages use the theme `ifdd` from `themes/ifdd/`: Keycloak's
`keycloak.v2` theme with a plain background instead of the Keycloak
artwork, a neutral line above the card and the realm's display name as a
quiet heading. It changes styles only (`theme.properties`,
`resources/css/ifdd.css`); templates and texts come from `keycloak.v2`, so
an upgrade of Keycloak does not break the pages. Dark mode follows the
browser.

The realm selects the theme with `loginTheme`. The heading and the browser
title show `display_name` of the values file, here
`{{ cookiecutter.ifdd_keycloak_prj_name }}`. The directory belongs to the
template and arrives with `cruft update`. Keycloak caches themes outside
`start-dev`: restart Keycloak after a change.

## Further realms

`realm/values.toml` describes the realm of this instance. Further realms for
a one-off import are described by copies of it, for example
`realm/values_aa.toml`; change at least `name` and `display_name` under
`[realm]`:

```bash
python3 realm/build_realm.py --values realm/values_aa.toml realm/values_dd.toml
```

Each values file gives `realm/import/<name>-realm.json`, named after
`[realm] name`, and `realm/OVERVIEW-<name>.md`; `realm/values.toml` keeps
writing `realm/OVERVIEW.md`. Two values files with the same realm name stop
the script. The script never removes files of other realms; it only lists
them. At the next start Keycloak imports every file in `realm/import/` whose
realm does not exist yet and skips the others.

`--check` compares only the given values files (by default
`realm/values.toml`), so the CI passes with further realm files in
`realm/import/`. A file left over after renaming a realm is not reported
either; remove it yourself.

{%- set extra_realms = cookiecutter.ifdd_keycloak_extra_realms.split(",") | map("trim") | reject("equalto", "") | list %}
(ifdd-keycloak-realm-own-secrets)=
### Secrets of further realms

Every further realm takes client secrets of its own,
`IFDD_KEYCLOAK_<CLIENT>_CLIENT_SECRET_<SUFFIX>` in `.env`, where the suffix
is the realm name in capitals with every character other than letters and
digits as `_` (realm `example-b`: `_EXAMPLE_B`). Only the realm of
`realm/values.toml` (`{{ cookiecutter.ifdd_keycloak_realm }}`) keeps the names without suffix. So
knowing the secret of one realm does not open another one.

The realms are listed in `ifdd_keycloak_extra_realms`{% if extra_realms %}
(this instance: {% for r in extra_realms %}`{{ r }}`{{ ", " if not loop.last else "" }}{% endfor %}){% endif %}: for them
the post-generation hook generates the secrets into `.env`, and the compose
files hand them to Keycloak. `build_realm.py` refuses a further realm whose
secrets the compose files do not pass, and names the missing variables.

A values file outside `realm/`, for example in a private directory, works
the same way; its realm name decides:

```bash
python3 realm/build_realm.py --values ../private/values_example-b.toml --out ../private/
```

Copy the import files into `realm/import/` before the start.

To add a realm to an existing instance: `cruft update --variables-to-update
'{"ifdd_keycloak_extra_realms": "<all further realms>"}'`, then add its
variables to `.env` by hand (`.env` is on the skip list), each with a new
random value of 48 letters and digits, for example from
`python3 -c "import secrets,string; a=string.ascii_letters+string.digits; print(''.join(secrets.choice(a) for _ in range(48)))"`.

Hand each secret to the service of the server that uses this realm, for
example the secret of the proxy client to `secrets/oauth2_proxy_client_secret`
of the proxy on that server. The secrets travel between servers by hand;
use a channel that keeps them confidential.

## Roles

The node roles exist as realm roles and as client roles of the backend
client `{{ cookiecutter.ifdd_oidc_backend_client_id }}`; the backend and the
UI check the client roles (`resource_access`).

| Role | Meaning |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_role_public }}` | signed in, no further rights; the default role grants only this |
| `{{ cookiecutter.ifdd_be_role_nodes_read }}` | read nodes; also the client scope that adds the audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}` |
| `{{ cookiecutter.ifdd_keycloak_role_nodes_write }}` | write nodes |
| `{{ cookiecutter.ifdd_keycloak_role_nodes_priv }}` | privileged read access |
| `{{ cookiecutter.ifdd_context_root }}` | context pattern for every domain context below the root; client role only |
| `{{ cookiecutter.ifdd_ts_role_admin }}`, `{{ cookiecutter.ifdd_ts_role_editor }}`, `{{ cookiecutter.ifdd_ts_role_viewer }}` | Grafana Admin, Editor, Viewer (realm roles) |

## Groups

| Group | Grants |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}` |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_writers }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}`, `{{ cookiecutter.ifdd_keycloak_role_nodes_write }}` |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_privileged }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}`, `{{ cookiecutter.ifdd_keycloak_role_nodes_priv }}` |
| `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}` | membership only (claim `groups`), for the login gate of wf |
{%- if cookiecutter.ifdd_keycloak_lab_client_id %}
| `{{ cookiecutter.ifdd_keycloak_lab_users_group }}`, `{{ cookiecutter.ifdd_keycloak_lab_admins_group }}` | membership only (claim `groups`): may log in to lab, administers lab |
{%- endif %}
| `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}` | the context pattern `{{ cookiecutter.ifdd_context_root }}` |

## Clients

| Client | Type | Flows | Redirect URIs |
|---|---|---|---|
| `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | public | authorization code with PKCE S256 | `{{ cookiecutter.ifdd_ui_url }}/authentication/callback`, `{{ cookiecutter.ifdd_ui_url }}/authentication/silent-callback`, `{{ cookiecutter.ifdd_be_url }}/docs/oauth2-redirect` |
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | confidential | client credentials | none |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | confidential | client credentials | none |
| `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | confidential | client credentials | none |
| `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | confidential | authorization code with PKCE S256, client credentials | `https://{{ cookiecutter.ifdd_ts_host }}/login/generic_oauth` |
| `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | confidential | authorization code with PKCE S256 | {% for host in gate_hosts %}`https://{{ host }}/oauth2/callback`{{ ", " if not loop.last else "" }}{% else %}none{% endfor %} |
| `{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` | confidential | none (carries the roles of ts-api) | none |
| `{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` | confidential | client credentials | none |
{%- if cookiecutter.ifdd_keycloak_lab_client_id %}
| `{{ cookiecutter.ifdd_keycloak_lab_client_id }}` | confidential | authorization code with PKCE S256 | `https://{{ cookiecutter.ifdd_lab_host }}/hub/oauth_callback` |
{%- endif %}

The redirect URIs of the login gate come from
`ifdd_keycloak_proxy_gate_hosts`: one per host behind oauth2-proxy. Empty
means no host behind the gate: the client keeps its secret but has no
redirect URIs, so a login through it fails. Which
roles reach the tokens of each client, and what the service accounts hold,
is listed in `realm/OVERVIEW.md`.

{% if cookiecutter.ifdd_keycloak_lab_client_id -%}
### Sessions

The realm keeps an idle SSO session for 8 hours, because the hub of lab
(`{{ cookiecutter.ifdd_keycloak_lab_client_id }}`) keeps its sessions that
long (idle 8 h, at most 24 h): notebook work runs for hours, and the hub
renews the tokens. Keycloak refuses a client value above the realm's
(Keycloak 26.8.1), so the realm sets the upper bound and every other client
of this template keeps 30 minutes with a setting of its own
(`client.session.idle.timeout`). Keycloak's built-in clients (account
console) follow the realm.

The lab client has full scope: its tokens carry every role of the user,
also context patterns created later, because notebooks act in ifdd-be with
the rights of the person logged in. It carries the audience of ifdd-be and
the group claim.

{% endif -%}
## Context patterns

The backend gives domain contexts (dotted names such as
`sub1.dom1.{{ cookiecutter.ifdd_context_root }}`) only to clients with a
matching context pattern: a client role of the backend client whose name
has a dot. Base and aspect contexts need no pattern.

The realm brings one pattern, `{{ cookiecutter.ifdd_context_root }}`: a
client role only, the group `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}`
that grants it, and the service accounts of
`{{ cookiecutter.ifdd_keycloak_api_client_id }}`,
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` and
`{{ cookiecutter.ifdd_ts_oidc_client_id }}` hold it. People get patterns only
through groups, together with a node group. Further patterns, each with its
group `ifdd_ctx_<pattern>`, are created in a running realm with
`keycloak_add_context_role.py` of the meta repository.

## Time series API

ifdd-ts-api checks the client roles of its own client
`{{ cookiecutter.ifdd_ts_api_oidc_client_id }}`, which is also the audience of
its tokens. Nobody logs in with that client: no flow is enabled, and
Keycloak puts it into the `aud` of every token that holds one of its roles.
Its roles:

| Role | Meaning |
|---|---|
| `{{ cookiecutter.ifdd_ts_api_role_read }}` | read samples |
| `{{ cookiecutter.ifdd_ts_api_role_write }}` | write samples |
| `{{ cookiecutter.ifdd_context_root }}` | store pattern of the root: every store |

A further store pattern is a further client role with a dot, e.g.
`temperature.ops.example.ifdd.de` for that store only. The roles go to
service accounts only, never to groups (ts-api takes client credentials
only):

| Service account | Roles of `{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_write }}`, `{{ cookiecutter.ifdd_context_root }}` |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_write }}`, `{{ cookiecutter.ifdd_context_root }}` |
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_read }}`, `{{ cookiecutter.ifdd_context_root }}` |

`{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` and
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` have no full scope; the roles
are in their scope mappings too. Grafana (`{{ cookiecutter.ifdd_ts_oidc_client_id }}`)
gets none: it reads VictoriaMetrics directly.

## Changes to an existing realm

A realm imported by an older template does not get later changes from
`cruft update`. These are the changes that need the admin console.

### Adding the context root

A realm imported before the context patterns has neither the role
`{{ cookiecutter.ifdd_context_root }}` nor its group, and the service accounts
lack it: they then see no domain context. Create both with
`keycloak_add_context_role.py {{ cookiecutter.ifdd_context_root }}` of the meta
repository, then, in the admin console, assign the role of the client
`{{ cookiecutter.ifdd_oidc_backend_client_id }}` to the service accounts of
`{{ cookiecutter.ifdd_keycloak_api_client_id }}`,
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` and
`{{ cookiecutter.ifdd_ts_oidc_client_id }}`, and add it to the client scopes
("Dedicated scope", "Scope") of `{{ cookiecutter.ifdd_keycloak_ct_client_id }}`
and `{{ cookiecutter.ifdd_ts_oidc_client_id }}`.

### Login theme and title

A realm imported before the theme existed keeps Keycloak's default theme and
has no display name. In the admin console, open "Realm settings": under
"Themes" choose `ifdd` as login theme, under "General" set "Display name"
and "HTML display name" to `{{ cookiecutter.ifdd_keycloak_prj_name }}`. The
theme must be mounted: compose files of this template version, then restart
Keycloak.

```{note}
Not tested: these admin console steps. The theme itself was tested with a
newly imported realm.
```

### Restricting the backend redirect

A realm imported before 2026-10-13 lets the client
`{{ cookiecutter.ifdd_oidc_backend_client_id }}` redirect to every path below
`{{ cookiecutter.ifdd_be_url }}` (`{{ cookiecutter.ifdd_be_url }}/*`). Only the
Swagger UI of the backend uses it, and only
`{{ cookiecutter.ifdd_be_url }}/docs/oauth2-redirect`. In the admin console,
open Clients, `{{ cookiecutter.ifdd_oidc_backend_client_id }}`, Settings, and
replace the entry under "Valid redirect URIs" by that exact URI. Patterns let
an attacker choose where the authorization code goes within the host
(RFC 9700, section 2.1).

```{note}
Not tested: these admin console steps on an existing realm. The exact
redirect itself was tested with a newly imported realm.
```

### Adding the user admin client

A realm imported before the client
`{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` existed does not get it
from a `cruft update`, but the compose files require
`IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` from then on. Create the client with
`kcadm.sh` inside the running container, as an admin of the master realm:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} CLIENT={{ cookiecutter.ifdd_keycloak_useradmin_client_id }}
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
CID=$(kcadm create clients -r "$REALM" -i -s clientId="$CLIENT" -s name="IFDD User Admin" \
  -s publicClient=false -s serviceAccountsEnabled=true -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false -s fullScopeAllowed=false)
kcadm add-roles -r "$REALM" --uusername "service-account-$CLIENT" \
  --cclientid realm-management --rolename manage-users
RMID=$(kcadm get clients -r "$REALM" -q clientId=realm-management --fields id --format csv --noquotes)
kcadm create "clients/$CID/scope-mappings/clients/$RMID" -r "$REALM" \
  -b "[$(kcadm get "clients/$RMID/roles/manage-users" -r "$REALM")]"
kcadm get "clients/$CID/client-secret" -r "$REALM" --fields value --format csv --noquotes
rm /tmp/kcadm.config
exit
```

Put the printed secret into `.env`:

```text
IFDD_KEYCLOAK_USERADMIN_CLIENT_ID={{ cookiecutter.ifdd_keycloak_useradmin_client_id }}
IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET=<printed secret>
```

```{note}
Tested with `kcadm.sh` of the Keycloak 26.8.0 distribution against
`http://localhost:8080`; not tested inside the container and with
`KC_HOSTNAME` set.
```

### Admin API scope of the user admin client (Keycloak 26.8.2)

From Keycloak 26.8.2 on, the admin API accepts only tokens that carry the
built-in scope `kc-admin-api`. On the upgrade Keycloak creates the scope in
every realm and gives it to `admin-cli` and `security-admin-console`, but not
to `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}`: its tokens then get
401. A realm imported with this template version already has it; in a realm
imported before, or after creating the client as above, add it as a default
scope, as an admin of the master realm:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} CLIENT={{ cookiecutter.ifdd_keycloak_useradmin_client_id }}
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
CID=$(kcadm get clients -r "$REALM" -q clientId="$CLIENT" --fields id --format csv --noquotes)
SCOPE=$(kcadm get client-scopes -r "$REALM" --fields id,name --format csv --noquotes \
  | awk -F, '$2 == "kc-admin-api" {print $1}')
kcadm update "clients/$CID/default-client-scopes/$SCOPE" -r "$REALM"
rm /tmp/kcadm.config
exit
```

```{note}
Tested with `kcadm.sh` of the Keycloak 26.8.2 distribution against
`http://127.0.0.1:18180` and a realm imported by this template: without the
scope the token of the client got 401 from the admin API, after these
commands 200. Not tested: the upgrade of a running Keycloak from 26.8.1.
```

### Adding the clients of ts-api

A realm imported before ts-api existed lacks the clients
`{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` and
`{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}`, and the compose files
require `IFDD_KEYCLOAK_TSAPI_CLIENT_SECRET` and
`IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET` from then on. Create both clients and
grant the roles with `kcadm.sh` inside the running container, as an admin of
the master realm:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} API={{ cookiecutter.ifdd_ts_api_oidc_client_id }} INGEST={{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}
RO={{ cookiecutter.ifdd_ts_api_role_read }} RW={{ cookiecutter.ifdd_ts_api_role_write }} ROOT={{ cookiecutter.ifdd_context_root }}
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
id_of() { kcadm get clients -r "$REALM" -q clientId="$1" --fields id --format csv --noquotes; }
AID=$(kcadm create clients -r "$REALM" -i -s clientId="$API" -s name="IFDD Time Series API" \
  -s publicClient=false -s serviceAccountsEnabled=false -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false)
for role in "$RO" "$RW" "$ROOT"; do kcadm create "clients/$AID/roles" -r "$REALM" -s name="$role"; done
IID=$(kcadm create clients -r "$REALM" -i -s clientId="$INGEST" -s name="IFDD Time Series Ingest" \
  -s publicClient=false -s serviceAccountsEnabled=true -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false -s fullScopeAllowed=false)
grant() {  # client, role, role
  kcadm add-roles -r "$REALM" --uusername "service-account-$1" --cclientid "$API" \
    --rolename "$2" --rolename "$3"
  for role in "$2" "$3"; do   # scope mapping, for clients without full scope
    kcadm create "clients/$(id_of "$1")/scope-mappings/clients/$AID" -r "$REALM" \
      -b "[$(kcadm get "clients/$AID/roles/$role" -r "$REALM")]"
  done
}
grant "$INGEST" "$RW" "$ROOT"
grant {{ cookiecutter.ifdd_keycloak_ct_client_id }} "$RW" "$ROOT"
grant {{ cookiecutter.ifdd_keycloak_api_client_id }} "$RO" "$ROOT"
kcadm get "clients/$AID/client-secret" -r "$REALM" --fields value --format csv --noquotes
kcadm get "clients/$IID/client-secret" -r "$REALM" --fields value --format csv --noquotes
rm /tmp/kcadm.config
exit
```

Put the two printed secrets into `.env`, in this order:

```text
IFDD_KEYCLOAK_TSAPI_CLIENT_SECRET=<first secret>
IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET=<second secret>
```

The scope mapping of `{{ cookiecutter.ifdd_keycloak_api_client_id }}` is not
needed (it has full scope) and does no harm.

```{note}
Tested with `kcadm.sh` of the Keycloak 26.8.0 distribution against
`http://localhost:8080` and a realm imported from the previous template;
not tested inside the container.
```{% if cookiecutter.ifdd_keycloak_lab_client_id %}

### Adding the lab client

A realm imported before lab existed lacks the client
`{{ cookiecutter.ifdd_keycloak_lab_client_id }}` and its groups, and keeps
30 minutes of SSO idle time; the compose files require
`IFDD_KEYCLOAK_LAB_CLIENT_SECRET` from then on. Set the session times, create
the client and the groups with `kcadm.sh` inside the running container, as an
admin of the master realm:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} LAB={{ cookiecutter.ifdd_keycloak_lab_client_id }} HOST={{ cookiecutter.ifdd_lab_host }} USERS={{ cookiecutter.ifdd_keycloak_lab_users_group }} ADMINS={{ cookiecutter.ifdd_keycloak_lab_admins_group }} READ={{ cookiecutter.ifdd_be_role_nodes_read }}
CLIENTS="{{ cookiecutter.ifdd_oidc_backend_client_id }} {{ cookiecutter.ifdd_keycloak_api_client_id }} {{ cookiecutter.ifdd_keycloak_ct_client_id }} {{ cookiecutter.ifdd_keycloak_useradmin_client_id }} {{ cookiecutter.ifdd_ts_oidc_client_id }} {{ cookiecutter.ifdd_proxy_oidc_client_id }} {{ cookiecutter.ifdd_ts_api_oidc_client_id }} {{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}"
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
# 8 h for the realm, 30 min for every client that exists already
kcadm update "realms/$REALM" -s ssoSessionIdleTimeout=28800
for client in $CLIENTS; do
  id=$(kcadm get clients -r "$REALM" -q clientId="$client" --fields id --format csv --noquotes)
  [ -n "$id" ] && kcadm update "clients/$id" -r "$REALM" -s 'attributes."client.session.idle.timeout"=1800'
done
LID=$(kcadm create clients -r "$REALM" -i -s clientId="$LAB" -s name="IFDD Lab (JupyterHub)" \
  -s publicClient=false -s standardFlowEnabled=true -s directAccessGrantsEnabled=false \
  -s serviceAccountsEnabled=false -s fullScopeAllowed=true -s rootUrl="https://$HOST/" \
  -s "redirectUris=[\"https://$HOST/hub/oauth_callback\"]" \
  -s 'attributes."pkce.code.challenge.method"=S256' \
  -s "attributes.\"post.logout.redirect.uris\"=https://$HOST/hub/" \
  -s 'attributes."client.session.idle.timeout"=28800' \
  -s 'attributes."client.session.max.lifespan"=86400')
for scope in "$READ" groups; do
  SID=$(kcadm get client-scopes -r "$REALM" --fields id,name --format csv --noquotes | grep ",$scope\$" | cut -d, -f1)
  kcadm update "clients/$LID/default-client-scopes/$SID" -r "$REALM"
done
kcadm delete "clients/$LID/optional-client-scopes/$(kcadm get client-scopes -r "$REALM" --fields id,name --format csv --noquotes | grep ',offline_access$' | cut -d, -f1)" -r "$REALM" 2>/dev/null || true
kcadm create groups -r "$REALM" -s name="$USERS"
kcadm create groups -r "$REALM" -s name="$ADMINS"
kcadm get "clients/$LID/client-secret" -r "$REALM" --fields value --format csv --noquotes
rm /tmp/kcadm.config
exit
```

Put the printed secret into `.env` as `IFDD_KEYCLOAK_LAB_CLIENT_SECRET`
and into `secrets/oidc_client_secret` of the lab instance.

```{note}
Tested with `kcadm.sh` of the Keycloak 26.8.1 distribution against a local
server and a realm imported from the template 26.11.2; afterwards a token of
the client had a refresh lifetime of 8 h, the audience of the backend, the
group claim and a context pattern created after the import. Not tested
inside the container.
```
{%- endif %}
