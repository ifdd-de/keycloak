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

Mit `KC_METRICS_ENABLED` umfasst die Readiness die Datenbank; Keycloak wird
also unhealthy, solange die Datenbank fehlt. Docker startet einen
unhealthy-Container nicht von selbst neu; `docker compose ps` zeigt den
Zustand. Beide Container starten mit `restart: always` neu, wenn sie sich
beenden.

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

| Was | Wie |
|---|---|
| die Datenbank (Realm, Benutzer, Sitzungen, Events) | Volume `postgres-data`, zum Beispiel `docker compose -f docker-compose-production.yml exec postgres pg_dump -U keycloak keycloak > keycloak.sql` |
| `.env` | Admin- und Datenbankpasswort, Client-Secrets |

`realm/` liegt in Git; es enthält weder Benutzer noch das, was in der
Admin-Konsole geändert wurde. Den Datenbank-Dump vor dem Start von Keycloak in
eine leere Datenbank einspielen, mit dem Datenbankpasswort der `.env`, mit der
sie angelegt wurde.

```{note}
Nicht getestet: Sicherung und Wiederherstellung der Datenbank.
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
