"""Create .env with generated secrets, the backup directory, then the realm import file.

1. .env from dotenv.dist, placeholders replaced by random values and by the
   ids of the user who generates the instance.
2. backups/ for the database dumps of the backup service, mode 0700.
3. realm/import/<realm>-realm.json from realm/values.toml (realm/build_realm.py).


A placeholder is the whole value of a variable (KEY=<<generate:...>>) and
states the quality of the value it stands for:

    <<generate:chars:LENGTH:CLASSES>>   LENGTH characters drawn from CLASSES,
                                        at least one of each class:
                                        a = lowercase, A = uppercase, 0 = digit
    <<generate:base64:BYTES>>           base64 of BYTES random bytes
    <<host:uid>>, <<host:gid>>          user and group id of the user running
                                        this hook; the backup container runs
                                        with them, so the dumps belong to that
                                        user. Refused for root.

An existing .env is never touched, so cruft update and a second run keep the
secrets the database and the clients were created with. Standard library
only; randomness from the secrets module.
"""
import base64
import os
import re
import secrets
import string
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE, TARGET = Path("dotenv.dist"), Path(".env")
MIN_LENGTH = 20
CLASSES = {"a": string.ascii_lowercase, "A": string.ascii_uppercase, "0": string.digits}
PLACEHOLDER = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*=)<<generate:([^>]*)>>[ \t]*$", re.MULTILINE)
HOST_ID = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*=)<<host:(uid|gid)>>[ \t]*$", re.MULTILINE)
BACKUPS = Path("backups")


def fail(message: str) -> None:
    print(f"post_gen_project: {message}", file=sys.stderr)
    sys.exit(1)


def chars(length: int, classes: str) -> str:
    if length < MIN_LENGTH:
        fail(f"length {length} is below the minimum of {MIN_LENGTH}")
    if not classes or any(c not in CLASSES for c in classes):
        fail(f"character classes {classes!r}: use a combination of 'a', 'A', '0'")
    alphabet = "".join(CLASSES[c] for c in dict.fromkeys(classes))
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if all(any(ch in CLASSES[c] for ch in value) for c in classes):
            return value


def generate(spec: str) -> str:
    parts = spec.split(":")
    try:
        if parts[0] == "chars" and len(parts) == 3:
            return chars(int(parts[1]), parts[2])
        if parts[0] == "base64" and len(parts) == 2:
            size = int(parts[1])
            if size < 16:
                fail(f"base64 of {size} bytes is too short")
            return base64.b64encode(secrets.token_bytes(size)).decode()
    except ValueError:
        pass
    fail(f"unknown placeholder <<generate:{spec}>>")
    return ""  # not reached


def host_id(kind: str) -> str:
    if os.getuid() == 0:
        fail("refusing to run as root: the backup container would write the dumps as root; "
             "generate the instance as the user who will own backups/")
    return str(os.getuid() if kind == "uid" else os.getgid())


def write_env() -> None:
    if not SOURCE.is_file():
        fail(f"{SOURCE} is missing")
    if TARGET.exists():
        print(f"post_gen_project: {TARGET} exists, left unchanged")
        return
    text = PLACEHOLDER.sub(lambda m: m.group(1) + generate(m.group(2)), SOURCE.read_text())
    text = HOST_ID.sub(lambda m: m.group(1) + host_id(m.group(2)), text)
    for line in text.splitlines():
        if ("<<generate" in line or "<<host" in line) and not line.lstrip().startswith("#"):
            fail(f"placeholder not replaced, check its form: {line.split('=')[0]}")
    fd, tmp = tempfile.mkstemp(dir=".", prefix=".env.")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, TARGET)
    print(f"post_gen_project: {TARGET} created with generated secrets")


def make_backup_dir() -> None:
    """The bind mount of the backup service; compose does not create it."""
    if not BACKUPS.exists():
        BACKUPS.mkdir()
        os.chmod(BACKUPS, 0o700)


def build_realm() -> None:
    result = subprocess.run([sys.executable, "realm/build_realm.py"], check=False)
    if result.returncode != 0:
        fail("realm/build_realm.py failed, see above")


if __name__ == "__main__":
    write_env()
    make_backup_dir()
    build_realm()
