"""Realm roles, client roles, the default role and named grants.

The node roles exist twice: as realm roles and as client roles of the
backend client. ifdd-be and ifdd-ui check the client roles
(resource_access.<backend client>.roles); the realm roles are kept
alongside. Every node grant below gives both.

A context pattern is a client role of the backend client whose name has a
dot (ifdd-be-core, "Contexts and access"); it exists only as a client role.
The template knows one, the context root; further patterns are created with
keycloak_add_context_role.py of the meta repository.

ifdd-ts-api has a client of its own that only carries roles: read, write and
store patterns (client roles with a dot, the same syntax). The context root
is its root store pattern too. Its roles are given to service accounts only.
"""
from .model import Grant, Role
from .values import Values


def realm_roles(v: Values) -> list[Role]:
    r = v.roles
    return [
        Role(name=r.public, description="Signed in, no further rights (e.g. /prot_version of ifdd-be)."),
        Role(name=r.nodes_read, description="Read nodes in ifdd-be."),
        Role(name=r.nodes_write, description="Write nodes in ifdd-be."),
        Role(name=r.nodes_priv, description="Privileged read access to nodes (ifdd-ui)."),
        Role(name=r.grafana_admin, description="Grafana Admin (ifdd-ts)."),
        Role(name=r.grafana_editor, description="Grafana Editor (ifdd-ts)."),
        Role(name=r.grafana_viewer, description="Grafana Viewer (ifdd-ts)."),
    ]


def client_roles(v: Values) -> dict[str, list[Role]]:
    r = v.roles
    result = {v.backend_client: [
        Role(name=r.public, description="Signed in, no further rights."),
        Role(name=r.nodes_read, description="Read nodes."),
        Role(name=r.nodes_write, description="Write nodes."),
        Role(name=r.nodes_priv, description="Privileged read access to nodes."),
        Role(name=r.context_root,
             description=f"Context pattern: every domain context below {r.context_root}."),
    ]}
    if v.ts_api_client:
        result[v.ts_api_client] = [
            Role(name=r.ts_read, description="Read samples (ifdd-ts-api)."),
            Role(name=r.ts_write, description="Write samples (ifdd-ts-api)."),
            Role(name=r.context_root,
                 description=f"Store pattern: every store below {r.context_root}."),
        ]
    return result


# Keycloak creates the client realm-management with every realm; the import
# file only refers to its roles.
REALM_MANAGEMENT = "realm-management"
# Enough to find users and groups, create users, set passwords and add users
# to existing groups (checked with Keycloak 26.8.0; query-groups, view-users
# and query-users add nothing to it).
USER_ADMIN_ROLES = ["manage-users"]


def user_admin() -> Grant:
    """Create users, set their passwords, add them to existing groups."""
    return Grant(client={REALM_MANAGEMENT: list(USER_ADMIN_ROLES)})


def node_grant(v: Values, *names: str) -> Grant:
    """The node roles `names` as realm roles and as client roles of the backend client."""
    return Grant(realm=list(names), client={v.backend_client: list(names)})


# Named grants, used by the default role, the groups and the service accounts.

def signed_in(v: Values) -> Grant:
    return node_grant(v, v.roles.public)


def read(v: Values) -> Grant:
    return node_grant(v, v.roles.nodes_read)


def write(v: Values) -> Grant:
    return node_grant(v, v.roles.nodes_read, v.roles.nodes_write)


def privileged(v: Values) -> Grant:
    return node_grant(v, v.roles.nodes_read, v.roles.nodes_priv)


def context_root(v: Values) -> Grant:
    """The context pattern of the root: every domain context (client role only)."""
    return Grant(client={v.backend_client: [v.roles.context_root]})


def ts_reader(v: Values) -> Grant:
    """Read samples of every store through ifdd-ts-api (nothing without ts-api)."""
    if not v.ts_api_client:
        return Grant()
    return Grant(client={v.ts_api_client: [v.roles.ts_read, v.roles.context_root]})


def ts_writer(v: Values) -> Grant:
    """Write samples to every store through ifdd-ts-api (nothing without ts-api)."""
    if not v.ts_api_client:
        return Grant()
    return Grant(client={v.ts_api_client: [v.roles.ts_write, v.roles.context_root]})


def default_role(v: Values) -> Role:
    """Granted to every user and service account of the realm: signed in only.

    Reading needs a group (groups.py). Keycloak adds offline_access,
    uma_authorization and two account roles to this role on import (26.8.0);
    that cannot be prevented from the import file.
    """
    grant = signed_in(v)
    return Role(name=f"default-roles-{v.realm}", description="${role_default-roles}",
                realm_composites=grant.realm, client_composites=grant.client)
