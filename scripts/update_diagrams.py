"""Deliver Archify diagrams and reject documentation that no longer matches source.

The checker needs only Python. Rendering additionally needs Node and the local
Archify skill (ARCHIFY_HOME or --archify-home). It does not invent semantics:
agents must review and edit the JSON before refreshing the evidence.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAGRAMS = Path("docs/diagrams")
MANIFEST = DIAGRAMS / "manifest.json"
SPECS = {
    "application": "architecture",
    "processing": "workflow",
    "maintenance": "architecture",
}
SOURCE_DIRS = ("pdf_lover", "packaging", "scripts", "tests", ".githooks")
SOURCE_FILES = ("main.py", "pyproject.toml", "requirements.txt", "AGENTS.md",
                "CONTRIBUTING.md", "docs/ARCHITECTURE.md", "docs/DIAGRAMS.md")
SOURCE_SUFFIXES = {".py", ".ps1", ".spec", ".iss"}


def digest(data):
    # Git can normalize line endings; evidence binds canonical UTF-8 text.
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def watched(path):
    p = Path(path)
    return path in SOURCE_FILES or (
        p.parts[0] in SOURCE_DIRS
        and "__pycache__" not in p.parts
        and ".verification" not in p.parts
        and (p.suffix in SOURCE_SUFFIXES or path == ".githooks/pre-commit")
    )


def snapshot(root=ROOT, staged=False):
    if staged:
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
        read = lambda p: subprocess.check_output(["git", "show", f":{p}"], cwd=root)
    else:
        paths = [p.relative_to(root).as_posix() for name in SOURCE_DIRS
                 if (root / name).exists() for p in (root / name).rglob("*") if p.is_file()]
        paths += [p for p in SOURCE_FILES if (root / p).is_file()]
        read = lambda p: (root / p).read_bytes()
    return {p: digest(read(p)) for p in sorted(set(paths)) if p and watched(p)}


def check(root=ROOT, staged=False):
    read = (lambda p: subprocess.check_output(["git", "show", f":{p}"], cwd=root)) if staged else (
        lambda p: (root / p).read_bytes())
    try:
        manifest = json.loads(read(MANIFEST.as_posix()))
        current = snapshot(root, staged)
        previous = manifest["source_files"]
        changed = sorted(p for p in current.keys() | previous.keys() if current.get(p) != previous.get(p))
        for item in manifest["diagrams"]:
            for field in ("specification", "artifact"):
                record = item[field]
                data = read(record["path"])
                if digest(data) != record["canonical_sha256"]:
                    changed.append(record["path"])
        if {item["name"] for item in manifest["diagrams"]} != set(SPECS):
            changed.append("diagram inventory")
        if changed:
            print("Archify diagrams are stale:", *changed, sep="\n  ", file=sys.stderr)
            print("Review JSON semantics, run python scripts/update_diagrams.py, then stage source, HTML and manifest together.", file=sys.stderr)
            return 1
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot verify Archify evidence: {error}", file=sys.stderr)
        return 1
    print("Archify diagrams match " + ("the Git index." if staged else "the current source."))
    return 0


def archify(command, skill, *args):
    result = subprocess.run(["node", str(skill / "bin/archify.mjs"), command, *map(str, args), "--json"],
                            cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def refresh(skill, visual=False):
    cli = skill / "bin/archify.mjs"
    if not cli.is_file():
        raise RuntimeError("Archify not found. Set ARCHIFY_HOME or pass --archify-home <skill directory>.")
    # Validate every candidate before replacing any last-good diagram.
    validations = {}
    for name, kind in SPECS.items():
        validations[name] = archify("validate", skill, kind, DIAGRAMS / f"{name}.{kind}.json", "--quality", "showcase")
        validation = validations[name]
        if len(validation.get("checks", [])) != 9 or not all(item["ok"] for item in validation["checks"]):
            raise RuntimeError(f"{name}: expected all nine showcase artifact checks.")
        if validation["composition"]["summary"] != {"errors": 0, "warnings": 0}:
            raise RuntimeError(f"{name}: composition diagnostics must be resolved.")
    records = []
    for name, kind in SPECS.items():
        spec = DIAGRAMS / f"{name}.{kind}.json"
        output = DIAGRAMS / f"{name}.html"
        receipt = archify("deliver", skill, kind, spec, output, "--quality", "showcase")
        # Preserve the canonical receipt without machine-specific absolute paths.
        receipt_path = ROOT / DIAGRAMS / f"{name}.delivery.json"
        clean = {key: receipt[key] for key in ("ok", "type", "specification", "artifact", "checks", "composition") if key in receipt}
        clean["checks"] = validations[name]["checks"]
        clean["composition"] = validations[name]["composition"]
        for field, path in (("specification", spec), ("artifact", output)):
            clean[field]["path"] = path.as_posix()
        receipt_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record = {"name": name, "type": kind}
        for field, path in (("specification", spec), ("artifact", output)):
            data = (ROOT / path).read_bytes()
            record[field] = {"path": path.as_posix(), "canonical_sha256": digest(data),
                             "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        records.append(record)
        print(f"Delivered {output}", flush=True)
        if visual:
            archify("visual-check", skill, output)
    manifest = {"schema_version": 1, "source_files": snapshot(), "diagrams": records}
    (ROOT / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return check()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Read-only freshness check; no Node needed")
    parser.add_argument("--staged", action="store_true", help="Check exactly the proposed commit")
    parser.add_argument("--visual-check", action="store_true", help="Collect four-viewport browser evidence after delivery")
    parser.add_argument("--archify-home", type=Path, default=Path(os.environ.get(
        "ARCHIFY_HOME", str(Path.home() / ".codex/skills/archify"))))
    args = parser.parse_args()
    if args.staged and not args.check:
        parser.error("--staged requires --check")
    try:
        return check(staged=args.staged) if args.check else refresh(args.archify_home, args.visual_check)
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
