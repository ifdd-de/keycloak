"""Template tests: render, build the realm, validate, check the hooks.

Run from the template root: pytest -q tests
Regenerate the golden files after an intended change of the realm:
    IFDD_UPDATE_GOLDEN=1 pytest -q tests
"""
import gzip
import importlib
import json
import os
import pty
import re
import select
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


def test_renaming_the_realm_keeps_the_old_file(instance):
    """Files of other realms are never removed; the script only points them out."""
    values = instance / "realm" / "values.toml"
    old = realm_of(instance)[0]
    values.write_text(re.sub(r'(?m)^name = ".*"$', 'name = "renamed"', values.read_text()))
    result = build(instance)
    assert result.returncode == 0
    assert old.exists() and (old.parent / "renamed-realm.json").is_file()
    assert old.name in result.stdout                       # the note names it
    assert build(instance, "--check").returncode == 0      # not an error any more


def further_realm(instance, name, title="Another realm"):
    """A copy of values.toml for a further realm, as the README describes it."""
    source = (instance / "realm" / "values.toml").read_text()
    text = re.sub(r'(?m)^name = ".*"$', f'name = "{name}"', source)
    text = re.sub(r'(?m)^display_name = ".*"$', f'display_name = "{title}"', text)
    path = instance / "realm" / f"values_{name}.toml"
    path.write_text(text)
    return path


def test_several_values_files(instance):
    own_file, _ = realm_of(instance)
    own_overview = instance / "realm" / "OVERVIEW.md"
    before = (own_file.read_text(), own_overview.read_text())
    further_realm(instance, "aa")
    further_realm(instance, "dd", title="Realm D & D")
    result = build(instance, "--values", "realm/values_aa.toml", "realm/values_dd.toml")
    assert result.returncode == 0, result.stderr
    out = instance / "realm" / "import"
    aa = json.loads((out / "aa-realm.json").read_text())
    dd = json.loads((out / "dd-realm.json").read_text())
    assert aa["realm"] == "aa" and dd["realm"] == "dd"
    assert dd["displayName"] == "Realm D & D" and dd["displayNameHtml"] == "Realm D &amp; D"
    assert "`realm/values_dd.toml`" in (instance / "realm" / "OVERVIEW-dd.md").read_text()
    assert (instance / "realm" / "OVERVIEW-aa.md").is_file()
    # the realm of values.toml and its overview are untouched
    assert (own_file.read_text(), own_overview.read_text()) == before
    assert build(instance, "--check").returncode == 0
    assert build(instance, "--check", "--values", "realm/values_aa.toml",
                 "realm/values_dd.toml").returncode == 0


def test_check_of_a_further_realm_notices_a_change(instance):
    path = further_realm(instance, "aa")
    assert build(instance, "--values", "realm/values_aa.toml").returncode == 0
    path.write_text(path.read_text().replace('id = "ifdd-ct"', 'id = "ifdd-ct-2"'))
    assert build(instance, "--check", "--values", "realm/values_aa.toml").returncode == 1


def test_one_realm_name_in_two_values_files_fails(instance):
    further_realm(instance, "aa")
    (instance / "realm" / "values_bb.toml").write_text(
        (instance / "realm" / "values_aa.toml").read_text())
    result = build(instance, "--values", "realm/values_aa.toml", "realm/values_bb.toml")
    assert result.returncode != 0 and "'aa'" in result.stderr
    assert not (instance / "realm" / "import" / "aa-realm.json").exists()


def test_overview_option_needs_one_values_file(instance):
    further_realm(instance, "aa")
    result = build(instance, "--overview", "x.md", "--values", "realm/values.toml",
                   "realm/values_aa.toml")
    assert result.returncode != 0 and "needs exactly one values file" in result.stderr


def test_values_file_without_display_name_still_loads(instance):
    path = further_realm(instance, "aa")
    path.write_text(re.sub(r'(?m)^display_name = .*\n', "", path.read_text()))
    assert build(instance, "--values", "realm/values_aa.toml").returncode == 0
    realm = json.loads((instance / "realm" / "import" / "aa-realm.json").read_text())
    assert "displayName" not in realm and "displayNameHtml" not in realm


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


def test_no_byte_code_in_the_instance(instance):
    """cruft update renders twice and runs the hook each time: byte code with time
    stamps in realm/ifdd_realm/__pycache__ would look like a change of the instance."""
    assert not list(instance.rglob("__pycache__"))
    assert build(instance).returncode == 0
    assert not list(instance.rglob("__pycache__"))


