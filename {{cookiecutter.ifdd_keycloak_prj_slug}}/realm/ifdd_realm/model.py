"""Data classes for the parts of a realm, each with its Keycloak JSON form.

Only what IFDD sets is modelled; everything else keeps Keycloak's defaults.
"""
from dataclasses import dataclass, field
from typing import Any

JSON = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class ProtocolMapper:
    name: str
    mapper: str                     # Keycloak provider id, e.g. oidc-audience-mapper
    config: dict[str, str]

    def to_json(self) -> JSON:
        return {
            "name": self.name,
            "protocol": "openid-connect",
            "protocolMapper": self.mapper,
            "consentRequired": False,
            "config": dict(self.config),
        }


@dataclass(frozen=True, kw_only=True)
class Role:
    name: str
    description: str = ""
    # Composite role: {client id: [client role, ...]} and realm role names
    client_composites: dict[str, list[str]] = field(default_factory=dict)
    realm_composites: list[str] = field(default_factory=list)

    @property
    def composite(self) -> bool:
        return bool(self.client_composites or self.realm_composites)

    def to_json(self, *, client_role: bool = False) -> JSON:
        data: JSON = {"name": self.name, "description": self.description,
                      "composite": self.composite, "clientRole": client_role, "attributes": {}}
        if self.composite:
            composites: JSON = {}
            if self.realm_composites:
                composites["realm"] = list(self.realm_composites)
            if self.client_composites:
                composites["client"] = {c: list(r) for c, r in self.client_composites.items()}
            data["composites"] = composites
        return data


@dataclass(frozen=True, kw_only=True)
class Grant:
    """Roles granted to a group or service account: realm roles and
    client roles ({client id: [role, ...]})."""
    realm: list[str] = field(default_factory=list)
    client: dict[str, list[str]] = field(default_factory=dict)

    def __add__(self, other: "Grant") -> "Grant":
        client = {c: list(r) for c, r in self.client.items()}
        for c, roles in other.client.items():
            client[c] = client.get(c, []) + [r for r in roles if r not in client.get(c, [])]
        return Grant(realm=self.realm + [r for r in other.realm if r not in self.realm], client=client)


@dataclass(frozen=True, kw_only=True)
class Group:
    name: str
    grant: Grant = field(default_factory=Grant)

    def to_json(self) -> JSON:
        data: JSON = {"name": self.name, "path": "/" + self.name, "subGroups": []}
        if self.grant.realm:
            data["realmRoles"] = list(self.grant.realm)
        if self.grant.client:
            data["clientRoles"] = {c: list(r) for c, r in self.grant.client.items()}
        return data


@dataclass(frozen=True, kw_only=True)
class ClientScope:
    name: str
    description: str = ""
    include_in_token_scope: bool = True
    display_on_consent_screen: bool = False
    mappers: list[ProtocolMapper] = field(default_factory=list)

    def to_json(self) -> JSON:
        return {
            "name": self.name,
            "description": self.description,
            "protocol": "openid-connect",
            "attributes": {
                "include.in.token.scope": str(self.include_in_token_scope).lower(),
                "display.on.consent.screen": str(self.display_on_consent_screen).lower(),
            },
            "protocolMappers": [m.to_json() for m in self.mappers],
        }


@dataclass(frozen=True, kw_only=True)
class Client:
    client_id: str
    name: str = ""
    description: str = ""
    # Confidential clients name the environment variable holding their
    # secret; the import resolves ${VAR}. Public clients have none.
    public: bool = False
    secret_env: str | None = None
    # Flows
    standard_flow: bool = False
    implicit_flow: bool = False
    direct_access_grants: bool = False
    service_account: bool = False
    # URLs
    root_url: str = ""
    base_url: str = ""
    admin_url: str = ""
    redirect_uris: list[str] = field(default_factory=list)
    web_origins: list[str] = field(default_factory=list)
    # Tokens
    full_scope_allowed: bool = True
    # With full_scope_allowed=False, roles reach the tokens only if listed
    # here (Keycloak "scope mappings"); the client's own roles always do.
    role_scope: Grant = field(default_factory=Grant)
    default_scopes: list[str] = field(default_factory=list)
    optional_scopes: list[str] = field(default_factory=list)
    mappers: list[ProtocolMapper] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> JSON:
        data: JSON = {
            "clientId": self.client_id,
            "name": self.name,
            "description": self.description,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": self.public,
            "clientAuthenticatorType": "client-secret",
        }
        if self.secret_env:
            data["secret"] = "${" + self.secret_env + "}"
        data |= {
            "standardFlowEnabled": self.standard_flow,
            "implicitFlowEnabled": self.implicit_flow,
            "directAccessGrantsEnabled": self.direct_access_grants,
            "serviceAccountsEnabled": self.service_account,
        }
        data |= {key: url for key, url in (("rootUrl", self.root_url), ("baseUrl", self.base_url),
                                            ("adminUrl", self.admin_url)) if url}
        data |= {
            "redirectUris": list(self.redirect_uris),
            "webOrigins": list(self.web_origins),
            "frontchannelLogout": True,
            "fullScopeAllowed": self.full_scope_allowed,
            "attributes": dict(self.attributes),
            "protocolMappers": [m.to_json() for m in self.mappers],
            "defaultClientScopes": list(self.default_scopes),
            "optionalClientScopes": list(self.optional_scopes),
        }
        return data


@dataclass(frozen=True, kw_only=True)
class ServiceAccount:
    """The service account user of a client with the client credentials grant."""
    client_id: str
    grant: Grant

    def to_json(self) -> JSON:
        data: JSON = {
            "username": "service-account-" + self.client_id,
            "enabled": True,
            "serviceAccountClientId": self.client_id,
            "realmRoles": list(self.grant.realm),
        }
        if self.grant.client:
            data["clientRoles"] = {c: list(r) for c, r in self.grant.client.items()}
        return data
