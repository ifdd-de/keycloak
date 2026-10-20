"""Validation before generation.

Rejects values that would render but not work: a realm file that is no
longer valid JSON, a Keycloak that cannot find its realm, or redirect URIs
that never match.
"""
import re
import sys

VALUES = {
    "ifdd_keycloak_prj_name": "{{ cookiecutter.ifdd_keycloak_prj_name }}",
    "ifdd_keycloak_prj_slug": "{{ cookiecutter.ifdd_keycloak_prj_slug }}",
    "ifdd_oidc_realm": "{{ cookiecutter.ifdd_oidc_realm }}",
    "ifdd_keycloak_host": "{{ cookiecutter.ifdd_keycloak_host }}",
    "ifdd_keycloak_realm": "{{ cookiecutter.ifdd_keycloak_realm }}",
    "ifdd_keycloak_dev_port": "{{ cookiecutter.ifdd_keycloak_dev_port }}",
    "ifdd_keycloak_admin_user": "{{ cookiecutter.ifdd_keycloak_admin_user }}",
    "ifdd_proxy_network": "{{ cookiecutter.ifdd_proxy_network }}",
    "ifdd_oidc_backend_client_id": "{{ cookiecutter.ifdd_oidc_backend_client_id }}",
    "ifdd_oidc_jwks_audience": "{{ cookiecutter.ifdd_oidc_jwks_audience }}",
    "ifdd_be_url": "{{ cookiecutter.ifdd_be_url }}",
    "ifdd_ui_url": "{{ cookiecutter.ifdd_ui_url }}",
    "ifdd_be_role_nodes_read": "{{ cookiecutter.ifdd_be_role_nodes_read }}",
    "ifdd_keycloak_role_nodes_write": "{{ cookiecutter.ifdd_keycloak_role_nodes_write }}",
    "ifdd_keycloak_role_public": "{{ cookiecutter.ifdd_keycloak_role_public }}",
    "ifdd_keycloak_role_nodes_priv": "{{ cookiecutter.ifdd_keycloak_role_nodes_priv }}",
    "ifdd_keycloak_api_client_id": "{{ cookiecutter.ifdd_keycloak_api_client_id }}",
    "ifdd_keycloak_ct_client_id": "{{ cookiecutter.ifdd_keycloak_ct_client_id }}",
    "ifdd_keycloak_useradmin_client_id": "{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}",
    "ifdd_ts_oidc_client_id": "{{ cookiecutter.ifdd_ts_oidc_client_id }}",
    "ifdd_ts_host": "{{ cookiecutter.ifdd_ts_host }}",
    "ifdd_ts_role_admin": "{{ cookiecutter.ifdd_ts_role_admin }}",
    "ifdd_ts_role_editor": "{{ cookiecutter.ifdd_ts_role_editor }}",
    "ifdd_ts_role_viewer": "{{ cookiecutter.ifdd_ts_role_viewer }}",
    "ifdd_proxy_oidc_client_id": "{{ cookiecutter.ifdd_proxy_oidc_client_id }}",
    "ifdd_wf_host": "{{ cookiecutter.ifdd_wf_host }}",
    "ifdd_keycloak_wf_admin_group": "{{ cookiecutter.ifdd_keycloak_wf_admin_group }}",
    "ifdd_keycloak_group_nodes_readers": "{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}",
    "ifdd_keycloak_group_nodes_writers": "{{ cookiecutter.ifdd_keycloak_group_nodes_writers }}",
    "ifdd_keycloak_group_nodes_privileged": "{{ cookiecutter.ifdd_keycloak_group_nodes_privileged }}",
    "ifdd_keycloak_proxy_gate_hosts": "{{ cookiecutter.ifdd_keycloak_proxy_gate_hosts }}",
    "ifdd_keycloak_image": "{{ cookiecutter.ifdd_keycloak_image }}",
    "ifdd_context_root": "{{ cookiecutter.ifdd_context_root }}",
}

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")           # realm, client, role, group
HOST = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?$")
URL = re.compile(r"^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]*)?$")

errors = []

def check(key, pattern, what):
    if not pattern.match(VALUES[key]):
        errors.append(f"{key}={VALUES[key]!r}: expected {what}")

# Also the title of the login pages, written into a TOML string (values.toml).
check("ifdd_keycloak_prj_name", re.compile(r'^[^"\\\x00-\x1f]+$'),
      "a name without double quotes, backslashes or control characters")
check("ifdd_keycloak_prj_slug", re.compile(r"^[a-z0-9][a-z0-9_-]*$"), "lowercase letters, digits, '-', '_'")
check("ifdd_oidc_realm", re.compile(r"^https://[^/]+/realms/[^/]+/?$"), "https://<host>/realms/<realm>")
for key in ("ifdd_keycloak_host", "ifdd_ts_host", "ifdd_wf_host"):
    check(key, HOST, "a host name without scheme or path")
