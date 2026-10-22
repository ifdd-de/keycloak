"""The values of realm/values.toml, read into typed data classes.

values.toml is written by cruft from the cookiecutter variables; edit it and
rebuild to change the realm file. Copies of it describe further realms.
"""
from dataclasses import dataclass
from pathlib import Path

import tomllib


@dataclass(frozen=True, kw_only=True)
class Roles:
    public: str           # signed in, no further rights (e.g. /prot_version)
    nodes_read: str       # read nodes in ifdd-be
    nodes_write: str      # write nodes in ifdd-be
    nodes_priv: str       # privileged read access (known to ifdd-ui)
    context_root: str     # context pattern: every domain context below the root
    grafana_admin: str
    grafana_editor: str
    grafana_viewer: str
    # ifdd-ts-api; empty in values files written before it existed
    ts_read: str = ""
    ts_write: str = ""


@dataclass(frozen=True, kw_only=True)
class Groups:
    wf_admins: str
    nodes_readers: str
    nodes_writers: str
    nodes_privileged: str


@dataclass(frozen=True, kw_only=True)
class Values:
    realm: str
    display_name: str     # title of the login pages; empty: none
    keycloak_version: str
    roles: Roles
    groups: Groups
    # backend: public client of ifdd-ui and ifdd-be
    backend_client: str
    backend_audience: str
    ui_url: str
    be_url: str
    # further clients
    api_client: str
    ct_client: str
    useradmin_client: str
    ts_client: str
    ts_host: str
    proxy_client: str
    proxy_gate_hosts: list[str]
    # ifdd-ts-api and its ingest client; empty: the realm has neither
    ts_api_client: str = ""
    ts_ingest_client: str = ""


def load(path: Path) -> Values:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    clients = raw["clients"]
    return Values(
        realm=raw["realm"]["name"],
        # Optional, so that values files written before it existed still load.
        display_name=raw["realm"].get("display_name", ""),
        keycloak_version=raw["realm"]["keycloak_version"],
        roles=Roles(**raw["roles"]),
        groups=Groups(**raw["groups"]),
        backend_client=clients["backend"]["id"],
        backend_audience=clients["backend"]["audience"],
        ui_url=clients["backend"]["ui_url"],
        be_url=clients["backend"]["be_url"],
        api_client=clients["api"]["id"],
        ct_client=clients["ct"]["id"],
        useradmin_client=clients["useradmin"]["id"],
        ts_client=clients["ts"]["id"],
        ts_host=clients["ts"]["host"],
        proxy_client=clients["proxy"]["id"],
        proxy_gate_hosts=list(clients["proxy"]["gate_hosts"]),
        # Optional, so that values files written before ts-api still load.
        ts_api_client=clients.get("ts_api", {}).get("id", ""),
        ts_ingest_client=clients.get("ts_ingest", {}).get("id", ""),
    )
