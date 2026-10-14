(ifdd-keycloak-index)=
# {{ cookiecutter.ifdd_keycloak_prj_name }} (keycloak)

Der Identity Provider eines IFDD-Knotens: Keycloak mit eigenem PostgreSQL,
hinter dem Proxy. Er hält den Realm mit den Clients der IFDD-Dienste, meldet
Menschen und Service-Accounts an und stellt die Access-Tokens aus, die das
Backend und die anderen Dienste prüfen. Dieses Kapitel beschreibt die Instanz
`{{ cookiecutter.ifdd_keycloak_prj_slug }}`, erzeugt aus dem Template
`ifdd-de/keycloak`, aus Sicht derer, die sie einrichten, betreiben und
absichern.

| | |
|---|---|
| Öffentliche URL | `https://{{ cookiecutter.ifdd_keycloak_host }}` (vom Proxy geroutet) |
| Realm | `{{ cookiecutter.ifdd_keycloak_realm }}`, Issuer `{{ cookiecutter.ifdd_oidc_realm }}` |
| Admin-Konsole | `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` |
| Images | `{{ cookiecutter.ifdd_keycloak_image }}`, `{{ cookiecutter.ifdd_keycloak_postgres_image }}` (Upstream, kein eigenes Image) |
| Netz | `{{ cookiecutter.ifdd_proxy_network }}` (Proxy) und `db` (nur Keycloak und PostgreSQL) |
| Entwicklung | `http://127.0.0.1:{{ cookiecutter.ifdd_keycloak_dev_port }}/admin/` |

## Was die Instanz enthält

Zwei Compose-Dateien, `.env` mit erzeugten Secrets und den Realm: die
Importdatei `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json`,
das Skript, das sie aus `realm/values.toml` erzeugt, und `realm/OVERVIEW.md`,
den Realm als Tabellen. Keycloak importiert den Realm nur beim ersten Start;
danach ist seine Datenbank maßgeblich ({ref}`ifdd-keycloak-realm`).

## Architektur

```{mermaid}
flowchart LR
  Browser -->|HTTPS| Proxy[proxy: Traefik]
  Services[be, ct, ts, oauth2-proxy, Skripte] -->|"{{ cookiecutter.ifdd_keycloak_host }}"| Proxy
  Proxy -->|HTTP 8080| KC[keycloak]
  KC -->|Netz db| PG[(PostgreSQL)]
```

TLS endet am Proxy; Keycloak spricht intern reines HTTP und nimmt die
öffentliche URL aus `KC_HOSTNAME`. Auch Dienste erreichen ihn unter seinem
öffentlichen Hostnamen: Im Proxy-Netz ist dieser Name ein Netz-Alias von
Traefik.

| Wer | Client | Nutzt Keycloak für |
|---|---|---|
| ui (Browser) | `{{ cookiecutter.ifdd_oidc_backend_client_id }}` (public) | Anmeldung mit Authorization Code und PKCE |
| be | `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | Prüfen der Access-Tokens (Signaturschlüssel, Issuer, Audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}`); „Authorize“ in seiner Swagger UI |
| ct | `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | Client Credentials zum Schreiben |
| ts (Grafana) | `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | Anmeldung von Menschen, Client Credentials |
| proxy (oauth2-proxy) | `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | das Login-Gate vor Diensten ohne eigene Anmeldung |
| wf, Skripte | `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | Client Credentials zum Lesen |
| Benutzer-Skripte des Meta-Repositorys | `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | Benutzer anlegen und Gruppen zuordnen |

## Kapitel

```{toctree}
:maxdepth: 2

setup
build-release
operations
security
troubleshooting
reference
realm
```

Die Werte der Variablen dieser Instanz und ihre Beziehungen zu den anderen
Diensten stehen im Kapitel über die Dienst-Instanzen
({ref}`ifdd-instances-keycloak`).
