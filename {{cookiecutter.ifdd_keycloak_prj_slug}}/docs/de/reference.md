(ifdd-keycloak-reference)=
# Referenz

Die Variablen des Templates und ihre Werte in dieser Instanz stehen in
{ref}`ifdd-instances-keycloak`. Diese Seite führt auf, was keine
Template-Variable ist.

## Aufbau

| Pfad | Zweck |
|---|---|
| `docker-compose-production.yml` | Keycloak hinter dem Proxy, PostgreSQL |
| `docker-compose-development.yml` | `start-dev` auf 127.0.0.1, ohne Proxy |
| `dotenv.dist` → `.env` | erzeugte Secrets und der Host, nie committet |
| `realm/values.toml` | Werte des Realms, von cruft geschrieben |
| `realm/build_realm.py`, `realm/ifdd_realm/` | das Skript und sein Modell |
| `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json` | erzeugte Importdatei, nur lesend in Keycloak eingebunden |
| `realm/OVERVIEW.md` | erzeugt: der Realm als Tabellen |
| `realm/values_*.toml` | optional: Werte weiterer Realms, von Hand geschrieben |
| `realm/OVERVIEW-<realm>.md` | erzeugt: die Übersicht eines weiteren Realms |
| `themes/ifdd/` | Login-Theme des Realms, nur lesend in Keycloak eingehängt |
| `adm_backup_restore.sh` | spielt einen Dump des Backup-Dienstes zurück ({ref}`ifdd-keycloak-operations`) |
| `backups/` | die Dumps des Backup-Dienstes, in ihn eingebunden; vom Hook angelegt, nie committet |

## Umgebung (`.env`)

| Variable | Vorgabe hier | Genutzt von |
|---|---|---|
| `IFDD_KEYCLOAK_HOST` | `{{ cookiecutter.ifdd_keycloak_host }}` | Router-Regel, `KC_HOSTNAME` |
| `IFDD_KEYCLOAK_DEV_PORT` | `{{ cookiecutter.ifdd_keycloak_dev_port }}` | Entwicklungsport auf 127.0.0.1 |
| `IFDD_KEYCLOAK_ADMIN_USER`, `IFDD_KEYCLOAK_ADMIN_PASSWORD` | `{{ cookiecutter.ifdd_keycloak_admin_user }}`, erzeugt | temporärer Admin des Master-Realms, nur erster Start |
| `IFDD_KEYCLOAK_DB_PASSWORD` | erzeugt | PostgreSQL und Keycloak |
| `IFDD_KEYCLOAK_API_CLIENT_SECRET` | erzeugt | Client `{{ cookiecutter.ifdd_keycloak_api_client_id }}` |
| `IFDD_KEYCLOAK_CT_CLIENT_SECRET` | erzeugt | Client `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` |
| `IFDD_KEYCLOAK_USERADMIN_CLIENT_ID`, `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` | `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}`, erzeugt | Client `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}`; die ID ist für die Skripte des Meta-Repositorys |
| `IFDD_KEYCLOAK_TS_CLIENT_SECRET` | erzeugt | Client `{{ cookiecutter.ifdd_ts_oidc_client_id }}` |
| `IFDD_KEYCLOAK_PROXY_CLIENT_SECRET` | erzeugt | Client `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` |
| `IFDD_KEYCLOAK_BACKUP_UID`, `IFDD_KEYCLOAK_BACKUP_GID` | IDs des Benutzers, der die Instanz erzeugt hat | Benutzer des Backup-Dienstes, Eigentümer der Dumps |

Die Client-Secrets erreichen den Keycloak-Container als gleichnamige
Umgebungsvariablen; die Realm-Datei verweist als Platzhalter auf sie.

## Endpunkte

| Endpunkt | URL |
|---|---|
| Issuer | `{{ cookiecutter.ifdd_oidc_realm }}` |
| Discovery | `{{ cookiecutter.ifdd_oidc_realm }}/.well-known/openid-configuration` |
| Autorisierung | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/auth` |
| Token | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/token` |
| Signaturschlüssel (JWKS) | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/certs` |
| Userinfo | `{{ cookiecutter.ifdd_oidc_realm }}/protocol/openid-connect/userinfo` |
| Admin-Konsole | `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` |

## Container, Ports und Netze

| Container | Port | Netz |
|---|---|---|
| `keycloak` | 8080 HTTP (vom Proxy geroutet), 9000 Management (`/health`, `/metrics`, nicht geroutet) | `db`, `{{ cookiecutter.ifdd_proxy_network }}` |
| `postgres` | 5432 | `db` |
| `backup` | 8080 Healthcheck seines Schedulers (nicht geroutet); `BACKUP_*`, `SCHEDULE`, `TZ` in der Compose-Datei gesetzt | `db` |

| Volume | Inhalt |
|---|---|
| `postgres-data` | die Datenbank, eingebunden unter `/var/lib/postgresql` (PostgreSQL 18 hält seine Daten in einem versionierten Unterverzeichnis) |

`backups/` ist ein Bind-Mount unter `/backups` von `backup`, kein Volume:
`docker compose down --volumes` lässt es stehen. Compose legt es nicht an
(`create_host_path: false`).

Labels: der Router `{{ cookiecutter.ifdd_keycloak_prj_slug }}` mit der Regel
`Host(<IFDD_KEYCLOAK_HOST>)`, Service-Port 8080, Middleware
`security-headers@file`, Netz `{{ cookiecutter.ifdd_proxy_network }}`.
