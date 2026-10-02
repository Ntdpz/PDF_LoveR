"""Run engine checks, followed by native UI checks sequentially on Windows."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit-only", action="store_true")
    args = parser.parse_args()
    commands = [["scripts/update_diagrams.py", "--check"],
                ["scripts/check_low_spec.py"],
                ["-m", "unittest", "discover", "-s", "tests/unit", "-v"]]
    if not args.unit_only:
        if sys.platform != "win32":
            parser.error("Native UI checks require Windows; use --unit-only elsewhere.")
        commands.extend([[f"tests/ui/{name}.py"] for name in (
            "verify_png", "verify_home", "verify_merge", "verify_merge_cards",
            "verify_file_drop", "verify_drag_performance", "verify_split", "verify_page_tools", "verify_rotate", "verify_resources", "verify_selector")])
    for command in commands:
        print("Running:", " ".join(command), flush=True)
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
