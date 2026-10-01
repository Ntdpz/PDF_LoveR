"""Hidden packaged-app smoke check, isolated from user documents."""
import json
import tempfile
import time
from pathlib import Path

import pymupdf
from PIL import Image


def run(root, app_class, report):
    root.withdraw()
    report = Path(report).resolve()
    started = time.monotonic()
    sandbox = tempfile.TemporaryDirectory(prefix="pdf-png-package-")
    folder = Path(sandbox.name)
    failures = []
    root.report_callback_exception = lambda kind, value, trace: failures.append(str(value))
    try:
        app = app_class(root)
        source = folder / "ทดสอบแพ็กเกจ.pdf"
        with pymupdf.open() as document:
            for _ in range(2):
                document.new_page(width=144, height=72)
            document.save(source)
        app.add_paths([source])
        app.output.set(str(folder / "images"))
        app.dpi.set("150")
        app.start()
    except Exception as error:
        failures.append(str(error))
        report.write_text(json.dumps({"passed": False, "errors": failures}, ensure_ascii=False), encoding="utf-8")
        root.destroy()
        sandbox.cleanup()
        return

    def finish():
        if app.busy and time.monotonic() - started < 30:
            root.after(100, finish)
            return
        try:
            assert not app.busy, "Conversion timeout"
            assert not app.errors, app.errors
            assert not failures, failures
            outputs = sorted((folder / "images" / source.stem).glob("*.png"))
            assert len(outputs) == 2, "Expected two PNGs"
            with Image.open(outputs[0]) as image:
                assert image.size == (300, 150), image.size
            second = folder / "เอกสารแรก.pdf"
            with pymupdf.open() as document:
                page = document.new_page(width=144, height=72)
                page.insert_text((10, 20), "MERGE FIRST", fontsize=8)
                document.save(second)
            assert app.show_tool("merge"), "Merge route not available"
            app.merge.add_paths([second, source])
            app.merge.output.set(str(folder / "รวมเอกสาร.pdf"))
            app.merge.start()
            root.after(100, finish_merge)
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    def complete(result):
        report.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        root.destroy()
        sandbox.cleanup()

    def finish_merge():
        if app.busy and time.monotonic() - started < 45:
            root.after(100, finish_merge)
            return
        try:
            assert not app.busy, "Merge timeout"
            assert not failures, failures
            assert app.merge.destination, app.merge.status.get()
            with pymupdf.open(app.merge.destination) as document:
                assert document.page_count == 3
                assert "MERGE FIRST" in document[0].get_text()
                assert document[1].rect == pymupdf.Rect(0, 0, 144, 72)
            complete({"passed": True, "gui": "constructed", "converted_pages": 2,
                      "dpi": 150, "png_size": [300, 150], "merged_pages": 3, "merge_order": "verified"})
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    root.after(150, finish)
    root.mainloop()
