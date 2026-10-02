"""Require a reviewed low-spec impact record tied to exact working/staged source."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.update_diagrams import digest, snapshot

REVIEW = "docs/low-spec-review.json"
IMPACTS = ("memory", "cpu_ui", "disk_startup", "dependencies", "output_quality")


def check(root=ROOT, staged=False):
    def read(path):
        if staged:
            return subprocess.check_output(["git", "show", f":{path}"], cwd=root, stderr=subprocess.DEVNULL)
        return (root / path).read_bytes()
    try:
        review = json.loads(read(REVIEW))
        if review.get("schema_version") != 1 or review.get("decision") != "accepted":
            raise ValueError("Review must have schema_version=1 and decision=accepted")
        if review.get("target") != {"cpu_cores": 2, "ram_gib": 4, "disk": "HDD"}:
            raise ValueError("Review target must consider 2 cores / 4 GiB / HDD")
        if review.get("source_files") != snapshot(root, staged):
            raise ValueError("Low-spec review is stale for this source/index; review the change again")
        impact = review.get("impact", {})
        if any(not isinstance(impact.get(key), str) or len(impact[key].strip()) < 20 for key in IMPACTS):
            raise ValueError(f"Describe low-spec impact for all of: {', '.join(IMPACTS)}")
        if not isinstance(review.get("limitations"), list) or not review["limitations"]:
            raise ValueError("Record measurement limitations, including hardware not tested")
        evidence = review.get("evidence", [])
        if not evidence:
            raise ValueError("At least one checked evidence artifact required")
        for item in evidence:
            path = item["path"]
            if Path(path).is_absolute() or ".." in Path(path).parts or not path.startswith("docs/"):
                raise ValueError("Evidence must be a repository-relative docs path")
            content = read(path)
            if digest(content) != item["sha256"] or json.loads(content).get("passed") is not True:
                raise ValueError(f"Changed or unsuccessful low-spec evidence: {path}")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Low-spec check failed: {error}", file=sys.stderr)
        return 1
    print("Low-spec impact and evidence match the Git index." if staged else
          "Low-spec impact and evidence match the current source.")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    raise SystemExit(check(staged=args.staged))


if __name__ == "__main__":
    main()
