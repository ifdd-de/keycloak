(ifdd-keycloak-realm)=
# Realm
{%- set gate_hosts = cookiecutter.ifdd_keycloak_proxy_gate_hosts.split(",") | map("trim") | reject("equalto", "") | list %}

Der Realm `{{ cookiecutter.ifdd_keycloak_realm }}` wird erzeugt, nicht
zusammengeklickt: cruft schreibt `realm/values.toml` aus den
Template-Variablen, und `realm/build_realm.py` macht daraus die Importdatei
und `realm/OVERVIEW.md`. Keycloak importiert die Datei nur beim ersten Start.

`realm/OVERVIEW.md` zeigt den erzeugten Realm als Tabellen: Einstellungen
(Token-Lebensdauern, Sitzungen, Passwort-Policy, Events), Rollen, Gruppen,
Client Scopes, Clients und Service-Accounts. Dort mit dem Lesen beginnen; die
Datei entsteht aus dem fertigen Realm und kann der Importdatei daher nicht
widersprechen.

Die Übersicht ist zugleich eine Seite für Sphinx (MyST-Markdown, nur
englisch, Label `ifdd-keycloak-realm-overview`). Für die Gesamtdoku
`realm/OVERVIEW.md` in beide Sprachprojekte kopieren, etwa als
`services/keycloak/realm-overview.md`, und in einen Toctree aufnehmen. Nach
jedem Neuerzeugen erneut kopieren.

## Das Modell

Rollen, Gruppen, Client Scopes, Clients und Service-Accounts haben je ein
eigenes Modul in `realm/ifdd_realm/`; `validate.py` prüft das Ergebnis, bevor
es geschrieben wird. `values.toml`, die Module und die erzeugten Dateien
gemeinsam committen. Persönliche Benutzer und Passwörter gehören nicht
hinein.

```bash
python3 realm/build_realm.py          # nach Änderungen an values.toml oder ifdd_realm/ neu erzeugen
python3 realm/build_realm.py --check  # was die CI ausführt
```

## Login-Theme

Die Anmeldeseiten nutzen das Theme `ifdd` aus `themes/ifdd/`: das Theme
`keycloak.v2` von Keycloak mit schlichtem Hintergrund statt der
Keycloak-Grafik, einer neutralen Linie über der Karte und dem Anzeigenamen
des Realms als ruhiger Überschrift. Es ändert nur Stile (`theme.properties`,
`resources/css/ifdd.css`); Templates und Texte kommen aus `keycloak.v2`,
sodass ein Keycloak-Upgrade die Seiten nicht bricht. Der dunkle Modus folgt
dem Browser.

Der Realm wählt das Theme mit `loginTheme`. Überschrift und Browser-Titel
zeigen `display_name` aus der Werte-Datei, hier
`{{ cookiecutter.ifdd_keycloak_prj_name }}`. Das Verzeichnis gehört dem
Template und kommt mit `cruft update`. Keycloak puffert Themes außerhalb von
`start-dev`: nach einer Änderung Keycloak neu starten.

## Weitere Realms

`realm/values.toml` beschreibt den Realm dieser Instanz. Weitere Realms für
einen einmaligen Import beschreiben Kopien davon, etwa
`realm/values_aa.toml`; darin mindestens `name` und `display_name` unter
`[realm]` ändern:

```bash
python3 realm/build_realm.py --values realm/values_aa.toml realm/values_dd.toml
```

Jede Werte-Datei ergibt `realm/import/<name>-realm.json`, benannt nach
`[realm] name`, und `realm/OVERVIEW-<name>.md`; `realm/values.toml` schreibt
weiterhin `realm/OVERVIEW.md`. Zwei Werte-Dateien mit demselben Realm-Namen
brechen das Skript ab. Das Skript entfernt nie Dateien anderer Realms, es
nennt sie nur. Beim nächsten Start importiert Keycloak jede Datei in
`realm/import/`, deren Realm noch nicht existiert, und überspringt die
übrigen.

