"""Build the Keycloak realm import file of IFDD from realm/values.toml.

Each aspect of the realm has its own module; realm.py puts them together:

    values.py     the values from values.toml, typed
    builtin.py    Keycloak's built-in client scopes (data file per version)
    mappers.py    protocol mappers (audience, group membership)
    roles.py      realm roles, client roles, the default role
    groups.py     groups
    scopes.py     client scopes of IFDD
    clients.py    one function per client
    users.py      service accounts (no personal users, no passwords)
    realm.py      realm settings and assembly
    validate.py   consistency checks before anything is written
    model.py      the data classes and their Keycloak JSON form

Standard library only.
"""
