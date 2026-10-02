"""Hidden packaged-app smoke check, isolated from user documents."""
import json
import hashlib
import tempfile
import time
from pathlib import Path

import pymupdf
from PIL import Image


def native_drop(root, paths):
    """Drive the Windows adapter used by Explorer, including Tcl substitutions."""
    data = root.tk.call('list', *(str(path) for path in paths))
    action = root.tk.call('tkdnd::olednd::HandleDragEnter', root._w,
                         ('CF_HDROP',), ('copy',), (), 0, 0, ('CF_HDROP',), data)
    assert action == 'copy', action
    action = root.tk.call('tkdnd::olednd::HandleDrop', root._w, (), 0, 0, 'CF_HDROP', data)
    assert action == 'copy', action
    root.tk.call('tkdnd::olednd::HandleDragLeave', root._w)


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
        app.show_tool('pdf-png')
        native_drop(root, [source])
        app.png.output.set(str(folder / "images"))
        app.png.dpi.set("150")
        root.after(10, app.png.start)
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
            assert not app.png.errors, app.png.errors
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
            native_drop(root, [second, source])
            app.merge.output.set(str(folder / "รวมเอกสาร.pdf"))
            root.after(10, app.merge.start)
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
        if app.merge.cards.pending and time.monotonic() - started < 45:
            root.after(100, finish_merge)
            return
        try:
            assert not app.busy, "Merge timeout"
            assert not failures, failures
            assert app.merge.destination, app.merge.status.get()
            assert len(app.merge.cards.cache) == 2, "Thumbnail worker did not return both previews"
            assert all(image is not None for image in app.merge.cards.cache.values()), "Thumbnail rendering failed"
            with pymupdf.open(app.merge.destination) as document:
                assert document.page_count == 3
                assert "MERGE FIRST" in document[0].get_text()
                assert document[1].rect == pymupdf.Rect(0, 0, 144, 72)
            assert app.show_tool("split"), "Split route not available"
            native_drop(root, [app.merge.destination])
            root.after(100, prepare_split)
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    def prepare_split():
        page = app.get_page("split")
        if (app.busy or page.info is None) and time.monotonic() - started < 60:
            root.after(100, prepare_split)
            return
        try:
            assert page.info and not app.busy, "Split inspection timeout"
            page.output.set(str(folder))
            page.mode.set("ranges")
            page.selector.expression.set("1,2-3")
            assert [len(output.pages) for output in page.plan.outputs] == [1, 2]
            page.start()
            root.after(100, finish_split)
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    def finish_split():
        page = app.get_page("split")
        if (app.busy or page.selector.pending) and time.monotonic() - started < 60:
            root.after(100, finish_split)
            return
        try:
            assert not app.busy and page.destination, page.status.get()
            assert len(page.selector.cache) == 3 and all(page.selector.cache.values())
            for output in page.plan.outputs:
                with pymupdf.open(output.path) as result:
                    assert result.page_count == len(output.pages)
            with pymupdf.open(page.plan.outputs[0].path) as result:
                assert "MERGE FIRST" in result[0].get_text()
            assert not failures, failures
            start_page_tool("extract-pages")
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    page_tool_source_hash = None

    def start_page_tool(tool):
        nonlocal page_tool_source_hash
        page_tool_source_hash = hashlib.sha256(app.merge.destination.read_bytes()).hexdigest()
        assert app.show_tool(tool), tool + " route not available"
        native_drop(root, [app.merge.destination])
        root.after(100, lambda: prepare_page_tool(tool))

    def prepare_page_tool(tool):
        page = app.get_page(tool)
        if (app.busy or page.info is None) and time.monotonic() - started < 85:
            root.after(100, lambda: prepare_page_tool(tool))
            return
        try:
            assert page.info and not app.busy, tool + " inspection timeout"
            page.output.set(str(folder))
            page.prefix.set(tool)
            page.selector.expression.set("1,3" if tool == "extract-pages" else "2")
            assert page.plan.outputs[0].pages == (1, 3)
            page.start()
            root.after(100, lambda: finish_page_tool(tool))
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    def finish_page_tool(tool):
        page = app.get_page(tool)
        if (app.busy or page.selector.pending) and time.monotonic() - started < 85:
            root.after(100, lambda: finish_page_tool(tool))
            return
        try:
            assert not app.busy and page.destination, page.status.get()
            assert len(page.selector.cache) == 3 and all(page.selector.cache.values())
            with pymupdf.open(page.plan.outputs[0].path) as result:
                assert result.page_count == 2 and "MERGE FIRST" in result[0].get_text()
                assert result[1].rect == pymupdf.Rect(0, 0, 144, 72)
            assert hashlib.sha256(app.merge.destination.read_bytes()).hexdigest() == page_tool_source_hash
            assert not failures, failures
            if tool == "extract-pages":
                start_page_tool("delete-pages")
                return
            start_rotation()
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    rotation_hashes = {}

    def start_rotation():
        for path in (app.merge.destination, source):
            rotation_hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        assert app.show_tool("rotate")
        native_drop(root, [app.merge.destination, source])
        root.after(100, prepare_rotation)

    def prepare_rotation():
        page = app.get_page("rotate")
        if (app.busy or len(page.inputs) != 2) and time.monotonic() - started < 115:
            root.after(100, prepare_rotation)
            return
        try:
            assert len(page.inputs) == 2 and not app.busy, "Rotation inspection timeout"
            page.output.set(str(folder))
            page.selector.expression.set("2")
            assert page.angle.get() == "0" and page.plan is None
            left, right = page.rotation_buttons
            for expected in ("90", "180", "270", "0"):
                right.invoke()
                assert page.angle.get() == expected
            assert page.plan is None
            left.invoke()
            assert page.angle.get() == "270"
            right.invoke()
            assert page.angle.get() == "0"
            right.invoke()
            page.preview.move(1)
            assert [j.selected for j in page.plan.jobs] == [(2,), (1, 2)]
            page.start()
            root.after(100, finish_rotation)
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    def finish_rotation():
        page = app.get_page("rotate")
        if (app.busy or page.selector.pending or page.preview.pending) and time.monotonic() - started < 115:
            root.after(100, finish_rotation)
            return
        try:
            assert not app.busy and page.destination, page.status.get()
            assert all(page.selector.cache.values())
            assert all(page.preview.cache.get(key) for key in page.preview.keys())
            for job in page.plan.jobs:
                with pymupdf.open(job.info.path) as original, pymupdf.open(job.output.path) as result:
                    assert result.page_count == original.page_count
                    for number, (before, after) in enumerate(zip(original, result), 1):
                        assert after.rotation == (before.rotation + (90 if number in job.selected else 0)) % 360
                        assert after.get_text() == before.get_text()
            assert all(hashlib.sha256(path.read_bytes()).hexdigest() == value for path, value in rotation_hashes.items())
            assert not failures, failures
            thumbnails = 11 + len(page.selector.cache) + len(page.preview.cache)
            complete({"passed": True, "gui": "constructed", "converted_pages": 2,
                      "dpi": 150, "png_size": [300, 150], "merged_pages": 3, "merge_order": "verified",
                      "split_groups": [1, 2], "split_preview": "verified", "split_order": "verified",
                      "extract_original_pages": [1, 3], "delete_removed_pages": [2],
                      "delete_retained_pages": [1, 3], "original_unchanged": True,
                      "thumbnail_worker": "separate process", "thumbnail_count": thumbnails,
                      "rotation_files": 2, "rotation_selected_pages": [[2], [1, 2]],
                      "rotation_angle": 90, "rotation_icon_cycle": "verified", "rotation_preview": "verified",
                      "file_drop": "Windows native callbacks verified for all 6 tools",
                      "tkdnd_version": app.file_drop.version})
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    root.after(150, finish)
    root.mainloop()