def test_check_notices_an_edited_overview(instance):
    overview = instance / "realm" / "OVERVIEW.md"
    overview.write_text(overview.read_text() + "edited by hand\n")
    assert build(instance, "--check").returncode == 1


def test_unknown_keycloak_version_fails(tmp_path):
    with pytest.raises(FailedHookException):
        render(tmp_path, ifdd_keycloak_image="quay.io/keycloak/keycloak:99.0.0")


# --- content ------------------------------------------------------------------

def test_login_theme_and_title(instance, fixture_name):
    realm = realm_of(instance)[1]
    name = yaml.safe_load(fixture_name.read_text())["default_context"].get(
        "ifdd_keycloak_prj_name", "IFDD Keycloak")
    assert realm["loginTheme"] == "ifdd"
    assert realm["displayName"] == name


def test_theme_is_copied_unrendered(instance):
    theme = instance / "themes" / "ifdd" / "login"
    for rel in ("theme.properties", "resources/css/ifdd.css"):
        assert (theme / rel).read_bytes() == \
            (ROOT / "{{cookiecutter.ifdd_keycloak_prj_slug}}" / "themes" / "ifdd" / "login" / rel).read_bytes()
    props = dict(line.split("=", 1) for line in (theme / "theme.properties").read_text().splitlines()
                 if line and not line.startswith("#"))
    assert props["parent"] == "keycloak.v2"
    assert props["styles"].split() == ["css/styles.css", "css/ifdd.css"]   # keeps the parent's styles
    css = (theme / "resources" / "css" / "ifdd.css").read_text()
    assert "url(" not in css and "@import" not in css        # nothing external (CSP)


@pytest.mark.parametrize("name", ["docker-compose-production.yml", "docker-compose-development.yml"])
def test_theme_is_mounted(instance, name):
    volumes = yaml.safe_load((instance / name).read_text())["services"]["keycloak"]["volumes"]
    assert "./themes/ifdd:/opt/keycloak/themes/ifdd:ro" in volumes

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
    # title in a TOML string; with an own slug, so that only the name check applies
    {"ifdd_keycloak_prj_name": "IFDD\\Keycloak", "ifdd_keycloak_prj_slug": "kc"},
    # backup: pg_dump must match the server's major version
    {"ifdd_keycloak_backup_image": "prodrigestivill/postgres-backup-local:17"},
    {"ifdd_keycloak_backup_image": "prodrigestivill/postgres-backup-local"},
    {"ifdd_keycloak_postgres_image": "postgres:latest"},
    {"ifdd_keycloak_backup_schedule": "@every ${HOURS}h"},   # compose would interpolate
    {"ifdd_keycloak_backup_schedule": ""},
    {"ifdd_keycloak_backup_timezone": "Europe/ Berlin"},
    {"ifdd_keycloak_backup_keep_days": "seven"},
])
def test_pre_hook_rejects(tmp_path, extra):
    with pytest.raises(FailedHookException):
        render(tmp_path, **extra)


# --- backup and restore -----------------------------------------------------------

RESTORE = "adm_backup_restore.sh"


def env_of(inst):
    return dict(line.split("=", 1) for line in (inst / ".env").read_text().splitlines()
                if line and not line.startswith("#"))


def test_backup_service(instance, fixture_name):
    ctx = json.loads((ROOT / "cookiecutter.json").read_text())
    ctx.update(yaml.safe_load(fixture_name.read_text())["default_context"])
    backup = yaml.safe_load((instance / "docker-compose-production.yml").read_text())["services"]["backup"]
    assert backup["image"] == ctx["ifdd_keycloak_backup_image"]
    # the host user that owns ./backups, required from .env
    assert backup["user"] == "${IFDD_KEYCLOAK_BACKUP_UID:?set in .env}:${IFDD_KEYCLOAK_BACKUP_GID:?set in .env}"
    env = backup["environment"]
    assert env["POSTGRES_HOST"] == "postgres" and env["POSTGRES_DB"] == env["POSTGRES_USER"] == "keycloak"
    assert env["POSTGRES_PASSWORD"] == "${IFDD_KEYCLOAK_DB_PASSWORD:?set in .env}"
    assert env["SCHEDULE"] == ctx["ifdd_keycloak_backup_schedule"]
    assert env["TZ"] == ctx["ifdd_keycloak_backup_timezone"]
    assert env["BACKUP_ON_START"] == "TRUE"
    for unit in ("days", "weeks", "months"):
        assert env[f"BACKUP_KEEP_{unit.upper()}"] == ctx[f"ifdd_keycloak_backup_keep_{unit}"]
    # a directory of the instance, never created by Docker (it would belong to root)
    assert backup["volumes"] == [{"type": "bind", "source": "./backups", "target": "/backups",
                                  "bind": {"create_host_path": False}}]
    assert backup["networks"] == ["db"] and "labels" not in backup and "ports" not in backup
    assert backup["depends_on"] == {"postgres": {"condition": "service_healthy"}}
    assert backup["cap_drop"] == ["ALL"] and backup["security_opt"] == ["no-new-privileges:true"]
    assert backup["restart"] == "always"


