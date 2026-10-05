"""Fresh-process image export measurement against the original PNG renderer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.benchmark_resources import counters


def child(mode):
    import pymupdf
    from pdf_lover.features.png.service import convert_pdf, ImageOptions
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "fixture.pdf"
        with pymupdf.open() as doc:
            for index in range(3):
                page = doc.new_page()
                page.insert_text((72, 72), f"Page {index}")
                page.draw_rect(pymupdf.Rect(72, 90, 220, 160), fill=(0.1, 0.5, 0.8))
            doc.save(source)
        started = time.perf_counter()
        if mode == "baseline":
            # Original service's full-page PNG DPI algorithm, before this change.
            output = root / "baseline"
            output.mkdir()
            with pymupdf.open(source) as doc:
                for index, page in enumerate(doc, 1):
                    image = page.get_pixmap(dpi=600, alpha=False)
                    try:
                        image.save(output / f"fixture_page_{index:03}.png")
                    finally:
                        del image
        else:
            file_type = "PNG" if mode == "current" else mode
            output = convert_pdf(source, root, 600 if mode == "current" else 300,
                                 lambda *_: None, ImageOptions(file_type=file_type))
        elapsed = time.perf_counter() - started
        stats = counters(os.getpid())
        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.glob("*.png"))]
        return {"mode": mode, "dpi": 600 if mode in ("baseline", "current") else 300,
                "elapsed_seconds": round(elapsed, 3), "peak_working_set_mib": round(stats["peak_working_set_mib"], 2),
                "cpu_seconds": round(stats["cpu_seconds"], 3), "png_hashes": hashes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child")
    args = parser.parse_args()
    if args.child:
        print(json.dumps(child(args.child)))
        return
    runs = []
    for mode in ("baseline", "current", "baseline", "current", "JPG", "WebP", "TIFF"):
        result = subprocess.run([sys.executable, __file__, "--child", mode], capture_output=True, text=True, check=True, timeout=120)
        runs.append(json.loads(result.stdout))
    assert all(run["png_hashes"] == runs[0]["png_hashes"] for run in runs if run["mode"] in ("baseline", "current"))
    report = {"passed": True, "host": platform.platform(), "logical_cpu_count": os.cpu_count(),
              "scope": "3 synthetic A4 pages; before/current PNG 600 DPI (two fresh processes each); new codecs 300 DPI (one each)",
              "runs": runs, "native_png_bytes_preserved": True,
              "limitations": ["Not physical 2-core/4-GiB/HDD certification", "No scanned-image or 40-million-pixel codec stress measurement", "Warm development environment; frozen cold startup not benchmarked"]}
    target = Path(__file__).resolve().parents[1] / "docs/image-resources-1.8.0.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(runs, indent=2))


if __name__ == "__main__":
    main()
