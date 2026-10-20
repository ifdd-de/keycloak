#!/usr/bin/env python3
"""Write Keycloak realm import files and their overviews from values files.

    python3 realm/build_realm.py                     # realm/values.toml
    python3 realm/build_realm.py --check             # fail if not up to date
    python3 realm/build_realm.py --values realm/values_aa.toml realm/values_dd.toml

Each values file gives import/<realm>-realm.json, named after [realm] name.
realm/values.toml writes OVERVIEW.md, every other values file
OVERVIEW-<realm>.md. Existing files of other realms are never removed.

Keycloak reads realm/import/ at every start and imports each file whose realm
does not exist yet (--import-realm); see the README. The files are generated:
change the values files or ifdd_realm/, not them.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# No __pycache__ next to the model: the post-generation hook runs this script
# in every rendering of cruft update, and byte code (with time stamps) would
# show up there as a change of the instance.
sys.dont_write_bytecode = True

from ifdd_realm import builtin, overview, realm, validate, values

DEFAULT_VALUES = HERE / "values.toml"


def shown(path: Path) -> str:
    """The path as the instance sees it (realm/...), for messages and the overview."""
    try:
        return str(path.resolve().relative_to(HERE.parent))
    except ValueError:
        return str(path)


def render(values_file: Path) -> tuple[str, str, str]:
    """Return (realm name, content of the import file, overview) for one values file."""
    v = values.load(values_file)
    data = realm.build(v)
    errors = validate.check(data)
    if errors:
        sys.exit(f"{shown(values_file)}: realm is inconsistent:\n  - " + "\n  - ".join(errors))
    return (data["realm"], json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            overview.render(data, builtin.load(v.keycloak_version), shown(values_file)))


def overview_path(values_file: Path, name: str, explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    if values_file.resolve() == DEFAULT_VALUES:
        return HERE / "OVERVIEW.md"
    return HERE / f"OVERVIEW-{name}.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--values", type=Path, nargs="+", default=[DEFAULT_VALUES],
                        help="values files (default: realm/values.toml)")
    parser.add_argument("--out", type=Path, default=HERE / "import")
    parser.add_argument("--overview", type=Path,
                        help="overview file; only with a single values file")
    parser.add_argument("--check", action="store_true", help="only compare, write nothing")
    args = parser.parse_args()
    if args.overview is not None and len(args.values) != 1:
        parser.error("--overview needs exactly one values file")

    # (import file, content, overview file, overview) per values file
    planned: list[tuple[Path, str, Path, str]] = []
    names: dict[str, Path] = {}
    for values_file in args.values:
        name, content, summary = render(values_file)
        if name in names:
            sys.exit(f"realm {name!r} is named in {shown(names[name])} and {shown(values_file)}")
        names[name] = values_file
        # Keycloak expects the file name <realm name>-realm.json.
        planned.append((args.out / f"{name}-realm.json", content,
                        overview_path(values_file, name, args.overview), summary))

    # Keycloak imports every *.json in the directory whose realm does not exist
    # yet. Other files are left alone on purpose; say that they are there.
    ours = {target.name for target, _, _, _ in planned}
    others = sorted(p.name for p in args.out.glob("*.json") if p.name not in ours)
    note = (f"note: {shown(args.out)} also holds {', '.join(others)}; Keycloak imports "
            "each of them at the next start if its realm does not exist yet") if others else ""

    if args.check:
        stale = [shown(path) for target, content, ov, summary in planned
                 for path, text in ((target, content), (ov, summary))
                 if not path.is_file() or path.read_text() != text]
        if note:
            print(note, file=sys.stderr)
        if stale:
            print("not up to date: " + ", ".join(stale) +
                  ". Run python3 realm/build_realm.py and commit the result.", file=sys.stderr)
            return 1
        print("up to date: " + ", ".join(shown(p) for t, _, o, _ in planned for p in (t, o)))
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for target, content, ov, summary in planned:
        target.write_text(content)
        ov.write_text(summary)
        print(f"wrote {shown(target)} and {shown(ov)}")
    if note:
        print(note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
