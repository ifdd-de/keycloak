"""Template tests: render, build the realm, validate, check the hooks.

Run from the template root: pytest -q tests
Regenerate the golden files after an intended change of the realm:
    IFDD_UPDATE_GOLDEN=1 pytest -q tests
"""
import importlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from cookiecutter.exceptions import FailedHookException
from cookiecutter.main import cookiecutter

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = sorted((ROOT / "tests" / "fixtures").glob("*.yaml"))
GOLDEN = ROOT / "tests" / "golden"
COMPOSE = shutil.which("docker-compose") or (shutil.which("docker") and "docker compose")


def render(tmp_path, fixture=None, **extra):
    ctx = yaml.safe_load(fixture.read_text())["default_context"] if fixture else {}
    ctx.update(extra)
    out = cookiecutter(str(ROOT), no_input=True, output_dir=str(tmp_path), extra_context=ctx)
    return Path(out)


def build(instance, *args):
    return subprocess.run([sys.executable, "realm/build_realm.py", *args], cwd=instance,
                          capture_output=True, text=True, check=False)


@pytest.fixture(params=FIXTURES, ids=lambda p: p.stem)
def fixture_name(request):
    return request.param


@pytest.fixture
def instance(fixture_name, tmp_path):
    return render(tmp_path, fixture_name)


def realm_of(inst):
    files = list((inst / "realm" / "import").glob("*.json"))
    assert len(files) == 1, files
    return files[0], json.loads(files[0].read_text())


# --- generation ---------------------------------------------------------------

def test_realm_file_is_generated_and_named_after_the_realm(instance):
    path, realm = realm_of(instance)
    assert path.name == f"{realm['realm']}-realm.json"     # required by --import-realm


def test_generated_file_is_up_to_date(instance):
    result = build(instance, "--check")
    assert result.returncode == 0, result.stderr


def test_check_notices_a_changed_value(instance):
    values = instance / "realm" / "values.toml"
    values.write_text(values.read_text().replace('id = "ifdd-ct"', 'id = "ifdd-ct-2"'))
    assert build(instance, "--check").returncode == 1
    assert build(instance).returncode == 0
    assert "ifdd-ct-2" in realm_of(instance)[0].read_text()


def test_renaming_the_realm_removes_the_old_file(instance):
    values = instance / "realm" / "values.toml"
    old = realm_of(instance)[0]
    values.write_text(re.sub(r'(?m)^name = ".*"$', 'name = "renamed"', values.read_text()))
    assert build(instance).returncode == 0
    assert not old.exists() and realm_of(instance)[0].name == "renamed-realm.json"


@pytest.mark.parametrize("kind", ["json", "md"])
def test_golden(instance, fixture_name, kind):
    """Unintended changes of the realm or its overview show up here (see module doc)."""
    path = realm_of(instance)[0] if kind == "json" else instance / "realm" / "OVERVIEW.md"
    golden = GOLDEN / f"{fixture_name.stem}.{kind}"
    if os.environ.get("IFDD_UPDATE_GOLDEN"):
        GOLDEN.mkdir(exist_ok=True)
        golden.write_text(path.read_text())
    assert path.read_text() == golden.read_text()


def test_overview_lists_every_client_role_and_group(instance):
    text = (instance / "realm" / "OVERVIEW.md").read_text()
    realm = realm_of(instance)[1]
    names = [c["clientId"] for c in realm["clients"]] + [g["name"] for g in realm["groups"]]
    names += [r["name"] for r in realm["roles"]["realm"]]
    assert all(f"`{n}`" in text for n in names)


def test_check_notices_an_edited_overview(instance):
    overview = instance / "realm" / "OVERVIEW.md"
    overview.write_text(overview.read_text() + "edited by hand\n")
    assert build(instance, "--check").returncode == 1


def test_unknown_keycloak_version_fails(tmp_path):
    with pytest.raises(FailedHookException):
        render(tmp_path, ifdd_keycloak_image="quay.io/keycloak/keycloak:99.0.0")


# --- content ------------------------------------------------------------------