`--check` vergleicht nur die angegebenen Werte-Dateien (ohne Angabe
`realm/values.toml`), sodass die CI auch mit weiteren Realm-Dateien in
`realm/import/` besteht. Eine Datei, die nach dem Umbenennen eines Realms
übrig bleibt, meldet sie ebenfalls nicht; sie von Hand entfernen.

Alle Realm-Dateien verweisen auf dieselben Client-Secrets in `.env`; weitere
Realms bekommen also dieselben Secrets wie
`{{ cookiecutter.ifdd_keycloak_realm }}`. Nach dem Import in der
Admin-Konsole neue erzeugen (Client, „Credentials“) und den Diensten geben,
die sie nutzen.

## Rollen

Die Knotenrollen gibt es als Realm-Rollen und als Client-Rollen des
Backend-Clients `{{ cookiecutter.ifdd_oidc_backend_client_id }}`; Backend und
UI prüfen die Client-Rollen (`resource_access`).

| Rolle | Bedeutung |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_role_public }}` | angemeldet, keine weiteren Rechte; die Standardrolle gewährt nur diese |
| `{{ cookiecutter.ifdd_be_role_nodes_read }}` | Knoten lesen; zugleich der Client Scope, der die Audience `{{ cookiecutter.ifdd_oidc_jwks_audience }}` hinzufügt |
| `{{ cookiecutter.ifdd_keycloak_role_nodes_write }}` | Knoten schreiben |
| `{{ cookiecutter.ifdd_keycloak_role_nodes_priv }}` | privilegierter Lesezugriff |
| `{{ cookiecutter.ifdd_context_root }}` | Kontextmuster für jeden Domain-Kontext unter der Wurzel; nur Client-Rolle |
| `{{ cookiecutter.ifdd_ts_role_admin }}`, `{{ cookiecutter.ifdd_ts_role_editor }}`, `{{ cookiecutter.ifdd_ts_role_viewer }}` | Grafana Admin, Editor, Viewer (Realm-Rollen) |

## Gruppen

| Gruppe | Gewährt |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_group_nodes_readers }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}` |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_writers }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}`, `{{ cookiecutter.ifdd_keycloak_role_nodes_write }}` |
| `{{ cookiecutter.ifdd_keycloak_group_nodes_privileged }}` | `{{ cookiecutter.ifdd_be_role_nodes_read }}`, `{{ cookiecutter.ifdd_keycloak_role_nodes_priv }}` |
| `{{ cookiecutter.ifdd_keycloak_wf_admin_group }}` | nur Mitgliedschaft (Claim `groups`), für das Login-Gate von wf |
| `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}` | das Kontextmuster `{{ cookiecutter.ifdd_context_root }}` |

## Clients

| Client | Art | Flows | Redirect-URIs |
|---|---|---|---|
| `{{ cookiecutter.ifdd_oidc_backend_client_id }}` | public | Authorization Code mit PKCE S256 | `{{ cookiecutter.ifdd_ui_url }}/authentication/callback`, `{{ cookiecutter.ifdd_ui_url }}/authentication/silent-callback`, `{{ cookiecutter.ifdd_be_url }}/docs/oauth2-redirect` |
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | vertraulich | Client Credentials | keine |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | vertraulich | Client Credentials | keine |
| `{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` | vertraulich | Client Credentials | keine |
| `{{ cookiecutter.ifdd_ts_oidc_client_id }}` | vertraulich | Authorization Code mit PKCE S256, Client Credentials | `https://{{ cookiecutter.ifdd_ts_host }}/login/generic_oauth` |
| `{{ cookiecutter.ifdd_proxy_oidc_client_id }}` | vertraulich | Authorization Code mit PKCE S256 | {% for host in gate_hosts %}`https://{{ host }}/oauth2/callback`{{ ", " if not loop.last else "" }}{% endfor %} |
| `{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` | vertraulich | keine (trägt die Rollen von ts-api) | keine |
| `{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` | vertraulich | Client Credentials | keine |

Die Redirect-URIs des Login-Gates kommen aus
`ifdd_keycloak_proxy_gate_hosts`: eine je Host hinter oauth2-proxy. Welche
Rollen in die Tokens jedes Clients gelangen und was die Service-Accounts
halten, steht in `realm/OVERVIEW.md`.

## Kontextmuster

Das Backend gibt Domain-Kontexte (Namen mit Punkten wie
`sub1.dom1.{{ cookiecutter.ifdd_context_root }}`) nur an Clients mit
passendem Kontextmuster: einer Client-Rolle des Backend-Clients, deren Name
einen Punkt enthält. Basis- und Aspekt-Kontexte brauchen kein Muster.

Der Realm bringt ein Muster mit, `{{ cookiecutter.ifdd_context_root }}`: nur
als Client-Rolle, dazu die Gruppe `ifdd_ctx_{{ cookiecutter.ifdd_context_root }}`,
die es gewährt, und die Service-Accounts von
`{{ cookiecutter.ifdd_keycloak_api_client_id }}`,
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` und
`{{ cookiecutter.ifdd_ts_oidc_client_id }}` halten es. Menschen bekommen
Muster nur über Gruppen, zusammen mit einer Knotengruppe. Weitere Muster, je
mit ihrer Gruppe `ifdd_ctx_<pattern>`, legt `keycloak_add_context_role.py`
des Meta-Repositorys in einem laufenden Realm an.

## Zeitreihen-API

ifdd-ts-api prüft die Client-Rollen ihres eigenen Clients
`{{ cookiecutter.ifdd_ts_api_oidc_client_id }}`, der zugleich die Audience
ihrer Tokens ist. Mit diesem Client meldet sich niemand an: Kein Flow ist
eingeschaltet, und Keycloak setzt ihn in das `aud` jedes Tokens, das eine
seiner Rollen trägt. Seine Rollen:

| Rolle | Bedeutung |
|---|---|
| `{{ cookiecutter.ifdd_ts_api_role_read }}` | Samples lesen |
| `{{ cookiecutter.ifdd_ts_api_role_write }}` | Samples schreiben |
| `{{ cookiecutter.ifdd_context_root }}` | Store-Muster der Wurzel: jeder Store |

Ein weiteres Store-Muster ist eine weitere Client-Rolle mit Punkt, z. B.
`temperature.ops.example.ifdd.de` nur für diesen Store. Die Rollen bekommen
nur Service-Accounts, nie Gruppen (ts-api nimmt nur Client Credentials an):

| Service-Account | Rollen von `{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` |
|---|---|
| `{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_write }}`, `{{ cookiecutter.ifdd_context_root }}` |
| `{{ cookiecutter.ifdd_keycloak_ct_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_write }}`, `{{ cookiecutter.ifdd_context_root }}` |
| `{{ cookiecutter.ifdd_keycloak_api_client_id }}` | `{{ cookiecutter.ifdd_ts_api_role_read }}`, `{{ cookiecutter.ifdd_context_root }}` |

`{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}` und
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` haben keinen Full Scope; die
Rollen stehen auch in ihren Scope-Mappings. Grafana
(`{{ cookiecutter.ifdd_ts_oidc_client_id }}`) bekommt keine: Es liest
VictoriaMetrics direkt.

## Änderungen an einem bestehenden Realm

Ein Realm, den ein älteres Template importiert hat, bekommt spätere
Änderungen nicht über `cruft update`. Diese Änderungen brauchen die
Admin-Konsole.

### Die Kontextwurzel ergänzen

Ein Realm, der vor den Kontextmustern importiert wurde, hat weder die Rolle
`{{ cookiecutter.ifdd_context_root }}` noch ihre Gruppe, und den
Service-Accounts fehlt sie: Sie sehen dann keinen Domain-Kontext. Beides mit
`keycloak_add_context_role.py {{ cookiecutter.ifdd_context_root }}` des
Meta-Repositorys anlegen, dann in der Admin-Konsole die Rolle des Clients
`{{ cookiecutter.ifdd_oidc_backend_client_id }}` den Service-Accounts von
`{{ cookiecutter.ifdd_keycloak_api_client_id }}`,
`{{ cookiecutter.ifdd_keycloak_ct_client_id }}` und
`{{ cookiecutter.ifdd_ts_oidc_client_id }}` zuweisen und sie den Client Scopes
(„Dedicated scope“, „Scope“) von `{{ cookiecutter.ifdd_keycloak_ct_client_id }}`
und `{{ cookiecutter.ifdd_ts_oidc_client_id }}` hinzufügen.

### Login-Theme und Titel

Ein Realm, der vor dem Theme importiert wurde, behält das Standard-Theme von
Keycloak und hat keinen Anzeigenamen. In der Admin-Konsole „Realm settings“
öffnen: unter „Themes“ `ifdd` als Login-Theme wählen, unter „General“
„Display name“ und „HTML display name“ auf
`{{ cookiecutter.ifdd_keycloak_prj_name }}` setzen. Das Theme muss
eingehängt sein: Compose-Dateien dieser Template-Fassung, dann Keycloak neu
starten.

```{note}
Nicht getestet: diese Schritte in der Admin-Konsole. Das Theme selbst wurde
mit einem neu importierten Realm getestet.
```

### Den Backend-Redirect einschränken

Ein Realm, der vor dem 2026-10-13 importiert wurde, lässt den Client
`{{ cookiecutter.ifdd_oidc_backend_client_id }}` auf jeden Pfad unter
`{{ cookiecutter.ifdd_be_url }}` umleiten (`{{ cookiecutter.ifdd_be_url }}/*`).
Nur die Swagger UI des Backends nutzt das, und nur
`{{ cookiecutter.ifdd_be_url }}/docs/oauth2-redirect`. In der Admin-Konsole
Clients, `{{ cookiecutter.ifdd_oidc_backend_client_id }}`, Settings öffnen und
den Eintrag unter „Valid redirect URIs“ durch genau diese URI ersetzen. Muster
lassen einen Angreifer wählen, wohin innerhalb des Hosts der
Authorization Code geht (RFC 9700, Abschnitt 2.1).

```{note}
Nicht getestet: diese Schritte in der Admin-Konsole an einem bestehenden
Realm. Der exakte Redirect selbst wurde mit einem neu importierten Realm
getestet.
```

### Den User-Admin-Client ergänzen

Ein Realm, der importiert wurde, bevor es den Client
`{{ cookiecutter.ifdd_keycloak_useradmin_client_id }}` gab, bekommt ihn nicht
über `cruft update`, aber die Compose-Dateien verlangen ab dann
`IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET`. Den Client mit `kcadm.sh` im
laufenden Container anlegen, als Admin des Master-Realms:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} CLIENT={{ cookiecutter.ifdd_keycloak_useradmin_client_id }}
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
CID=$(kcadm create clients -r "$REALM" -i -s clientId="$CLIENT" -s name="IFDD User Admin" \
  -s publicClient=false -s serviceAccountsEnabled=true -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false -s fullScopeAllowed=false)
