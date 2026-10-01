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
            report.write_text(json.dumps({"passed": True, "gui": "constructed", "converted_pages": 2,
                                          "dpi": 150, "png_size": [300, 150]}, ensure_ascii=False), encoding="utf-8")
        except Exception as error:
            report.write_text(json.dumps({"passed": False, "errors": failures + [str(error)]}, ensure_ascii=False), encoding="utf-8")
        finally:
            root.destroy()
            sandbox.cleanup()

    root.after(150, finish)
    root.mainloop()