def test_content(instance):
    realm = realm_of(instance)[1]
    names = {s["name"] for s in realm["clientScopes"]}
    assert {"profile", "email", "roles", "basic", "groups"} <= names     # built-ins plus own
    backend = next(c for c in realm["clients"] if c["publicClient"])["clientId"]
    default = realm["defaultRole"]["name"]
    role = next(r for r in realm["roles"]["realm"] if r["name"] == default)
    # signed in only; reading comes from groups
    assert role["composites"] == {"realm": ["ifdd_public"], "client": {backend: ["ifdd_public"]}}
    assert {r["name"] for r in realm["roles"]["client"][backend]} == \
        {"ifdd_public", "ifdd_nodes_ro", "ifdd_nodes_rw", "ifdd_nodes_priv", "ifdd.de"}
    groups = {g["name"]: g for g in realm["groups"]}
    assert groups["ifdd_nodes_readers"]["clientRoles"] == {backend: ["ifdd_nodes_ro"]}
    assert groups["ifdd_nodes_writers"]["clientRoles"] == {backend: ["ifdd_nodes_ro", "ifdd_nodes_rw"]}
    assert groups["ifdd_nodes_privileged"]["clientRoles"] == {backend: ["ifdd_nodes_ro", "ifdd_nodes_priv"]}
    assert all(m["protocolMapper"] != "oidc-usersessionmodel-note-mapper"
               for c in realm["clients"] for m in c.get("protocolMappers", []))


def test_review_rules(instance):
    """Decisions of the review of 2026-10-03 (RFC 9700)."""
    realm = realm_of(instance)[1]
    clients = {c["clientId"]: c for c in realm["clients"]}
    backend = next(c for c in clients.values() if c["publicClient"])
    assert not backend["implicitFlowEnabled"]
    assert backend["attributes"]["pkce.code.challenge.method"] == "S256"
    assert [u for u in backend["redirectUris"] if "/authentication/" in u] == [
        backend["rootUrl"] + "authentication/callback", backend["rootUrl"] + "authentication/silent-callback"]
    api = clients["ifdd-api-script"]
    assert api["serviceAccountsEnabled"] and not api["standardFlowEnabled"] \
        and not api["directAccessGrantsEnabled"] and api["redirectUris"] == []
    for c in clients.values():
        assert "offline_access" not in c["defaultClientScopes"] + c["optionalClientScopes"]
    assert "offline_access" not in realm["defaultOptionalClientScopes"]
    assert "ifdd_nodes_ro" not in realm["defaultDefaultClientScopes"]     # no audience for new clients
    assert not clients["ifdd-ts"]["fullScopeAllowed"] and not clients["ifdd-ct"]["fullScopeAllowed"]
    assert clients["ifdd-api-script"]["fullScopeAllowed"] and clients["ifdd-proxy"]["fullScopeAllowed"]
    assert realm["revokeRefreshToken"] is True and realm["refreshTokenMaxReuse"] == 0
    assert realm["bruteForceProtected"] is True
    assert realm["passwordPolicy"] == "length(12) and notUsername"
    assert realm["eventsEnabled"] and realm["adminEventsEnabled"] and not realm["adminEventsDetailsEnabled"]
    assert realm["accessTokenLifespan"] == 1800 and realm["accessCodeLifespan"] == 300   # kept


def test_backend_client_redirects_are_exact(instance, fixture_name):
    """No redirect pattern (RFC 9700, 2.1); the backend entry is the Swagger UI redirect page."""
    realm = realm_of(instance)[1]
    backend = next(c for c in realm["clients"] if c["publicClient"])
    assert not [u for u in backend["redirectUris"] if "*" in u]
    be_url = yaml.safe_load(fixture_name.read_text())["default_context"].get(
        "ifdd_be_url", "https://be.example.org")
    assert be_url + "/docs/oauth2-redirect" in backend["redirectUris"]


def test_context_root(instance):
    """The root pattern: a client role only, its group, and the service accounts that read."""
    realm = realm_of(instance)[1]
    backend = next(c for c in realm["clients"] if c["publicClient"])["clientId"]
    assert "ifdd.de" not in {r["name"] for r in realm["roles"]["realm"]}
    groups = {g["name"]: g for g in realm["groups"]}
    assert groups["ifdd_ctx_ifdd.de"]["clientRoles"] == {backend: ["ifdd.de"]}
    accounts = {u["serviceAccountClientId"]: u for u in realm["users"]}
    for client in ("ifdd-api-script", "ifdd-ct", "ifdd-ts"):
        assert "ifdd.de" in accounts[client]["clientRoles"][backend], client
    assert backend not in accounts["ifdd-user-admin"].get("clientRoles", {})
    # clients without full scope need the pattern in their scope mapping
    mapped = {m["client"]: m["roles"] for m in realm["clientScopeMappings"][backend]}
    assert "ifdd.de" in mapped["ifdd-ct"] and "ifdd.de" in mapped["ifdd-ts"]


