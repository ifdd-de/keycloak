(ifdd-keycloak-troubleshooting)=
# Fehlersuche

Bekannte Fehlerbilder aus Einrichtungen von IFDD-Knoten. Beginnen mit
`docker compose -f docker-compose-production.yml logs keycloak` und den Events
des Realms in der Admin-Konsole.

## Start

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `docker compose` bricht mit `... set in .env` ab | eine Pflichtvariable fehlt in `.env`, etwa `IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET` nach einem Template-Update (`.env` steht auf der Skip-Liste) | den Eintrag ergänzen; für den User-Admin-Client auch den Client anlegen ({ref}`ifdd-keycloak-realm`) |
| der Container steht minutenlang auf `starting` | der erste Start baut Keycloak und importiert den Realm | warten; der Healthcheck lässt 180 s Zeit |
| Keycloak erreicht die Datenbank nach einer Änderung an `.env` nicht | die Datenbank behält das Passwort, mit dem sie angelegt wurde | das alte `IFDD_KEYCLOAK_DB_PASSWORD` zurücksetzen oder das Passwort auch in PostgreSQL ändern |
| `unhealthy`, obwohl Keycloak läuft | die Datenbank fehlt (die Readiness umfasst sie); Docker startet unhealthy-Container nicht neu | die Datenbank wiederherstellen; `docker compose ps` zeigt beide |
| `build_realm.py` scheitert an einer unbekannten Keycloak-Version | für diesen Image-Tag gibt es keine Datei mit eingebauten Scopes | eine Keycloak-Version nehmen, die das Template kennt |

## Sicherung und Wiederherstellung

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `docker compose` bricht mit `IFDD_KEYCLOAK_BACKUP_UID ... set in .env` ab | die Instanz ist älter als der Backup-Dienst; `cruft update` lässt `.env` unberührt | `IFDD_KEYCLOAK_BACKUP_UID` und `IFDD_KEYCLOAK_BACKUP_GID` mit den Werten von `id -u` und `id -g` des Benutzers ergänzen, dem die Dumps gehören sollen |
| `bind source path does not exist: .../backups` | `backups/` fehlt, etwa in einem frischen Klon oder nach dem Template-Update, das den Backup-Dienst brachte (Git hält keine leeren Verzeichnisse) | `mkdir -m 700 backups` als der Benutzer aus `IFDD_KEYCLOAK_BACKUP_UID` |
| `backup` startet immer wieder neu, sein Log meldet `BACKUP_DIR points to a file or folder with insufficient permissions` | `backups/` gehört einem anderen Benutzer als `IFDD_KEYCLOAK_BACKUP_UID`, etwa root | es diesem Benutzer geben: `chown -R <uid>:<gid> backups` |
| `backup` ist `unhealthy` | der letzte Dump scheiterte, etwa weil die Datenbank fehlte | `docker compose -f docker-compose-production.yml logs backup`; der nächste erfolgreiche Dump macht ihn wieder healthy |
| die Dumps entstehen zu einer unerwarteten Stunde | der Zeitplan läuft in der Zeitzone `TZ` des Containers; ein unbekannter Name fällt auf UTC zurück | `TZ` in der Compose-Datei und die Daten in den Dateinamen prüfen |
| der Post-Generation-Hook bricht mit `refusing to run as root` ab | die Instanz wurde als root erzeugt | sie als der Benutzer erzeugen, dem die Dumps gehören sollen |
| `adm_backup_restore.sh` meldet `needs a terminal to confirm` | es lief ohne Terminal, etwa aus cron oder einer Pipe | es in einer interaktiven Shell aufrufen |
| die Wiederherstellung bricht mit `the restore failed; Keycloak stays stopped` ab | der Dump ließ sich nicht einspielen (siehe die Meldung von `psql` darüber) | den Sicherheits-Dump, den das Skript nennt, mit demselben Skript zurückspielen |

## Realm

