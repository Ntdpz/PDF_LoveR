"""Install the repository's freshness check without replacing existing hooks."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    hook_dir = Path(subprocess.check_output(
        ["git", "rev-parse", "--git-path", "hooks"], cwd=ROOT, text=True).strip())
    if not hook_dir.is_absolute():
        hook_dir = ROOT / hook_dir
    target = hook_dir / "pre-commit"
    source = (ROOT / ".githooks/pre-commit").read_bytes()
    if target.exists() and target.read_bytes() != source:
        raise SystemExit(f"Existing hook preserved: {target}. Add the command from .githooks/pre-commit manually.")
    hook_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    target.chmod(target.stat().st_mode | 0o111)
    print(f"Installed: {target}")


if __name__ == "__main__":
    main()
