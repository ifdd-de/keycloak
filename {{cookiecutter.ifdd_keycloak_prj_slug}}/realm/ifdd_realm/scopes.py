"""Client scopes of IFDD (the built-in ones come from builtin.py)."""
from . import mappers
from .model import ClientScope
from .values import Values

GROUPS = "groups"


def nodes_read_scope(v: Values) -> ClientScope:
    """Adds the audience ifdd-be checks. Named like the read role, as before.

    Assigned only to the clients that call ifdd-be (clients.py), not as a
    realm default: a client created later reaches ifdd-be only when given it.
    """
    return ClientScope(name=v.roles.nodes_read,
                       display_on_consent_screen=True,       # as in the original realm
                       mappers=[mappers.audience(v.backend_audience)])


def groups_scope() -> ClientScope:
    """Group membership in the claim 'groups', requested by oauth2-proxy."""
    return ClientScope(name=GROUPS,
                       description="Group membership in the claim 'groups' (short names).",
                       mappers=[mappers.group_membership(GROUPS)])


def scopes(v: Values) -> list[ClientScope]:
    return [nodes_read_scope(v), groups_scope()]
