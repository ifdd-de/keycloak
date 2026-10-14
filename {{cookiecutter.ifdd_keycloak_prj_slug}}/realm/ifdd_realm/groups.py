"""Groups. People get their rights by membership, assigned in the admin console."""
from . import roles
from .model import Group
from .values import Values

# Group of a context pattern: ifdd_ctx_<pattern>. keycloak_add_context_role.py
# of the meta repository uses the same prefix.
CONTEXT_GROUP_PREFIX = "ifdd_ctx_"


def groups(v: Values) -> list[Group]:
    g = v.groups
    return [
        Group(name=g.nodes_readers, grant=roles.read(v)),
        Group(name=g.nodes_writers, grant=roles.write(v)),
        Group(name=g.nodes_privileged, grant=roles.privileged(v)),
        Group(name=g.wf_admins),           # admitted to ifdd-wf by oauth2-proxy (claim groups)
        # every domain context; together with a node group (read or write)
        Group(name=CONTEXT_GROUP_PREFIX + v.roles.context_root, grant=roles.context_root(v)),
    ]
