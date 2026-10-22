(ifdd-keycloak-build-release)=
# Bauen und Freigeben

## Images

| Container | Image |
|---|---|
| `keycloak` | `{{ cookiecutter.ifdd_keycloak_image }}` |
| `postgres` | `{{ cookiecutter.ifdd_keycloak_postgres_image }}` |
| `backup` | `{{ cookiecutter.ifdd_keycloak_backup_image }}` |

Die Instanz baut kein eigenes Image. Keycloak läuft mit `start`, nicht mit
`start --optimized`: Es baut sich bei jedem Start selbst, was den Start
verlangsamt, aber kein eigenes Image braucht.

## Die Realm-Datei

Die Realm-Datei ist das Build-Ergebnis dieser Instanz:

```bash
python3 realm/build_realm.py          # nach Änderungen an values.toml oder ifdd_realm/ neu erzeugen
python3 realm/build_realm.py --check  # scheitert, wenn die eingecheckten Dateien veraltet sind
```

Es schreibt `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json`
und `realm/OVERVIEW.md`. Das Skript braucht Python 3.11 oder neuer und nur die
Standardbibliothek. `values.toml`, die Module in `realm/ifdd_realm/` und die
erzeugten Dateien gemeinsam committen. Was das Skript modelliert, steht in
{ref}`ifdd-keycloak-realm`.

## Versionen

| Wert | Hier | Quelle |
|---|---|---|
| Keycloak | `{{ cookiecutter.ifdd_keycloak_image }}` | Template-Variable `ifdd_keycloak_image` |
| PostgreSQL | `{{ cookiecutter.ifdd_keycloak_postgres_image }}` | Template-Variable `ifdd_keycloak_postgres_image` |
| Backup-Dienst | `{{ cookiecutter.ifdd_keycloak_backup_image }}` | Template-Variable `ifdd_keycloak_backup_image`; gleiche Hauptversion wie PostgreSQL, weil `pg_dump` nicht älter als der Server sein darf (das Template weist eine andere ab) |

Der Tag des Keycloak-Images wählt die Datei mit den eingebauten Client Scopes
von Keycloak (`realm/ifdd_realm/builtin/keycloak-<tag>.json`); eine Version
ohne solche Datei weist das Skript ab. Eine neue Keycloak-Version kommt daher
mit einer neuen Template-Version, nicht durch Ändern des Tags allein. Das
Template ist mit Keycloak 26.8.0 getestet; die PostgreSQL-Tests liefen mit
Version 16.

## CI der Instanz

`.github/workflows/ci.yml` läuft bei jedem Push und Pull Request:

- **template drift**: `cruft check` und, wenn es Abweichungen meldet,
  `cruft diff`; nur informativ;
- **realm file**: `python3 realm/build_realm.py --check`, damit eine Änderung
  an `values.toml` oder `realm/ifdd_realm/` ohne neu erzeugte Dateien
  scheitert;
- **compose files**: `docker compose config` für beide, mit Platzhaltern
  statt der Secrets und einem leeren `backups/`.

## Freigabe

Es gibt keinen Release-Workflow, weil kein Image gebaut wird. Ein neuer Stand
der Realm-Datei erreicht ein laufendes Keycloak nur über einen neuen Realm
({ref}`ifdd-keycloak-realm`).

```{note}
Nicht getestet: die Container-Images selbst; das Template wurde mit der
Distribution von Keycloak 26.8.0 getestet.
```