kcadm add-roles -r "$REALM" --uusername "service-account-$CLIENT" \
  --cclientid realm-management --rolename manage-users
RMID=$(kcadm get clients -r "$REALM" -q clientId=realm-management --fields id --format csv --noquotes)
kcadm create "clients/$CID/scope-mappings/clients/$RMID" -r "$REALM" \
  -b "[$(kcadm get "clients/$RMID/roles/manage-users" -r "$REALM")]"
kcadm get "clients/$CID/client-secret" -r "$REALM" --fields value --format csv --noquotes
rm /tmp/kcadm.config
exit
```

Das ausgegebene Secret in `.env` eintragen:

```text
IFDD_KEYCLOAK_USERADMIN_CLIENT_ID={{ cookiecutter.ifdd_keycloak_useradmin_client_id }}
IFDD_KEYCLOAK_USERADMIN_CLIENT_SECRET=<printed secret>
```

```{note}
Getestet mit `kcadm.sh` aus der Distribution von Keycloak 26.8.0 gegen
`http://localhost:8080`; nicht getestet im Container und mit gesetztem
`KC_HOSTNAME`.
```

### Die Clients von ts-api ergänzen

Einem Realm, der importiert wurde, bevor es ts-api gab, fehlen die Clients
`{{ cookiecutter.ifdd_ts_api_oidc_client_id }}` und
`{{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}`, und die
Compose-Dateien verlangen ab dann `IFDD_KEYCLOAK_TSAPI_CLIENT_SECRET` und
`IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET`. Beide Clients mit `kcadm.sh` im
laufenden Container anlegen und die Rollen vergeben, als Admin des
Master-Realms:

```bash
docker compose -f docker-compose-production.yml exec keycloak bash
```

```bash
# inside the container
REALM={{ cookiecutter.ifdd_keycloak_realm }} API={{ cookiecutter.ifdd_ts_api_oidc_client_id }} INGEST={{ cookiecutter.ifdd_keycloak_ts_ingest_client_id }}
RO={{ cookiecutter.ifdd_ts_api_role_read }} RW={{ cookiecutter.ifdd_ts_api_role_write }} ROOT={{ cookiecutter.ifdd_context_root }}
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
kcadm config credentials --server http://localhost:8080 --realm master --user <admin>  # asks for the password
id_of() { kcadm get clients -r "$REALM" -q clientId="$1" --fields id --format csv --noquotes; }
AID=$(kcadm create clients -r "$REALM" -i -s clientId="$API" -s name="IFDD Time Series API" \
  -s publicClient=false -s serviceAccountsEnabled=false -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false)
for role in "$RO" "$RW" "$ROOT"; do kcadm create "clients/$AID/roles" -r "$REALM" -s name="$role"; done
IID=$(kcadm create clients -r "$REALM" -i -s clientId="$INGEST" -s name="IFDD Time Series Ingest" \
  -s publicClient=false -s serviceAccountsEnabled=true -s standardFlowEnabled=false \
  -s directAccessGrantsEnabled=false -s fullScopeAllowed=false)
grant() {  # client, role, role
  kcadm add-roles -r "$REALM" --uusername "service-account-$1" --cclientid "$API" \
    --rolename "$2" --rolename "$3"
  for role in "$2" "$3"; do   # scope mapping, for clients without full scope
    kcadm create "clients/$(id_of "$1")/scope-mappings/clients/$AID" -r "$REALM" \
      -b "[$(kcadm get "clients/$AID/roles/$role" -r "$REALM")]"
  done
}
grant "$INGEST" "$RW" "$ROOT"
grant {{ cookiecutter.ifdd_keycloak_ct_client_id }} "$RW" "$ROOT"
grant {{ cookiecutter.ifdd_keycloak_api_client_id }} "$RO" "$ROOT"
kcadm get "clients/$AID/client-secret" -r "$REALM" --fields value --format csv --noquotes
kcadm get "clients/$IID/client-secret" -r "$REALM" --fields value --format csv --noquotes
rm /tmp/kcadm.config
exit
```

Die beiden ausgegebenen Secrets in dieser Reihenfolge in `.env` eintragen:

```text
IFDD_KEYCLOAK_TSAPI_CLIENT_SECRET=<first secret>
IFDD_KEYCLOAK_TSINGEST_CLIENT_SECRET=<second secret>
```

Das Scope-Mapping von `{{ cookiecutter.ifdd_keycloak_api_client_id }}` ist
nicht nötig (der Client hat Full Scope) und schadet nicht.

```{note}
Getestet mit `kcadm.sh` aus der Distribution von Keycloak 26.8.0 gegen
`http://localhost:8080` und einen aus dem vorigen Template importierten
Realm; nicht getestet im Container.
```
