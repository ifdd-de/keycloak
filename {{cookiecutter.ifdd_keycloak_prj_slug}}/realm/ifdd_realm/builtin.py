"""Keycloak's built-in client scopes, from a data file per Keycloak version.

The realm file must list them: a clientScopes list without them makes
Keycloak create none of them (verified with 26.8.0). The data file is a
partial export of a fresh realm of that version; add a new one together
with a new Keycloak image.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent / "builtin"


@dataclass(frozen=True)
class Builtin:
    client_scopes: list[dict[str, Any]]
    default_scopes: list[str]       # assigned to every new client
    optional_scopes: list[str]

    @property
    def names(self) -> set[str]:
        return {s["name"] for s in self.client_scopes}


def load(keycloak_version: str) -> Builtin:
    path = DATA / f"keycloak-{keycloak_version}.json"
    if not path.is_file():
        known = sorted(p.stem.removeprefix("keycloak-") for p in DATA.glob("keycloak-*.json"))
        raise SystemExit(f"no built-in scopes for Keycloak {keycloak_version} in {DATA} "
                         f"(available: {', '.join(known)}); export a fresh realm of that version")
    data = json.loads(path.read_text())
    return Builtin(data["clientScopes"], data["defaultDefaultClientScopes"],
                   data["defaultOptionalClientScopes"])
