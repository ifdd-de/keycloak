(ifdd-keycloak-security)=
# Sicherheit

Keycloak entscheidet, wer sich anmeldet und welche Rollen die Tokens tragen.
Jeder Dienst des Knotens vertraut diesen Tokens; eine Schwäche hier ist eine
Schwäche überall.

## Transport und Proxy

- TLS endet am Proxy. Keycloak spricht intern reines HTTP
  (`KC_HTTP_ENABLED`) und bildet seine öffentlichen URLs aus
  `KC_HOSTNAME=https://{{ cookiecutter.ifdd_keycloak_host }}`; der Issuer der
  Tokens ist daher `{{ cookiecutter.ifdd_oidc_realm }}`.
- `KC_PROXY_HEADERS=xforwarded`: Keycloak nimmt Client-Adresse und Schema aus
  den `X-Forwarded-*`-Headern. Es vertraut ihnen von jedem Container in
  `{{ cookiecutter.ifdd_proxy_network }}`; `KC_PROXY_TRUSTED_ADDRESSES` kann
  das einschränken, sobald der Adressbereich dieses Netzes feststeht.
- Der Router hängt nur `security-headers` des Proxys an, keine `csp-*`:
  Keycloak setzt für Admin-Konsole und Anmeldeseiten eine eigene
  Content-Security-Policy, die die strenge `csp-api` zerstören würde.
- Der Realm verlangt TLS für externe Adressen (`sslRequired: external`).

## Administration

- Der Admin aus `.env` (`IFDD_KEYCLOAK_ADMIN_USER`) ist ein temporärer
  Bootstrap-Admin des Master-Realms. Einen dauerhaften Admin anlegen, dann ihn
  löschen.
- Die Admin-Konsole ist wie alles andere über den Proxy erreichbar, unter
  `https://{{ cookiecutter.ifdd_keycloak_host }}/admin/`. Die Admin-Konten
  entsprechend schützen.
- Der Client `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` hat
  `manage-users` von `realm-management`: Wer sein Secret hat, kann Benutzer
  anlegen, ändern, sperren und löschen, jeden in jede Gruppe setzen (auch
  `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}`) und Gruppen anlegen. Sein
  Secret wie ein Admin-Passwort hüten.

## Secrets

| Secret | Wo | Hinweis |
|---|---|---|
| Admin-Passwort | `.env` | nur für den ersten Start |
| Datenbankpasswort | `.env` | einmal gesetzt; die Datenbank behält es |
| Client-Secrets | `.env`, dann in Keycloak und in den Diensten | vom ersten Import gelesen; in der Admin-Konsole rotieren |
| Datenbank-Dumps | `backups/` | enthalten Passwort-Hashes, Sitzungen und die Client-Secrets der Datenbank; Rechte 0700, Eigentümer ist der Backup-Benutzer |

`.env` entsteht mit erzeugten Werten (32 bis 48 Zeichen mit Klein- und
Großbuchstaben und Ziffern), wird nie committet und steht auf der Skip-Liste.
Die Compose-Dateien verlangen jedes Secret (`${...:?}`): Eine nicht gesetzte
Variable würde sonst zum wörtlichen Secret im Realm. `realm/` enthält keine
Passwörter und keine persönlichen Benutzer. Auch `backups/` wird nicht
committet; eine Kopie davon auf einem anderen System braucht denselben Schutz
wie die Datenbank.

## Regeln des Realms

Der Realm folgt RFC 9700 (OAuth 2.0 Security Best Current Practice):

| Thema | Regel |
|---|---|
| public Client `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | Authorization Code mit PKCE S256 Pflicht, kein Implicit Flow; exakte Redirect-URIs, keine Muster |
| vertrauliche Clients für Skripte und ct | nur Client Credentials, keine Browser-Anmeldung, kein Password Grant |
| Offline-Tokens | kein Client bietet den Scope `offline_access` an |
| Audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}` | nur in den Tokens der Clients, die das Backend aufrufen |
| Full Scope | aus für den Backend-Client, ts, ct und den User-Admin-Client; sie bekommen Scope-Mappings für die Rollen, die sie brauchen |
| Rechte | die Standardrolle gewährt nur `{{ cookiecutter.ifdd_keycloak_role_public }}`; Lesen, Schreiben und privilegierter Zugriff kommen aus Gruppen |
| Refresh-Tokens | rotiert: jedes gilt einmal |
| Anmeldungen | Brute-Force-Schutz mit den Schwellen von Keycloak; Passwort-Policy: mindestens 12 Zeichen, nicht der Benutzername |
| Events | Login-Events 30 Tage aufbewahrt; Admin-Events ohne Repräsentationen |

Die Tests des Templates prüfen diese Regeln in der erzeugten Realm-Datei.
Einzelheiten je Client stehen in {ref}`ifdd-keycloak-realm` und in
`realm/OVERVIEW.md`.

## Container

Keycloak läuft ohne alle Capabilities (`cap_drop: ALL`) und mit
`no-new-privileges`, PostgreSQL mit `no-new-privileges`. PostgreSQL hängt nur
im Netz `db`, das der Proxy nicht erreicht. Der Backup-Dienst läuft als der
Benutzer des Hosts aus `IFDD_KEYCLOAK_BACKUP_UID`, nicht als root, ohne
Capabilities und mit `no-new-privileges`, nur im Netz `db`; er kennt das
Datenbankpasswort.

Der Management-Port 9000 (`/health`, `/metrics`) wird vom Proxy nicht
geroutet, ist aber für Container in denselben Netzen erreichbar.
