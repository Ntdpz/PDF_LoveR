"""Remove known regenerable build/cache output; dry run unless --apply is given."""
import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIRS = ("build-modern", "build-portable", "build-portable-dist", "build-release",
              "build-release-dist", "build-superapp", "build-superapp-dist", "build-verification")
SCRATCH_FILES = {"benchmark_drag.py", "home-check.json", "log.json", "package-check.json", "preflight.json"}


def candidates(root):
    paths = [root / name for name in BUILD_DIRS]
    paths += [root / "packaging/.verification", root / "packaging/distribution-check.json",
              root / "__pycache__"]
    for name in ("pdf_lover", "tests", "scripts", "packaging", ".hallmark"):
        base = root / name
        if base.exists():
            paths.extend(base.rglob("__pycache__"))
    scratch = root / ".hallmark"
    if scratch.exists():
        paths += [p for p in scratch.iterdir() if p.is_file() and
                  (p.name in SCRATCH_FILES or p.suffix == ".png")]
    result = []
    for path in sorted(set(paths), key=lambda p: (len(p.parts), str(p))):
        if not path.exists():
            continue
        resolved = path.resolve()
        if resolved == root or not resolved.is_relative_to(root):
            raise RuntimeError(f"Outside workspace: {path}")
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise RuntimeError(f"Linked target preserved: {path}")
        if any(path.is_relative_to(parent) for parent in result if parent.is_dir()):
            continue
        # Refuse linked descendants rather than following them during recursion.
        if path.is_dir():
            for directory, dirs, files in os.walk(path, followlinks=False):
                for name in dirs + files:
                    child = Path(directory) / name
                    if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                        raise RuntimeError(f"Linked descendant preserved: {child}")
        result.append(path)
    return result


def size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not (root / "pdf_lover/app.py").is_file() or not (root / "main.py").is_file():
        parser.error("Target must be a PDF LoveR source workspace.")
    paths = candidates(root)
    total = 0
    for path in paths:
        amount = size(path)
        total += amount
        print(f"{path.relative_to(root)}: {amount / 1024**2:.2f} MiB")
    print(f"{'Remove' if args.apply else 'Dry run'}: {len(paths)} targets, {total / 1024**2:.2f} MiB")
    if args.apply:
        for path in paths:
            # Final containment check immediately before each mutation.
            resolved = path.resolve(strict=True)
            if resolved == root or not resolved.is_relative_to(root):
                raise RuntimeError(f"Unsafe target: {path}")
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        scratch = root / ".hallmark"
        if scratch.is_dir() and not any(scratch.iterdir()):
            scratch.rmdir()


if __name__ == "__main__":
    main()
