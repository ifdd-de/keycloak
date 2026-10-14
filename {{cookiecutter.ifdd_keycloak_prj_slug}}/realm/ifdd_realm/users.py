"""Service accounts of the confidential clients and their rights.

No personal users: they and their passwords do not belong into the import
file; create them in the admin console and put them into a group.
"""
from . import roles
from .model import Grant, ServiceAccount
from .values import Values


def service_accounts(v: Values, default_role: str) -> list[ServiceAccount]:
    default = Grant(realm=[default_role])
    return [
        ServiceAccount(client_id=v.api_client,
                       grant=default + roles.read(v) + roles.context_root(v)),
        ServiceAccount(client_id=v.ct_client,
                       grant=default + roles.write(v) + roles.context_root(v)),
        ServiceAccount(client_id=v.useradmin_client, grant=default + roles.user_admin()),
        ServiceAccount(client_id=v.ts_client,
                       grant=default + roles.read(v) + roles.context_root(v)),
    ]
