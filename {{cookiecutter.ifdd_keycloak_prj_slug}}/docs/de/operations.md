(ifdd-keycloak-operations)=
# Betrieb

## Starten, Stoppen, Reihenfolge

```bash
docker compose -f docker-compose-production.yml up -d
docker compose -f docker-compose-production.yml ps
docker compose -f docker-compose-production.yml down        # behält das Datenbank-Volume
```

Reihenfolge auf dem Knoten: zuerst Traefik, dann Keycloak und die anderen
Dienste, dann der vollständige Proxy mit oauth2-proxy, der beim Start einen
erreichbaren Realm braucht. `.adm_03_up_services.sh` des Meta-Repositorys
macht genau das. Innerhalb dieses Projekts wartet Keycloak auf eine gesunde
Datenbank.

## Healthchecks

| Container | Prüfung | Intervall |
|---|---|---|
| `keycloak` | `GET /health/ready` auf dem Management-Port 9000, mit bash (das Image hat kein curl) | 15 s, 5 Versuche, Startphase 180 s |
| `postgres` | `pg_isready -d keycloak -U keycloak` | 10 s, 10 Versuche |
| `backup` | aus dem Image: `curl` auf seinen Port 8080, beantwortet vom Scheduler | 5 min |

Mit `KC_METRICS_ENABLED` umfasst die Readiness die Datenbank; Keycloak wird
also unhealthy, solange die Datenbank fehlt. Docker startet einen
unhealthy-Container nicht von selbst neu; `docker compose ps` zeigt den
Zustand. Alle Container starten mit `restart: always` neu, wenn sie sich
beenden. Der Healthcheck von `backup` zeigt nur, dass der Scheduler läuft,
nicht, ob der letzte Dump gelang; das steht im Log des Containers.

## Logs

```bash
docker compose -f docker-compose-production.yml logs -f keycloak
```

Der Realm speichert Login-Events 30 Tage und Admin-Events ohne
Repräsentationen; sie stehen in der Admin-Konsole unter „Events“ des Realms.

## Der Realm nach dem ersten Start

Der Import läuft nur, solange der Realm nicht existiert. Danach ist die
Datenbank maßgeblich:

- Änderungen an der Realm-Datei, auch über `cruft update`, erreichen den
  laufenden Realm nicht; sie in der Admin-Konsole vornehmen und
  `values.toml` im Gleichlauf halten, damit ein neuer Realm dazu passt.
  {ref}`ifdd-keycloak-realm` beschreibt die Änderungen, die bestehende Realms
  brauchen.
- Die Client-Secrets in `.env` liest nur der erste Import. Ein Secret wird in
  der Admin-Konsole rotiert (Client, „Credentials“), dann in dem Dienst, der
  es nutzt.
- Um den Realm aus der Datei neu anzulegen, ihn in der Admin-Konsole löschen
  und Keycloak neu starten. Alle Benutzer und Sitzungen des Realms gehen
  verloren.

## Sicherung

Der Dienst `backup` (`{{ cookiecutter.ifdd_keycloak_backup_image }}`)
sichert die Datenbank `keycloak` mit `pg_dump`, während Keycloak weiterläuft.
Die Dumps landen im Verzeichnis `backups/` dieser Instanz, einem gewöhnlichen
Verzeichnis auf dem Host, keinem Docker-Volume:

| | Hier |
|---|---|
| Zeitplan | `{{ cookiecutter.ifdd_keycloak_backup_schedule }}`, Zeitzone `{{ cookiecutter.ifdd_keycloak_backup_timezone }}`; zusätzlich bei jedem Start des Containers |
| Aufbewahrung | die täglichen Dumps {{ cookiecutter.ifdd_keycloak_backup_keep_days }} Tage, die wöchentlichen {{ cookiecutter.ifdd_keycloak_backup_keep_weeks }} Wochen, die monatlichen {{ cookiecutter.ifdd_keycloak_backup_keep_months }} Monate; jeder einzelne Dump 24 Stunden |
| Eigentümer | der Benutzer des Hosts mit den IDs `IFDD_KEYCLOAK_BACKUP_UID` und `IFDD_KEYCLOAK_BACKUP_GID` aus `.env`; der Hook hat die des Benutzers eingetragen, der die Instanz erzeugt hat |