def test_no_backup_service_in_development(instance):
    services = yaml.safe_load((instance / "docker-compose-development.yml").read_text())["services"]
    assert set(services) == {"postgres", "keycloak"}


def test_backup_values_of_the_instance(tmp_path):
    inst = render(tmp_path, ifdd_keycloak_backup_schedule="0 30 2 * * *",
                  ifdd_keycloak_backup_timezone="Europe/Berlin", ifdd_keycloak_backup_keep_days="14",
                  ifdd_keycloak_backup_keep_weeks="8", ifdd_keycloak_backup_keep_months="12")
    env = yaml.safe_load((inst / "docker-compose-production.yml").read_text())["services"]["backup"]["environment"]
    assert (env["SCHEDULE"], env["TZ"]) == ("0 30 2 * * *", "Europe/Berlin")
    assert (env["BACKUP_KEEP_DAYS"], env["BACKUP_KEEP_WEEKS"], env["BACKUP_KEEP_MONTHS"]) == ("14", "8", "12")


def test_backup_directory_and_owner(instance):
    backups = instance / "backups"
    assert backups.is_dir() and stat.S_IMODE(backups.stat().st_mode) == 0o700
    env = env_of(instance)
    assert (env["IFDD_KEYCLOAK_BACKUP_UID"], env["IFDD_KEYCLOAK_BACKUP_GID"]) == \
        (str(os.getuid()), str(os.getgid()))
    assert "backups/" in (instance / ".gitignore").read_text().splitlines()


def test_hook_refuses_root(instance):
    """As root, the backup container would write the dumps as root."""
    (instance / ".env").unlink()
    (instance / "backups").rmdir()
    code = ("import os, runpy; os.getuid = lambda: 0; "
            f"runpy.run_path({str(ROOT / 'hooks' / 'post_gen_project.py')!r}, run_name='__main__')")
    result = subprocess.run([sys.executable, "-c", code], cwd=instance, capture_output=True, text=True)
    assert result.returncode == 1 and "root" in result.stderr
    assert not (instance / ".env").exists()


def test_existing_backup_directory_is_kept(instance):
    backups = instance / "backups"
    backups.chmod(0o750)
    (backups / "keycloak-latest.sql.gz").write_bytes(b"x")
    subprocess.run([sys.executable, str(ROOT / "hooks" / "post_gen_project.py")], cwd=instance, check=True)
    assert stat.S_IMODE(backups.stat().st_mode) == 0o750
    assert (backups / "keycloak-latest.sql.gz").read_bytes() == b"x"


def test_restore_script_is_executable_and_parses(instance):
    script = instance / RESTORE
    assert script.stat().st_mode & stat.S_IXUSR
    subprocess.run(["bash", "-n", str(script)], check=True)
    if shutil.which("shellcheck"):
        subprocess.run(["shellcheck", str(script)], check=True)


# A stand-in for docker: logs every call and plays the containers of the
# compose project. STUB_FAIL_LOAD makes the load of the dump fail.
DOCKER_STUB = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
args=" $* "
case "$args" in
  *" exec -T postgres psql "*"pg_database"*) echo "${STUB_DB_EXISTS-1}" ;;
  *" exec -T postgres psql "*"ON_ERROR_STOP=1"*)
      cat > "$STUB_LOADED"; [ -z "$STUB_FAIL_LOAD" ] || { echo "ERROR: broken" >&2; exit 3; } ;;
  *" exec -T postgres pg_dump "*) echo "-- the database before the restore" ;;
