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

## Documentation

Setup, build and release, operations, security, troubleshooting, reference
and the realm of this instance:

- English: [docs/en/index.md](docs/en/index.md)
- Deutsch: [docs/de/index.md](docs/de/index.md)

The pages are Sphinx sources in MyST Markdown, meant to be copied into a
documentation project that covers all services; GitHub shows them as plain
Markdown.

## Honesty notes

The realm of this template was tested against the Keycloak 26.8.0
distribution (start import, code flow with PKCE, client credentials, admin
API); the README of the template `ifdd-de/keycloak` lists the checks. Not
verified: the container images, PostgreSQL 18 (the tests used 16), backup
and restore, and upgrades of Keycloak or PostgreSQL with existing data.

## License

BSD-3-Clause, see `LICENSE`.
