(ifdd-keycloak-setup)=
# Einrichtung

## Voraussetzungen

| Was | Warum |
|---|---|
| Docker mit Compose | Keycloak und PostgreSQL laufen als zwei Container |
| das externe Netz `{{ cookiecutter.ifdd_proxy_network }}` und eine laufende Proxy-Instanz | Traefik routet `{{ cookiecutter.ifdd_keycloak_host }}` anhand der Labels dieses Dienstes zu Keycloak |
| das Zertifikat des Proxys deckt `{{ cookiecutter.ifdd_keycloak_host }}` ab | mit eigenen Zertifikaten muss der Host unter dessen Namen sein (`adm_01_certs.sh` des Proxys nimmt `ifdd_proxy_internal_hosts`) |
| der Proxy führt `{{ cookiecutter.ifdd_keycloak_host }}` in `ifdd_proxy_internal_hosts` | Dienste rufen Keycloak unter seinem öffentlichen Host auf; in den Containern muss dieser Name zu Traefik führen |

## Instanz anlegen

Üblicherweise legt das Meta-Repository alle Instanzen in einem Zug an
(`.adm_meta_01_all.sh`, Schritt `.adm_01_create_services.sh`): Es ruft
`cruft create` mit der gemeinsamen Variablendatei `.cookiecutter_all.yaml`
auf und kopiert danach die Client-Secrets aus dieser `.env` zu den Diensten,
die sie nutzen.

Von Hand, im Verzeichnis der Instanzen:

```bash
cruft create --no-input --config-file .cookiecutter_all.yaml \
  --skip .env \
  https://github.com/ifdd-de/keycloak
```

`.env` enthält die erzeugten Secrets; die Skip-Liste hält sie aus jedem
späteren `cruft update` heraus.

## Konfiguration und Secrets

Der Post-Generation-Hook schreibt `.env` aus `dotenv.dist` (eine vorhandene
`.env` bleibt unberührt) und ersetzt jeden Platzhalter durch einen
Zufallswert:

| Eintrag | Inhalt |
|---|---|
| `IFDD_KEYCLOAK_ADMIN_PASSWORD` | Passwort des temporären Admins `IFDD_KEYCLOAK_ADMIN_USER` im Master-Realm |
| `IFDD_KEYCLOAK_DB_PASSWORD` | Passwort des Datenbankbenutzers `keycloak` |
| `IFDD_KEYCLOAK_*_CLIENT_SECRET` | die Secrets der vertraulichen Clients, gelesen vom Realm-Import |
| `IFDD_KEYCLOAK_BACKUP_UID`, `IFDD_KEYCLOAK_BACKUP_GID` | Benutzer- und Gruppen-ID des Benutzers, der die Instanz erzeugt; der Backup-Dienst schreibt die Dumps als dieser Benutzer |

Er legt das Verzeichnis `backups/` (Rechte 0700) für die Dumps des
Backup-Dienstes an. Als root bricht der Hook ab: Die Dumps gehörten sonst
root. Die Instanz als der Benutzer erzeugen, dem sie gehören sollen.

Danach führt er `realm/build_realm.py` aus, das
`realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json` und
`realm/OVERVIEW.md` aus `realm/values.toml` schreibt. Alle übrigen Werte
kommen aus den Variablen des Templates; sie stehen mit ihren Werten und ihrer
Bedeutung in {ref}`ifdd-instances-keycloak`. Die Einträge von `.env` stehen in
{ref}`ifdd-keycloak-reference`.

## Erster Start

```bash
docker compose -f docker-compose-production.yml up -d
docker compose -f docker-compose-production.yml logs -f keycloak
```

Der erste Start baut Keycloak und importiert den Realm; das Log meldet
`Realm '{{ cookiecutter.ifdd_keycloak_realm }}' imported`. Der Healthcheck
lässt dafür 180 Sekunden Zeit.