def test_another_context_root(tmp_path):
    realm = realm_of(render(tmp_path, ifdd_context_root="example.ifdd.de"))[1]
    assert "ifdd_ctx_example.ifdd.de" in {g["name"] for g in realm["groups"]}


def test_user_admin_client(instance):
    """Client credentials only, and of realm-management nothing but manage-users."""
    realm = realm_of(instance)[1]
    client = next(c for c in realm["clients"] if c["clientId"] == "ifdd-user-admin")
    assert client["serviceAccountsEnabled"] and not client["publicClient"]
    assert not client["standardFlowEnabled"] and not client["directAccessGrantsEnabled"]
    assert client["redirectUris"] == [] and not client["fullScopeAllowed"]
    account = next(u for u in realm["users"] if u["serviceAccountClientId"] == "ifdd-user-admin")
    assert account["clientRoles"] == {"realm-management": ["manage-users"]}
    assert realm["clientScopeMappings"]["realm-management"] == [
        {"client": "ifdd-user-admin", "roles": ["manage-users"]}]
    granted = [u for u in realm["users"] if "realm-management" in u.get("clientRoles", {})]
    assert granted == [account]                  # no other service account may manage users


def test_ui_roles_reach_the_client_side(instance):
    """Pattern 2B: the backend client's own client roles in ID token and userinfo."""
    realm = realm_of(instance)[1]
    backend = next(c for c in realm["clients"] if c["publicClient"])
    mapper = next(m for m in backend["protocolMappers"]
                  if m["protocolMapper"] == "oidc-usermodel-client-role-mapper")
    config = mapper["config"]
    assert config["usermodel.clientRoleMapping.clientId"] == backend["clientId"]
    assert config["claim.name"] == "resource_access.${client_id}.roles"
    assert config["id.token.claim"] == config["userinfo.token.claim"] == "true"
    assert config["access.token.claim"] == "false"       # access token unchanged


@pytest.mark.parametrize("name", ["docker-compose-production.yml", "docker-compose-development.yml"])
def test_keycloak_healthcheck(instance, name):
    keycloak = yaml.safe_load((instance / name).read_text())["services"]["keycloak"]
    assert keycloak["environment"]["KC_HEALTH_ENABLED"] == "true"
    assert keycloak["environment"]["KC_METRICS_ENABLED"] == "true"    # adds the database check
    test = keycloak["healthcheck"]["test"]
    assert test[:3] == ["CMD", "bash", "-c"] and "/dev/tcp/127.0.0.1/9000" in test[3]
    assert "$$status" in test[3]          # compose must not interpolate the shell variable


def test_gate_hosts(tmp_path):
    inst = render(tmp_path, ROOT / "tests" / "fixtures" / "two-gate-hosts.yaml")
    proxy = next(c for c in realm_of(inst)[1]["clients"] if c["clientId"] == "ifdd-proxy")
    assert proxy["redirectUris"] == ["https://wf.example.org/oauth2/callback",
                                     "https://ts.example.org/oauth2/callback"]
    assert proxy["attributes"]["post.logout.redirect.uris"] == \
        "https://wf.example.org/*##https://ts.example.org/*"


def test_secrets_come_from_the_environment(instance):
    realm = realm_of(instance)[1]
    secrets_ = [c["secret"] for c in realm["clients"] if not c["publicClient"]]
    assert all(re.fullmatch(r"\$\{IFDD_KEYCLOAK_[A-Z]+_CLIENT_SECRET\}", s) for s in secrets_)
    compose = (instance / "docker-compose-production.yml").read_text()
    for s in secrets_:
        var = s[2:-1]
        assert f'{var}: "${{{var}:?' in compose      # unset would become the literal secret


@pytest.fixture
def validate(instance):
    sys.path.insert(0, str(instance / "realm"))
    for name in [m for m in sys.modules if m == "ifdd_realm" or m.startswith("ifdd_realm.")]:
        del sys.modules[name]
    yield importlib.import_module("ifdd_realm.validate")
    sys.path.remove(str(instance / "realm"))


