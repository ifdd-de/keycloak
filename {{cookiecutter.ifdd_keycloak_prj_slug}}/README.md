# {{ cookiecutter.ifdd_keycloak_prj_name }}

Keycloak ({{ cookiecutter.ifdd_keycloak_image }}) with PostgreSQL, behind the
shared proxy on the network `{{ cookiecutter.ifdd_proxy_network }}`. Realm
`{{ cookiecutter.ifdd_keycloak_realm }}`, issuer
`{{ cookiecutter.ifdd_oidc_realm }}`.

Generated from `ifdd-de/keycloak` with cruft.

## Quick start

```bash
docker compose -f docker-compose-production.yml up -d
docker compose -f docker-compose-production.yml logs -f keycloak   # until "Realm '{{ cookiecutter.ifdd_keycloak_realm }}' imported"
```

The proxy must run first. Sign in to
`https://{{ cookiecutter.ifdd_keycloak_host }}/admin/` with
`IFDD_KEYCLOAK_ADMIN_USER` and `IFDD_KEYCLOAK_ADMIN_PASSWORD` from `.env`
(a temporary admin: create a permanent one, then delete it), and hand each
service its client secret from `.env`. The realm file is imported on the
first start only; `realm/OVERVIEW.md` shows it as tables.

The service `backup` dumps the database into `backups/` on the schedule
`{{ cookiecutter.ifdd_keycloak_backup_schedule }}`;
`./adm_backup_restore.sh <dump>` restores one.

## Documentation

Setup, build and release, operations, security, troubleshooting, reference
and the realm of this instance:

- English: [docs/en/index.md](docs/en/index.md)
- Deutsch: [docs/de/index.md](docs/de/index.md)

The pages are Sphinx sources in MyST Markdown, meant to be copied into a
documentation project that covers all services; GitHub shows them as plain
Markdown.

## AI assistance

Some parts of the template `ifdd-de/keycloak` this instance was generated
from, in particular the tests, the test data and the documentation, were
developed or improved with the help of large language models (LLMs). All
changes were reviewed and released by the maintainer.

## License

BSD-3-Clause, see `LICENSE`.