```text
backups/                                  Rechte 0700, vom Hook angelegt
  last/keycloak-YYYYMMDD-HHMMSS.sql.gz    jeder Dump, 24 Stunden aufbewahrt
  daily/keycloak-YYYYMMDD.sql.gz          der letzte Dump jedes Tages
  weekly/keycloak-YYYYWW.sql.gz           der letzte Dump jeder ISO-Woche
  monthly/keycloak-YYYYMM.sql.gz          der letzte Dump jedes Monats
  */keycloak-latest.sql.gz                Verweis auf die neueste Datei des Ordners
  pre-restore/keycloak-*.sql.gz           Sicherheits-Dumps des Restore-Skripts, nie gelöscht
```

Die Dateien in `daily/`, `weekly/` und `monthly/` sind harte Links auf einen
Dump in `last/`; ein Dump belegt seinen Platz also nur einmal. Alte Dateien
werden erst nach einem erfolgreichen Dump gelöscht. Ein Dump ist reines SQL,
mit gzip komprimiert; er enthält Realms, Benutzer, Sitzungen und Events der
Datenbank, aber nicht den Datenbankbenutzer `keycloak` und sein Passwort.

Ein Dump sofort, etwa vor einer Änderung in der Admin-Konsole:

```bash
docker compose -f docker-compose-production.yml exec backup sh -c 'umask 077 && /backup.sh'
```

Ohne `umask` sind die Dateien eines solchen Aufrufs für alle beschreibbar; die
geplanten Dumps nicht. `backups/` selbst ist nur seinem Eigentümer zugänglich.

Nicht in den Dumps und eine eigene Kopie wert:

| Was | Warum |
|---|---|
| `.env` | Admin- und Datenbankpasswort, Client-Secrets, die IDs des Backup-Benutzers |
| `realm/` | in Git; enthält weder Benutzer noch das, was in der Admin-Konsole geändert wurde |

Die Dumps bleiben auf diesem Host: Gegen den Verlust des Hosts `backups/` auf
ein anderes System kopieren. Das macht die Instanz nicht.

### Wiederherstellung

```bash
./adm_backup_restore.sh backups/daily/keycloak-YYYYMMDD.sql.gz
```

Das Skript prüft die Datei (`gzip -t`) und verlangt, `restore` einzutippen.
Dann stoppt es `keycloak` und `backup`, sichert die aktuelle Datenbank nach
`backups/pre-restore/`, löscht die Datenbank `keycloak` und legt sie neu an,
spielt den Dump ein und startet beide Dienste wieder. PostgreSQL läuft weiter.
Es braucht ein Terminal und die Container von `docker-compose-production.yml`.

- Scheitert das Einspielen, bleibt Keycloak gestoppt, und das Skript nennt den
  Sicherheits-Dump; diesen mit demselben Skript zurückspielen.
- Datenbankbenutzer und Passwort stehen nicht im Dump: Die Wiederherstellung
  arbeitet mit dem Passwort der aktuellen `.env`.
- Keycloak nimmt die Client-Secrets aus der wiederhergestellten Datenbank. In
  einer neuen Instanz brauchen die Dienste weiter die Secrets der alten (deren
  `.env` oder die Admin-Konsole).
- Benutzer, Sitzungen und die Änderungen aus der Admin-Konsole sind die des
  Dumps.

```{note}
Getestet mit lokal gebauten Images: PostgreSQL 18.6 mit dem Entrypoint des
offiziellen Images, das Backup-Image aus seinem Dockerfile, die Distribution
von Keycloak 26.8.0. Nicht getestet: die veröffentlichten Images selbst, die
Zeitzone im veröffentlichten Backup-Image und Docker unter macOS.
```

## Aktualisieren

Template-Updates kommen mit `cruft update`; `.env` steht auf der Skip-Liste.
Nach jedem `cruft update` einmal `python3 realm/build_realm.py` ausführen,
damit lokale Änderungen an `values.toml` und die Fassung des Templates
übereinstimmen. Gemeinsame Werte (Hosts, Client-IDs, Rollennamen) besser in
`.cookiecutter_all.yaml` ändern und mit
`cruft update --variables-to-update '{...}'` übernehmen; für einen laufenden
Realm braucht es zusätzlich die Admin-Konsole.

Die Datenbank behält das Passwort, mit dem sie angelegt wurde: Wer
`IFDD_KEYCLOAK_DB_PASSWORD` nur in `.env` ändert, sperrt Keycloak aus.

```{note}
Nicht getestet: ein Major-Upgrade von PostgreSQL mit Daten im Volume und ein
Upgrade von Keycloak mit bestehender Datenbank.
```