| Symptom | Ursache | Abhilfe |
|---|---|---|
| eine Änderung in `values.toml` oder nach `cruft update` wirkt nicht | der Import läuft nur, solange der Realm nicht existiert | die Änderung in der Admin-Konsole vornehmen ({ref}`ifdd-keycloak-operations`) |
| `realm/build_realm.py --check` scheitert in der CI | `values.toml` oder `realm/ifdd_realm/` geändert, ohne neu zu erzeugen | `python3 realm/build_realm.py` ausführen, die erzeugten Dateien committen |
| die Anmeldeseite sieht aus wie das Standard-Theme von Keycloak | der Realm wurde vor dem Theme importiert, oder `themes/ifdd` ist nicht eingehängt | das Theme in der Admin-Konsole setzen ({ref}`ifdd-keycloak-realm`); die Volumes der Compose-Datei prüfen |
| eine Änderung am Theme wirkt nicht | Keycloak puffert Themes außerhalb von `start-dev` | Keycloak neu starten |
| `build_realm.py` bricht mit `realm '...' is named in ...` ab | zwei Werte-Dateien nennen denselben Realm | jedem weiteren Realm einen eigenen `name` geben |
| das erste `cruft update` nach dem Template vom 2026-10-20 meldet Patch-Fehler zu `realm/ifdd_realm/__pycache__/*.pyc` | das ältere Template schrieb Bytecode, wenn sein Hook `build_realm.py` ausführte; er unterscheidet sich bei jedem Rendern | dieses Update als `PYTHONDONTWRITEBYTECODE=1 cruft update` ausführen oder vorher `realm/ifdd_realm/__pycache__` löschen; spätere Updates brauchen nichts |
| ein Client-Secret aus `.env` funktioniert nicht | der Realm wurde mit einem anderen Wert importiert, oder das Secret wurde in Keycloak rotiert | das Secret aus der Admin-Konsole nehmen (Client, „Credentials“) |

## Anmeldungen

| Symptom | Ursache | Abhilfe |
|---|---|---|
| `Invalid parameter: redirect_uri` | die Redirect-URI des Dienstes ist nicht genau eine des Clients | mit {ref}`ifdd-keycloak-realm` vergleichen; die Dienst-URL oder den Client in der Admin-Konsole korrigieren |
| das Backend weist Tokens ab (Issuer) | `IFDD_KEYCLOAK_HOST` passt nicht zum Host von `{{ cookiecutter.ifdd_oidc_realm }}` | den Host aus `ifdd_oidc_realm` setzen, neu starten |
| Benutzer werden abgemeldet, wenn mehrere Tabs offen sind | Rotation der Refresh-Tokens: jedes gilt einmal | erwartet |
| ein Konto ist nach Fehlversuchen gesperrt | Brute-Force-Schutz | warten oder den Benutzer in der Admin-Konsole entsperren |
| „Account is not fully set up“ beim Password Grant, oder ein Formular bei der ersten Anmeldung | das User Profile von Keycloak verlangt E-Mail, Vor- und Nachname | ausfüllen; den Password Grant bieten die IFDD-Clients ohnehin nicht an |
| Anmeldung gegen die Entwicklungsinstanz scheitert für die anderen Dienste | die Redirect-URIs nennen die Produktions-Hosts | die Produktionsinstanz nutzen |

## Rechte

| Symptom | Ursache | Abhilfe |
|---|---|---|
| 403 vom Backend, obwohl die Anmeldung klappt | der Benutzer ist in keiner Knotengruppe | ihn zu `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` oder einer anderen Knotengruppe hinzufügen |
| 403 nur für Domain-Kontexte | Benutzer oder Service-Account hat kein Kontextmuster | Gruppe `ifdd_ctx_<pattern>`; für einen älteren Realm siehe {ref}`ifdd-keycloak-realm` |
| das Login-Gate des Proxys weist einen Benutzer ab | keine bestätigte E-Mail-Adresse, oder nicht in der Gruppe, die der Dienst verlangt | Adresse setzen und bestätigen; Gruppe zuordnen |