for key in ("ifdd_be_url", "ifdd_ui_url"):
    check(key, URL, "http(s)://host[/path] without query")
    if VALUES[key].endswith("/"):
        errors.append(f"{key}: no trailing slash (the realm appends '/*')")
for key in ("ifdd_keycloak_realm", "ifdd_keycloak_admin_user", "ifdd_proxy_network",
            "ifdd_oidc_backend_client_id", "ifdd_oidc_jwks_audience",
            "ifdd_be_role_nodes_read", "ifdd_keycloak_role_nodes_write", "ifdd_keycloak_role_public",
            "ifdd_keycloak_api_client_id", "ifdd_keycloak_ct_client_id",
            "ifdd_keycloak_useradmin_client_id", "ifdd_ts_oidc_client_id",
            "ifdd_ts_role_admin", "ifdd_ts_role_editor", "ifdd_ts_role_viewer",
            "ifdd_proxy_oidc_client_id", "ifdd_keycloak_wf_admin_group",
            "ifdd_keycloak_role_nodes_priv", "ifdd_keycloak_group_nodes_readers",
            "ifdd_keycloak_group_nodes_writers", "ifdd_keycloak_group_nodes_privileged"):
    check(key, NAME, "letters, digits, '.', '_', '-' (no spaces, no quotes)")

# A context pattern, as ifdd-be-core reads it: two or more lower-case labels.
check("ifdd_context_root", re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"),
      "a dotted lower-case name such as ifdd.de (letters, digits, inner '-')")

gate_hosts = [h.strip() for h in VALUES["ifdd_keycloak_proxy_gate_hosts"].split(",")]
if not all(HOST.match(h) for h in gate_hosts) or len(set(gate_hosts)) != len(gate_hosts):
    errors.append("ifdd_keycloak_proxy_gate_hosts: comma-separated, distinct host names without scheme")
if not re.match(r"^[^:@]+:[0-9][0-9A-Za-z.-]*$", VALUES["ifdd_keycloak_image"].rsplit("/", 1)[-1]):
    errors.append("ifdd_keycloak_image: needs a version tag (it selects the built-in scopes of the realm)")
if VALUES["ifdd_keycloak_realm"] == "master":
    errors.append("ifdd_keycloak_realm: the master realm cannot be imported")
if not VALUES["ifdd_oidc_realm"].rstrip("/").endswith("/realms/" + VALUES["ifdd_keycloak_realm"]):
    errors.append("ifdd_keycloak_realm must be the realm named in ifdd_oidc_realm (services use that URL)")
if VALUES["ifdd_oidc_realm"].split("://")[-1].split("/")[0] != VALUES["ifdd_keycloak_host"]:
    errors.append("ifdd_keycloak_host must be the host named in ifdd_oidc_realm (tokens carry it as issuer)")
if not VALUES["ifdd_keycloak_dev_port"].isdigit() or not 1 <= int(VALUES["ifdd_keycloak_dev_port"]) <= 65535:
    errors.append("ifdd_keycloak_dev_port: expected a port number")

clients = [VALUES[k] for k in ("ifdd_oidc_backend_client_id", "ifdd_keycloak_api_client_id",
                                "ifdd_keycloak_ct_client_id", "ifdd_keycloak_useradmin_client_id",
                                "ifdd_ts_oidc_client_id", "ifdd_proxy_oidc_client_id")]
if len(set(clients)) != len(clients):
    errors.append(f"client ids must differ: {clients}")
roles = [VALUES[k] for k in ("ifdd_be_role_nodes_read", "ifdd_keycloak_role_nodes_write",
                              "ifdd_keycloak_role_public", "ifdd_keycloak_role_nodes_priv",
                              "ifdd_ts_role_admin",
                              "ifdd_ts_role_editor", "ifdd_ts_role_viewer")]
if len(set(roles)) != len(roles):
    errors.append(f"realm role names must differ: {roles}")
groups = [VALUES[k] for k in ("ifdd_keycloak_wf_admin_group", "ifdd_keycloak_group_nodes_readers",
                               "ifdd_keycloak_group_nodes_writers",
                               "ifdd_keycloak_group_nodes_privileged")]
if len(set(groups)) != len(groups):
    errors.append(f"group names must differ: {groups}")
if VALUES["ifdd_be_role_nodes_read"] in {"groups", "profile", "email", "roles", "basic", "acr",
                                          "web-origins", "address", "phone", "offline_access",
                                          "microprofile-jwt", "organization", "role_list",
                                          "saml_organization", "service_account",
                                          "AuthnContextClassRef"}:
    errors.append("ifdd_be_role_nodes_read also names a client scope; it must not clash with a built-in scope")

if errors:
    print("Invalid values:", *errors, sep="\n  - ", file=sys.stderr)
    sys.exit(1)
