"""Consistency checks on the finished realm, before it is written.

Keycloak's import is forgiving: a missing scope is skipped with a warning,
an unset ${VAR} stays literal text. These checks make such mistakes fail
here instead.
"""
import re
from collections import Counter
from typing import Any

SECRET = re.compile(r"\$\{IFDD_KEYCLOAK_[A-Z_]+_CLIENT_SECRET\}")

# Roles of clients Keycloak creates itself that the realm grants (the import
# file does not define them). Add a role here before granting it.
BUILTIN_CLIENT_ROLES = {"realm-management": {"manage-users"}}


def duplicates(names: list[str]) -> list[str]:
    return [n for n, count in Counter(names).items() if count > 1]


def check(realm: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    clients = {c["clientId"]: c for c in realm["clients"]}
    scope_names = [s["name"] for s in realm["clientScopes"]]
    realm_roles = [r["name"] for r in realm["roles"]["realm"]]

    for kind, names in (("client", [c["clientId"] for c in realm["clients"]]),
                        ("client scope", scope_names), ("realm role", realm_roles),
                        ("group", [g["name"] for g in realm["groups"]])):
        errors += [f"duplicate {kind}: {n}" for n in duplicates(names)]

    known_scopes = set(scope_names)
    referenced = [("realm default", s) for s in realm["defaultDefaultClientScopes"]]
    referenced += [("realm optional", s) for s in realm["defaultOptionalClientScopes"]]
    for c in realm["clients"]:
        referenced += [(c["clientId"], s) for s in c["defaultClientScopes"] + c["optionalClientScopes"]]
    errors += [f"{who}: unknown client scope {s}" for who, s in referenced if s not in known_scopes]

    if realm["defaultRole"]["name"] not in realm_roles:
        errors.append("defaultRole is not among the realm roles")
    client_roles = {c: {r["name"] for r in rs} for c, rs in realm["roles"]["client"].items()}
    errors += [f"client roles for unknown client {c}" for c in client_roles if c not in clients]
    client_roles |= BUILTIN_CLIENT_ROLES
    for role in realm["roles"]["realm"]:
        composites = role.get("composites", {})
        errors += [f"role {role['name']}: unknown realm role {r}"
                   for r in composites.get("realm", []) if r not in realm_roles]
        for client, names in composites.get("client", {}).items():
            errors += [f"role {role['name']}: unknown role {n} of client {client}"
                       for n in names if n not in client_roles.get(client, set())]
    for mapping in realm["scopeMappings"]:
        if mapping["client"] not in clients:
            errors.append(f"scope mapping for unknown client {mapping['client']}")
        errors += [f"scope mapping of {mapping['client']}: unknown realm role {r}"
                   for r in mapping["roles"] if r not in realm_roles]

    def check_grant(who: str, realm_names: list[str], client_names: dict[str, list[str]]) -> None:
        errors.extend(f"{who}: unknown realm role {r}" for r in realm_names if r not in realm_roles)
        for client, names in client_names.items():
            errors.extend(f"{who}: unknown role {n} of client {client}"
                          for n in names if n not in client_roles.get(client, set()))

    for owner, mappings in realm["clientScopeMappings"].items():
        for mapping in mappings:
            if mapping["client"] not in clients:
                errors.append(f"client scope mapping for unknown client {mapping['client']}")
            check_grant(f"client scope mapping of {mapping['client']}", [], {owner: mapping["roles"]})
    for group in realm["groups"]:
        check_grant(f"group {group['name']}", group.get("realmRoles", []), group.get("clientRoles", {}))
    for user in realm["users"]:
        client = clients.get(user["serviceAccountClientId"])
        if not client or not client["serviceAccountsEnabled"]:
            errors.append(f"{user['username']}: client without service account")
        check_grant(user["username"], user["realmRoles"], user.get("clientRoles", {}))

    for c in realm["clients"]:
        if c["publicClient"] == ("secret" in c):
            errors.append(f"{c['clientId']}: a public client has no secret, a confidential one needs one")
        if "secret" in c and not SECRET.fullmatch(c["secret"]):
            errors.append(f"{c['clientId']}: secret must be an ${{IFDD_KEYCLOAK_*_CLIENT_SECRET}} placeholder")
        # Rules of the review (RFC 9700): no implicit flow, no password grant,
        # PKCE for public clients, no offline tokens.
        if c["implicitFlowEnabled"] or c["directAccessGrantsEnabled"]:
            errors.append(f"{c['clientId']}: implicit flow and password grant are not allowed")
        if c["publicClient"] and c["attributes"].get("pkce.code.challenge.method") != "S256":
            errors.append(f"{c['clientId']}: a public client must require PKCE S256")
        if "offline_access" in c["defaultClientScopes"] + c["optionalClientScopes"]:
            errors.append(f"{c['clientId']}: offline_access is not offered")
        if '"type": "js"' in str(c.get("authorizationSettings", "")):
            errors.append(f"{c['clientId']}: js policies cannot be imported by Keycloak 26")
    return errors
