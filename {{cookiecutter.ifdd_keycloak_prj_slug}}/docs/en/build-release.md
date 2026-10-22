(ifdd-keycloak-build-release)=
# Build and release

## Images

| Container | Image |
|---|---|
| `keycloak` | `{{ cookiecutter.ifdd_keycloak_image }}` |
| `postgres` | `{{ cookiecutter.ifdd_keycloak_postgres_image }}` |
| `backup` | `{{ cookiecutter.ifdd_keycloak_backup_image }}` |

The instance builds no image of its own. Keycloak runs with `start`, not
`start --optimized`: it builds itself on every start, which makes the start
slower but needs no custom image.

## The realm file

The realm file is the build product of this instance:

```bash
python3 realm/build_realm.py          # rebuild after editing values.toml or ifdd_realm/
python3 realm/build_realm.py --check  # fails if the committed files are out of date
```

It writes `realm/import/{{ cookiecutter.ifdd_keycloak_realm }}-realm.json`
and `realm/OVERVIEW.md`. The script needs Python 3.11 or later and only the
standard library. Commit `values.toml`, the modules in `realm/ifdd_realm/`
and the generated files together. What the script models is described in
{ref}`ifdd-keycloak-realm`.

## Versions

| Value | Here | Source |
|---|---|---|
| Keycloak | `{{ cookiecutter.ifdd_keycloak_image }}` | template variable `ifdd_keycloak_image` |
| PostgreSQL | `{{ cookiecutter.ifdd_keycloak_postgres_image }}` | template variable `ifdd_keycloak_postgres_image` |
| backup service | `{{ cookiecutter.ifdd_keycloak_backup_image }}` | template variable `ifdd_keycloak_backup_image`; same major version as PostgreSQL, because `pg_dump` must not be older than the server (the template refuses another one) |

The tag of the Keycloak image selects the file of Keycloak's built-in client
scopes (`realm/ifdd_realm/builtin/keycloak-<tag>.json`); the script refuses a
version without such a file. A new Keycloak version therefore comes with a
new template version, not by editing the tag alone. The template has been
tested with Keycloak 26.8.0; the PostgreSQL tests used version 16.

## CI of the instance

`.github/workflows/ci.yml` runs on every push and pull request:

- **template drift**: `cruft check`, and `cruft diff` if it reports drift;
  informational;
- **realm file**: `python3 realm/build_realm.py --check`, so a change of
  `values.toml` or `realm/ifdd_realm/` without the rebuilt files fails;
- **compose files**: `docker compose config` for both, with dummy values
  instead of the secrets and an empty `backups/`.

## Release

There is no release workflow, because no image is built. A new state of the
realm file reaches a running Keycloak only through a new realm
({ref}`ifdd-keycloak-realm`).

```{note}
Not tested: the container images themselves; the template was tested with
the Keycloak 26.8.0 distribution.
```