def test_validate_accepts_the_realm(instance, validate):
    assert validate.check(realm_of(instance)[1]) == []


@pytest.mark.parametrize("break_it, message", [
    (lambda r: r["clients"][0]["defaultClientScopes"].append("nope"), "unknown client scope nope"),
    (lambda r: r["users"][0]["realmRoles"].append("nope"), "unknown realm role nope"),
    (lambda r: r["clients"].append(dict(r["clients"][1])), "duplicate client"),
    (lambda r: r["clients"][1].update(secret="plain"), "placeholder"),
    (lambda r: r["scopeMappings"][0]["roles"].append("nope"), "unknown realm role nope"),
    (lambda r: r.update(defaultRole={"name": "nope"}), "defaultRole"),
    (lambda r: r["groups"][0]["clientRoles"].update(nope=["x"]), "unknown role x of client nope"),
    (lambda r: r["clients"][0].update(implicitFlowEnabled=True), "implicit flow"),
    (lambda r: r["clients"][0]["attributes"].pop("pkce.code.challenge.method"), "PKCE"),
    (lambda r: r["clients"][2]["optionalClientScopes"].append("offline_access"), "offline_access"),
    (lambda r: r["users"][0].setdefault("clientRoles", {}).update({"realm-management": ["manage-realm"]}),
     "unknown role manage-realm of client realm-management"),
])
def test_validate_rejects(instance, validate, break_it, message):
    realm = realm_of(instance)[1]
    break_it(realm)
    assert any(message in e for e in validate.check(realm))


# --- hooks and compose ----------------------------------------------------------

def test_env_is_generated_and_private(instance):
    env = instance / ".env"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    values = dict(line.split("=", 1) for line in env.read_text().splitlines()
                  if line and not line.startswith("#"))
    for key in [k for k in values if k.endswith(("_PASSWORD", "_SECRET"))]:
        assert re.fullmatch(r"[A-Za-z0-9]{32,}", values[key]), key


def test_env_names_the_user_admin_client(instance):
    """keycloak_add_user.py reads the client id from .env."""
    values = dict(line.split("=", 1) for line in (instance / ".env").read_text().splitlines()
                  if line and not line.startswith("#"))
    clients = [c["clientId"] for c in realm_of(instance)[1]["clients"]]
    assert values["IFDD_KEYCLOAK_USERADMIN_CLIENT_ID"] in clients


def test_existing_env_is_kept(instance):
    env = instance / ".env"
    before = env.read_text()
    subprocess.run([sys.executable, str(ROOT / "hooks" / "post_gen_project.py")], cwd=instance, check=True)
    assert env.read_text() == before


@pytest.mark.skipif(not COMPOSE, reason="docker compose not available")
@pytest.mark.parametrize("name", ["docker-compose-production.yml", "docker-compose-development.yml"])
def test_compose_is_valid(instance, name):
    subprocess.run(f"{COMPOSE} -f {name} config -q", shell=True, cwd=instance, check=True)


@pytest.mark.parametrize("extra", [
    {"ifdd_keycloak_realm": "other"},
    {"ifdd_keycloak_host": "other.example.org"},
    {"ifdd_oidc_realm": "https://kc.example.org/realms/master"},
    {"ifdd_ui_url": "https://ui.example.org/"},
    {"ifdd_ts_host": "https://ts.example.org"},
    {"ifdd_keycloak_ct_client_id": "ifdd-ts"},
    {"ifdd_keycloak_useradmin_client_id": "ifdd-ct"},
    {"ifdd_keycloak_useradmin_client_id": "user admin"},
    {"ifdd_ts_role_viewer": "admin"},
    {"ifdd_be_role_nodes_read": "groups"},
    {"ifdd_keycloak_api_client_id": 'a"b'},
    {"ifdd_keycloak_dev_port": "http"},
    {"ifdd_keycloak_proxy_gate_hosts": "wf, https://ts"},
    {"ifdd_keycloak_proxy_gate_hosts": "wf, wf"},
    {"ifdd_keycloak_image": "quay.io/keycloak/keycloak"},
    {"ifdd_context_root": "ifdd"},             # one label: not a pattern
    {"ifdd_context_root": "IFDD.de"},
    {"ifdd_context_root": "ifdd_x.de"},
])
def test_pre_hook_rejects(tmp_path, extra):
    with pytest.raises(FailedHookException):
        render(tmp_path, **extra)