esac
exit 0
"""


def run_restore(inst, tmp_path, *args, answer="restore", tty=True, **env):
    """Run the restore script with the docker stub, on a pseudo terminal."""
    bindir = tmp_path / "stub-bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "docker"
    stub.write_text(DOCKER_STUB)
    stub.chmod(0o755)
    log, loaded = tmp_path / "docker.log", tmp_path / "loaded.sql"
    environ = dict(os.environ, PATH=f"{bindir}:{os.environ['PATH']}", STUB_LOG=str(log),
                   STUB_LOADED=str(loaded), **env)
    cmd = [str(inst / RESTORE), *args]
    if not tty:
        result = subprocess.run(cmd, env=environ, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr, log, loaded
    pid, fd = pty.fork()
    if pid == 0:                         # child: never return into pytest
        try:
            os.chdir(tmp_path)
            os.execvpe(cmd[0], cmd, environ)
        finally:
            os._exit(127)
    out, sent = b"", False
    while select.select([fd], [], [], 30)[0]:
        try:
            chunk = os.read(fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        out += chunk
        if not sent and b'Type "restore"' in out:
            os.write(fd, answer.encode() + b"\n")
            sent = True
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status), out.decode(errors="replace"), log, loaded


def calls(log):
    return [line.split(" ", 3)[-1] for line in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture
def dump(tmp_path):
    path = tmp_path / "keycloak-20261021.sql.gz"
    path.write_bytes(gzip.compress(b"-- the dump\nSELECT 1;\n"))
    return path


def test_restore(instance, tmp_path, dump):
    code, out, log, loaded = run_restore(instance, tmp_path, str(dump))
    assert code == 0, out
    lines = log.read_text().splitlines()
    assert all(line.startswith("compose -f docker-compose-production.yml ") for line in lines)
    steps = [line.split(" ", 3)[3] for line in lines]
    assert steps[0].startswith("exec -T postgres pg_isready")
    assert steps[1] == "stop keycloak backup"
    assert [s.split()[3] for s in steps[2:7]] == ["psql", "pg_dump", "dropdb", "createdb", "psql"]
    assert steps[4].endswith("--force keycloak") and steps[5].endswith("-O keycloak keycloak")
    assert steps[7] == "up -d keycloak backup" and len(steps) == 8
    assert loaded.read_text() == "-- the dump\nSELECT 1;\n"
    safety = list((instance / "backups" / "pre-restore").glob("keycloak-*.sql.gz"))
    assert len(safety) == 1 and stat.S_IMODE(safety[0].stat().st_mode) == 0o600
    assert gzip.decompress(safety[0].read_bytes()) == b"-- the database before the restore\n"


def test_restore_without_a_database(instance, tmp_path, dump):
    """An interrupted restore can leave no database: restore anyway, without a safety dump."""
    code, out, log, _ = run_restore(instance, tmp_path, str(dump), STUB_DB_EXISTS="")
    assert code == 0, out
    assert not any(" pg_dump " in f" {c} " for c in calls(log))
    assert not (instance / "backups" / "pre-restore").exists()


def test_restore_failure_keeps_keycloak_stopped(instance, tmp_path, dump):
    code, out, log, _ = run_restore(instance, tmp_path, str(dump), STUB_FAIL_LOAD="1")
    assert code != 0
    assert not any(c.startswith("up ") for c in calls(log))
    assert "Keycloak stays stopped" in out and "backups/pre-restore/keycloak-" in out


@pytest.mark.parametrize("answer", ["", "yes", "Restore"])
def test_restore_needs_the_confirmation(instance, tmp_path, dump, answer):
    code, out, log, _ = run_restore(instance, tmp_path, str(dump), answer=answer)
    assert code == 1 and "nothing changed" in out
    assert not any(c.startswith(("stop", "exec -T postgres dropdb")) for c in calls(log))


def test_restore_refuses(instance, tmp_path, dump):
    broken = tmp_path / "broken.sql.gz"
    broken.write_bytes(dump.read_bytes()[:-8])                      # truncated
    for args, tty, message in [((str(broken),), True, "not a complete gzip file"),
                               ((str(tmp_path / "missing.sql.gz"),), True, "cannot read"),
                               ((str(dump),), False, "needs a terminal")]:
        code, out, log, _ = run_restore(instance, tmp_path, *args, tty=tty)
        assert code == 1 and message in out
        assert calls(log) == []
    code, out, _, _ = run_restore(instance, tmp_path, tty=False)
    assert code == 2 and "usage" in out