Dann unter `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` mit
`IFDD_KEYCLOAK_ADMIN_USER` und `IFDD_KEYCLOAK_ADMIN_PASSWORD` aus `.env`
anmelden. Dieser Admin ist temporär: einen dauerhaften Admin im Master-Realm
anlegen, dann den temporären löschen.

## Client-Secrets für die Dienste

Jeder vertrauliche Client hat sein Secret in `.env`. Das Meta-Repository
kopiert sie; von Hand:

| Client | Dienst | Secret in dieser `.env` | Gehört nach |
|---|---|---|---|
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | wf, Skripte | `IFDD_KEYCLOAK_API_CLIENT_SECRET` | `secrets/kestra.env` von wf (`IFDD_API_CLIENT_SECRET`), Skripte |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | ct | `IFDD_KEYCLOAK_CT_CLIENT_SECRET` | `IFDD_CT_OIDC_CLIENT_SECRET` in der `.env` von ct |
| `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | `keycloak_add_user.py` des Meta-Repositorys | `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` | wird aus dieser `.env` gelesen |
| `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | ts (Grafana) | `IFDD_KEYCLOAK_TS_CLIENT_SECRET` | `secrets/oidc_client_secret` von ts |
| `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | proxy (oauth2-proxy) | `IFDD_KEYCLOAK_PROXY_CLIENT_SECRET` | `secrets/oauth2_proxy_client_secret` des Proxys |

`{{ cookiecutter.ifdd_oidc_backend_client_id }}` ist public und hat kein
Secret. Der Import liest diese Secrets nur beim ersten Start; danach hält
Keycloak eine eigene Kopie ({ref}`ifdd-keycloak-operations`).

## Menschen und Gruppen

Menschen in der Admin-Konsole oder mit `keycloak_add_user.py` des
Meta-Repositorys anlegen und Gruppen zuordnen. Ein neuer Benutzer hat nur
`{{ cookiecutter.ifdd_keycloak_role_public }}` (angemeldet, keine weiteren
Rechte):

| Gruppe | Rechte |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` | Knoten lesen |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_writers }}` | Knoten lesen und schreiben |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_privileged }}` | lesen und privilegierter Zugriff |
| `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}` | Zugang zu wf (Login-Gate) |
| `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}` | jeder Domain-Kontext (Kontextmuster `{{ cookiecutter.ifdd_context_root }}`); zusammen mit einer Knotengruppe |

Basis- und Aspekt-Kontexte brauchen nur eine Knotengruppe. Ein
Domain-Kontext wie `sub1.dom1.{{ cookiecutter.ifdd_context_root }}` braucht
zusätzlich ein Kontextmuster; Gruppen für weitere Muster legt
`keycloak_add_context_role.py` des Meta-Repositorys an
({ref}`ifdd-keycloak-realm`).

Für Grafana die Realm-Rollen `{{ cookiecutter.ifdd_ts_role_admin }}`,
`{{ cookiecutter.ifdd_ts_role_editor }}` oder `{{ cookiecutter.ifdd_ts_role_viewer }}`
zuweisen. Keycloak fragt bei der ersten Anmeldung nach E-Mail, Vor- und
Nachname, wenn sie fehlen. Das Login-Gate des Proxys lässt nur Benutzer
durch, deren E-Mail-Adresse als bestätigt markiert ist.

## Lokale Entwicklung

```bash
docker compose -f docker-compose-development.yml up -d
```

Die Admin-Konsole liegt unter
`http://127.0.0.1:{{ cookiecutter.ifdd_keycloak_dev_port }}/admin/`
(`IFDD_KEYCLOAK_DEV_PORT`): `start-dev`, reines HTTP, kein Proxy, dasselbe
Datenbank-Volume und derselbe Realm-Import. Die Redirect-URIs des Realms
nennen die Produktions-Hosts, daher können sich die anderen Dienste nicht
gegen diese Instanz anmelden.
