"""Native PDF to Image controls, warnings, bounded events and layout checks."""
import csv
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import customtkinter as ctk
import pymupdf
from PIL import Image
from pdf_lover.app import App
from pdf_lover.features.png.service import FORMATS
from tests.ui.verify_png import pump, screenshot

ROOT = Path(__file__).resolve().parents[2]


def main():
    failures = []
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        source = folder / "image controls.pdf"
        with pymupdf.open() as doc:
            for index in range(61):
                doc.new_page(width=144, height=72).insert_text((10, 30), str(index))
            doc.save(source)
        for scale in (1, 1.25):
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            root = ctk.CTk()
            root.report_callback_exception = lambda kind, value, trace: failures.append(str(value))
            app = App(root)
            app.show_tool("pdf-png")
            root.geometry("920x700+15+15")
            page = app.png
            pump(root, 0.1)
            page.add_paths([source])
            page.output.set(str(folder / f"output-{scale}"))
            page.size_mode.set("พิกเซล")
            page.update_image_settings()
            page.start()
            assert not app.busy and "อย่างน้อยหนึ่งช่อง" in page.status.get()
            page.width_px.set("240")
            page.height_px.set("240")
            for invalid in ("NaN", "-1", "abc", "0.000000001"):
                page.limit_size.set(invalid)
                page.start()
                assert not app.busy
            page.limit_unit.set("KB")
            page.limit_size.set("0.001")
            for file_type, extension in FORMATS.items():
                page.file_type.set(file_type)
                page.update_image_settings()
                assert bool(page.jpeg_entry.winfo_manager()) == (file_type == "JPG")
                page.start_button.invoke()
                assert app.busy
                assert page.format_menu.cget("state") == "disabled"
                deadline = time.monotonic() + 30
                while app.busy and time.monotonic() < deadline:
                    pump(root, 0.01)
                assert not app.busy and not page.errors, page.errors
                assert page.warning_count == 61 and len(page.warnings) == 50
                assert page.events.maxsize == 32 and page.events.empty()
                outputs = sorted((folder / f"output-{scale}").glob(f"*/*.{extension}"))
                assert len(outputs) == 61
                with Image.open(outputs[0]) as image:
                    assert image.size == (240, 120)
                report = outputs[0].parent / "image_report.csv"
                with report.open(encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                assert len(rows) == 61 and all(row["over_limit"] == "True" for row in rows)
                assert page.error_button.winfo_manager()
                cases.append({"scaling": scale, "format": file_type, "pages": 61, "warnings": page.warning_count})
            assert app.show_tool("merge")
            assert app.show_tool("pdf-png")
            assert page.width_px.get() == "240" and page.file_type.get() == "TIFF"
            assert page.start_button.winfo_rooty() + page.start_button.winfo_height() <= root.winfo_rooty() + root.winfo_height()
            screenshot(root, f"image-options-{scale}.png")
            page.size_mode.set("DPI")
            page.update_image_settings()
            assert not page.width_entry.winfo_manager() and page.dpi_box.winfo_manager()
            assert not failures, failures
            for timer in root.tk.call("after", "info"):
                root.after_cancel(timer)
            root.destroy()
    evidence = {"passed": True, "cases": cases, "event_queue_capacity": 32,
                "warning_preview_limit": 50, "source_settings_retained": True,
                "native_callback_errors": failures, "limitations": ["Development Windows PC; physical low-spec HDD machine not tested"]}
    (ROOT / "docs/image-ui-verification-1.8.0.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("PASS: formats, pixel controls, size validation, 61 warnings, bounded queue, state retention, 920x700 at 100%/125%")


if __name__ == "__main__":
    main()
