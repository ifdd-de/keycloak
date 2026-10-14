"""Protocol mappers used by the IFDD scopes and clients."""
from .model import ProtocolMapper

TOKENS = {"id.token.claim": "true", "access.token.claim": "true",
          "introspection.token.claim": "true", "lightweight.claim": "false"}


def audience_of_client(client_id: str) -> ProtocolMapper:
    """Put a client of this realm into the aud claim."""
    return ProtocolMapper(name="audience", mapper="oidc-audience-mapper",
                          config=TOKENS | {"included.client.audience": client_id})


def audience(value: str) -> ProtocolMapper:
    """Put a fixed value into the aud claim (what a resource server checks)."""
    return ProtocolMapper(name="audience", mapper="oidc-audience-mapper",
                          config=TOKENS | {"included.custom.audience": value})


def group_membership(claim: str = "groups") -> ProtocolMapper:
    """Group names without path (/name would not match allowed_groups=name)."""
    return ProtocolMapper(name=claim, mapper="oidc-group-membership-mapper",
                          config=TOKENS | {"claim.name": claim, "full.path": "false",
                                           "userinfo.token.claim": "true"})


def own_client_roles_for_client_side(client_id: str) -> ProtocolMapper:
    """This client's own client roles in the ID token and the userinfo response.

    The built-in scope 'roles' puts resource_access only into the access token,
    which a client must not read (RFC 9068, section 6); ifdd-ui reads its roles
    from user.profile (ID token and userinfo). The access token stays as it is.
    """
    return ProtocolMapper(
        name="client roles for the client", mapper="oidc-usermodel-client-role-mapper",
        config={"usermodel.clientRoleMapping.clientId": client_id,
                "claim.name": "resource_access.${client_id}.roles",
                "multivalued": "true", "jsonType.label": "String",
                "id.token.claim": "true", "userinfo.token.claim": "true",
                "access.token.claim": "false", "introspection.token.claim": "false",
                "lightweight.claim": "false"})
