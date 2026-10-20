"""Realm settings and the assembly of all parts into the import file."""
import html
from typing import Any

from . import builtin, clients, groups, roles, scopes, users
from .values import Values

# Settings that differ from a fresh realm (taken over from the original realm).
SETTINGS: dict[str, Any] = {
    "sslRequired": "external",
    "loginWithEmailAllowed": False,
    "accessTokenLifespan": 1800,          # s; Keycloak default 300
    "accessCodeLifespan": 300,            # s; default 60
    "ssoSessionIdleTimeout": 1800,        # s
    "ssoSessionMaxLifespan": 86400,       # s; default 36000
    "oauth2DeviceCodeLifespan": 1800,     # s; default 600
    # Refresh token rotation: each refresh token is valid once (RFC 9700 4.14).
    "revokeRefreshToken": True,
    "refreshTokenMaxReuse": 0,
    # Temporary lockout after repeated login failures (Keycloak's thresholds).
    "bruteForceProtected": True,
    "passwordPolicy": "length(12) and notUsername",
    # Audit: login events kept 30 days, admin events without representations.
    "eventsEnabled": True,
    "eventsExpiration": 30 * 24 * 3600,
    "adminEventsEnabled": True,
    "adminEventsDetailsEnabled": False,
    # themes/ifdd of the instance, mounted into the container (styles only).
    "loginTheme": "ifdd",
}


def client_scope_mappings(all_clients: list) -> dict[str, list[dict[str, Any]]]:
    """{role-owning client: [{client, roles}]} for the client roles in role_scope."""
    result: dict[str, list[dict[str, Any]]] = {}
    for c in all_clients:
        for owner, names in c.role_scope.client.items():
            result.setdefault(owner, []).append({"client": c.client_id, "roles": list(names)})
    return result


def build(v: Values) -> dict[str, Any]:
    b = builtin.load(v.keycloak_version)
    default = roles.default_role(v)
    ifdd_scopes = scopes.scopes(v)
    all_clients = clients.clients(v, b)
    return {
        "realm": v.realm,
        "enabled": True,
        **SETTINGS,
        # The login pages show displayNameHtml as their heading, the browser
        # title shows displayName; the HTML one is escaped plain text.
        **({"displayName": v.display_name, "displayNameHtml": html.escape(v.display_name)}
           if v.display_name else {}),
        "roles": {
            "realm": [r.to_json() for r in roles.realm_roles(v)] + [default.to_json()],
            "client": {client: [r.to_json(client_role=True) for r in client_roles]
                       for client, client_roles in roles.client_roles(v).items()},
        },
        # Without defaultRole Keycloak ignores the role above and creates
        # default-roles-<realm>-1 (verified with 26.8.0).
        "defaultRole": {"name": default.name},
        "groups": [g.to_json() for g in groups.groups(v)],
        "clientScopes": b.client_scopes + [s.to_json() for s in ifdd_scopes],
        # For clients created later: no backend audience, no offline tokens.
        "defaultDefaultClientScopes": b.default_scopes,
        "defaultOptionalClientScopes": clients.optional_scopes(b),
        "users": [a.to_json() for a in users.service_accounts(v, default.name)],
        # Roles allowed into the tokens of clients without full scope.
        "scopeMappings": [{"client": c.client_id, "roles": list(c.role_scope.realm)}
                          for c in all_clients if c.role_scope.realm],
        "clientScopeMappings": client_scope_mappings(all_clients),
        "clients": [c.to_json() for c in all_clients],
    }
