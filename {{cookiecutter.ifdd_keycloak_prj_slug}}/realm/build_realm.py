#!/usr/bin/env python3
"""Write the Keycloak realm import file and its overview from values.toml.

    python3 realm/build_realm.py            # write import/<realm>-realm.json and OVERVIEW.md
    python3 realm/build_realm.py --check    # fail if either is not up to date

Keycloak reads realm/import/ on its first start only (--import-realm); see
the README. The file is generated: change values.toml or ifdd_realm/, not it.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ifdd_realm import builtin, overview, realm, validate, values


def render(values_file: Path) -> tuple[str, str, str]:
    """Return (file name, content) of the import file and the overview."""
    v = values.load(values_file)
    data = realm.build(v)
    errors = validate.check(data)
    if errors:
        sys.exit("realm is inconsistent:\n  - " + "\n  - ".join(errors))
    # Keycloak requires the file name <realm name>-realm.json.
    return (f"{data['realm']}-realm.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            overview.render(data, builtin.load(v.keycloak_version)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--values", type=Path, default=HERE / "values.toml")
    parser.add_argument("--out", type=Path, default=HERE / "import")
    parser.add_argument("--overview", type=Path, default=HERE / "OVERVIEW.md")
    parser.add_argument("--check", action="store_true", help="only compare, write nothing")
    args = parser.parse_args()

    name, content, summary = render(args.values)
    target = args.out / name
    # Keycloak imports every *.json in the directory: a file of a former
    # realm name would create a second realm.
    others = sorted(p.name for p in args.out.glob("*.json") if p.name != name)

    if args.check:
        stale = [str(path) for path, text in ((target, content), (args.overview, summary))
                 if not path.is_file() or path.read_text() != text]
        stale += [str(args.out / other) + " (other realm)" for other in others]
        if stale:
            print("not up to date: " + ", ".join(stale) +
                  ". Run python3 realm/build_realm.py and commit the result.", file=sys.stderr)
            return 1
        print(f"{target} and {args.overview}: up to date")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    for other in others:
        (args.out / other).unlink()
        print(f"removed {args.out / other} (not the file of realm {name.removesuffix('-realm.json')})")
    target.write_text(content)
    args.overview.write_text(summary)
    print(f"wrote {target} and {args.overview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
