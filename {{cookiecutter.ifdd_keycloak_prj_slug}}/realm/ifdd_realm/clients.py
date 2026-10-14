"""One function per client of the realm.

Common rules (review of 2026-10-03, following RFC 9700):
- no implicit flow, no password grant;
- public clients must use PKCE (S256);
- no client offers the scope offline_access (no offline tokens);
- only clients that call ifdd-be get the scope with its audience.
"""
from . import mappers, roles
from .builtin import Builtin
from .model import Client, Grant, ProtocolMapper
from .scopes import GROUPS
from .values import Values

OFFLINE = "offline_access"
# The OAuth2 redirect page of the backend's Swagger UI (ifdd-be-core,
# docs_ui.OAUTH2_REDIRECT_PATH): "Authorize" on <be_url>/docs returns there.
BE_DOCS_REDIRECT = "/docs/oauth2-redirect"
PKCE = {"pkce.code.challenge.method": "S256"}


def optional_scopes(b: Builtin) -> list[str]:
    return [s for s in b.optional_scopes if s != OFFLINE]


def backend(v: Values, b: Builtin) -> Client:
    """Public client of ifdd-ui (login) and ifdd-be (audience).

    Redirect URIs are those of ifdd-ui's src/auth/authConfig.js and the
    OAuth2 redirect page of the backend's Swagger UI, each exact (RFC 9700,
    section 2.1: no patterns).
    """
    return Client(
        client_id=v.backend_client,
        public=True,
        standard_flow=True,
        root_url=v.ui_url + "/", base_url=v.ui_url + "/", admin_url=v.ui_url + "/",
        redirect_uris=[v.ui_url + "/authentication/callback",
                       v.ui_url + "/authentication/silent-callback",
                       v.be_url + BE_DOCS_REDIRECT],
        web_origins=["+"],
        full_scope_allowed=False,                     # own client roles reach the tokens anyway
        role_scope=Grant(realm=[v.roles.public]),     # plus realm ifdd_public
        mappers=[mappers.own_client_roles_for_client_side(v.backend_client)],
        attributes=PKCE | {"post.logout.redirect.uris": v.ui_url,
                           "backchannel.logout.session.required": "true"},
        default_scopes=b.default_scopes + [v.roles.nodes_read],
        optional_scopes=optional_scopes(b),
    )


def api_script(v: Values, b: Builtin) -> Client:
    """Confidential client for scripts: client credentials only."""
    return Client(
        client_id=v.api_client,
        secret_env="IFDD_KEYCLOAK_API_CLIENT_SECRET",
        service_account=True,
        attributes={
            "use.refresh.tokens": "true",
            "client_credentials.use_refresh_token": "true",   # kept, as in the original realm
        },
        mappers=[ProtocolMapper(
            name="audience-mapper", mapper="oidc-audience-mapper",
            config={"included.client.audience": v.api_client,
                    "included.custom.audience": v.backend_audience,
                    "id.token.claim": "false", "access.token.claim": "true",
                    "introspection.token.claim": "true", "lightweight.claim": "false"})],
        default_scopes=b.default_scopes + [v.roles.nodes_read],
        optional_scopes=optional_scopes(b),
    )


def ct(v: Values, b: Builtin) -> Client:
    """ifdd-ct: client credentials only; writes to ifdd-be. Tokens carry node roles only."""
    return Client(
        client_id=v.ct_client,
        name="IFDD Core Tools",
        description="Client credentials of ifdd-ct (writes to ifdd-be).",
        secret_env="IFDD_KEYCLOAK_CT_CLIENT_SECRET",
        service_account=True,
        full_scope_allowed=False,
        role_scope=roles.signed_in(v) + roles.write(v) + roles.context_root(v),
        default_scopes=b.default_scopes + [v.roles.nodes_read],
        optional_scopes=optional_scopes(b),
    )


def user_admin(v: Values, b: Builtin) -> Client:
    """Scripts that create users of this realm and add them to groups:
    client credentials only. Tokens carry its realm-management roles only."""
    return Client(
        client_id=v.useradmin_client,
        name="IFDD User Admin",
        description="Client credentials for scripts that create users and add them to groups.",
        secret_env="IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET",
        service_account=True,
        full_scope_allowed=False,
        role_scope=roles.user_admin(),
        default_scopes=b.default_scopes,
        optional_scopes=optional_scopes(b),
    )


def ts(v: Values, b: Builtin) -> Client:
    """Grafana of ifdd-ts: login (generic OAuth, realm roles in realm_access)
    and client credentials for reading ifdd-be. Tokens carry the Grafana roles
    and the read roles only."""
    url = "https://" + v.ts_host
    r = v.roles
    return Client(
        client_id=v.ts_client,
        name="IFDD Time Series (Grafana)",
        description="Grafana login (generic OAuth) and client credentials for reading ifdd-be.",
        secret_env="IFDD_KEYCLOAK_TS_CLIENT_SECRET",
        standard_flow=True, service_account=True,
        root_url=url + "/",
        redirect_uris=[url + "/login/generic_oauth"],
        web_origins=["+"],
        full_scope_allowed=False,
        role_scope=Grant(realm=[r.grafana_admin, r.grafana_editor, r.grafana_viewer])
                   + roles.signed_in(v) + roles.read(v) + roles.context_root(v),
        attributes=PKCE | {"post.logout.redirect.uris": url + "/*"},
        default_scopes=b.default_scopes + [v.roles.nodes_read],
        optional_scopes=optional_scopes(b),
    )


def proxy(v: Values, b: Builtin) -> Client:
    """oauth2-proxy of ifdd-proxy: login gate, groups in the claim 'groups'."""
    hosts = ["https://" + host for host in v.proxy_gate_hosts]
    return Client(
        client_id=v.proxy_client,
        name="IFDD Proxy (oauth2-proxy)",
        description="Login gate in front of services; group membership in claim 'groups'.",
        secret_env="IFDD_KEYCLOAK_PROXY_CLIENT_SECRET",
        standard_flow=True,
        redirect_uris=[h + "/oauth2/callback" for h in hosts],
        attributes=PKCE | {"post.logout.redirect.uris": "##".join(h + "/*" for h in hosts)},
        mappers=[mappers.audience_of_client(v.proxy_client)],    # oauth2-proxy checks aud
        default_scopes=b.default_scopes + [GROUPS],
        optional_scopes=optional_scopes(b),
    )


def clients(v: Values, b: Builtin) -> list[Client]:
    return [backend(v, b), api_script(v, b), ct(v, b), user_admin(v, b), ts(v, b), proxy(v, b)]
