"""Hidden packaged-app smoke check, isolated from user documents."""
import json
import traceback
import hashlib
import tempfile
import time
from pathlib import Path

import pymupdf
from PIL import Image
from pdf_lover.core.cancellation import Cancelled


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
    selector_pages = {}
    def callback_error(kind, value, trace):
        failures.append(str(value))
        root.after(0, lambda: complete({'passed': False, 'errors': failures}))
    root.report_callback_exception = callback_error
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
            from pdf_lover.features.png.service import convert_pdf, ImageOptions, FORMATS
            for file_type, extension in FORMATS.items():
                image_folder = convert_pdf(source, folder / "images", 150, lambda *_: None,
                                           ImageOptions(file_type=file_type, width=200), pages=(2,))
                assert [p.name for p in image_folder.glob("*." + extension)] == [source.stem + "_page_002." + extension]
                with Image.open(next(image_folder.glob("*." + extension))) as image:
                    assert image.size == (200, 100), (file_type, image.size)
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
        root.destroy()
        result["preview_cleanup"] = app.preview_coordinator.process is None
        if not result["preview_cleanup"]:
            result["passed"] = False
            result.setdefault("errors", []).append("Preview child survived root destruction")
        report.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        sandbox.cleanup()

    def selector_preview_ready(page, name, timeout):
        """Scroll every synthetic page through the withdrawn window's tiny viewport."""
        selector = page.selector
        required = selector.worker.required
        seen = selector_pages.setdefault(name, set())
        if required and all(selector.cache.get(key) for key in required):
            seen.update(key[3] + 1 for key in required)
            assert len(selector.visible) <= selector.VISIBLE
            assert selector.cache.resident_bytes <= selector.cache.max_bytes
            missing = set(range(1, selector.info.page_count + 1)) - seen
            if not missing:
                return True
            number = min(missing)
            if hasattr(selector, 'order'):
                number = selector.order.index(number) + 1
            rows = (selector.info.page_count + selector.columns - 1) // selector.columns
            total = max(selector.canvas.winfo_height(), rows * selector.step_y)
            selector._scroll("moveto", ((number - 1) // selector.columns * selector.step_y) / total)
            selector.render()
        assert time.monotonic() - started < timeout, name + " viewport thumbnail timeout"
        return False

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
            if not selector_preview_ready(page, "split", 60):
                root.after(100, finish_split)
                return
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
            if not selector_preview_ready(page, tool, 85):
                root.after(100, lambda: finish_page_tool(tool))
                return
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
            if not selector_preview_ready(page, "rotate", 115):
                root.after(100, finish_rotation)
                return
            assert all(page.preview.cache.get(key) for key in page.preview.keys())
            assert page.selector.worker.process is page.preview.worker.process is app.preview_coordinator.process
            assert app.preview_coordinator.process and app.preview_coordinator.process.is_alive()
            for job in page.plan.jobs:
                with pymupdf.open(job.info.path) as original, pymupdf.open(job.output.path) as result:
                    assert result.page_count == original.page_count
                    for number, (before, after) in enumerate(zip(original, result), 1):
                        assert after.rotation == (before.rotation + (90 if number in job.selected else 0)) % 360
                        assert after.get_text() == before.get_text()
            assert all(hashlib.sha256(path.read_bytes()).hexdigest() == value for path, value in rotation_hashes.items())
            assert not failures, failures
            assert all(not view.activity_indicator.running for view in app.views.values())
            from pdf_lover.core.cancellation import Cancelled
            from pdf_lover.features.merge.service import merge_pdfs
            from pdf_lover.features.split.service import split_pdf
            from pdf_lover.features.extract.service import extract_pdf
            from pdf_lover.features.delete_pages.service import delete_pdf
            from pdf_lover.features.rotate.service import rotate_pdf
            from pdf_lover.features.png.service import convert_pdf
            app.busy = True
            page.cancel_button.invoke()
            token = page.cancel_event
            assert token.is_set() and app.busy
            checks = [
                lambda: convert_pdf(source, folder, 72, lambda *_: None, cancel=token),
                lambda: merge_pdfs(list(app.merge.files), folder/'cancelled.pdf', cancel=token),
                lambda: split_pdf(app.get_page('split').plan, cancel=token),
                lambda: extract_pdf(app.get_page('extract-pages').plan, cancel=token),
                lambda: delete_pdf(app.get_page('delete-pages').plan, cancel=token),
                lambda: rotate_pdf(page.plan, cancel=token),
            ]
            for check in checks:
                try:check()
                except Cancelled:pass
                else:raise AssertionError('Packaged engine ignored cancellation')
            app.busy = False
            assert all(not view.cancel_button.winfo_ismapped() for view in app.views.values())
            thumbnails = 2 + sum(len(pages) for pages in selector_pages.values()) + len(page.preview.cache)
            summary.update({"passed": True, "gui": "constructed", "converted_pages": 2,
                      "dpi": 150, "png_size": [300, 150], "merged_pages": 3, "merge_order": "verified",
                      "split_groups": [1, 2], "split_preview": "verified", "split_order": "verified",
                      "extract_original_pages": [1, 3], "delete_removed_pages": [2],
                      "delete_retained_pages": [1, 3], "original_unchanged": True,
                      "thumbnail_worker": "single shared process", "thumbnail_count": thumbnails,
                      "preview_process_limit": 1,
                      "activity_indicators": "all six tools constructed; inactive after jobs",
                      "cancellation": "button requests stop; six packaged engines honour token; busy restored",
                      "selector_layout": "vertical viewport grid",
                      "selector_preview_pages": {name: sorted(pages) for name, pages in selector_pages.items()},
                      "rotation_files": 2, "rotation_selected_pages": [[2], [1, 2]],
                      "rotation_angle": 90, "rotation_icon_cycle": "verified", "rotation_preview": "verified",
                      "file_drop": "Windows native callbacks verified for all 6 tools",
                      "tkdnd_version": app.file_drop.version})
            start_order()
        except Exception as error:
            complete({"passed": False, "errors": failures + [str(error)]})

    summary = {}

    def start_order():
        assert app.show_tool('organize')
        native_drop(root, [app.merge.destination])
        root.after(100, prepare_order)

    def prepare_order():
        page = app.get_page('organize')
        if app.busy and time.monotonic() - started < 125:
            root.after(100, prepare_order)
            return
        try:
            assert page.info and not app.busy
            page.output.set(str(folder))
            page.prefix.set('ordered')
            page.selector.expression.set('1')
            page.selector.nudge(1)
            assert page.selector.order == (2,1,3)
            page.start()
            root.after(100, finish_order)
        except Exception as error:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    def finish_order():
        page = app.get_page('organize')
        if app.busy and time.monotonic() - started < 125:
            root.after(100, finish_order)
            return
        try:
            assert not app.busy and page.destination, page.status.get()
            if not selector_preview_ready(page, 'organize', 125):
                root.after(100, finish_order)
                return
            with pymupdf.open(app.merge.destination) as original, pymupdf.open(page.plan.outputs[0].path) as result:
                for index, number in enumerate((2,1,3)):
                    assert result[index].get_text() == original[number-1].get_text()
                    assert result[index].get_pixmap().samples == original[number-1].get_pixmap().samples
            assert hashlib.sha256(app.merge.destination.read_bytes()).hexdigest() == page_tool_source_hash
            from pdf_lover.core.cancellation import Cancelled
            from pdf_lover.features.organize.service import reorder_pdf
            app.busy = True
            page.cancel_button.invoke()
            try:
                reorder_pdf(page.plan, cancel=page.cancel_event)
            except Cancelled:
                pass
            else:
                raise AssertionError('Packaged reorder engine ignored cancellation')
            app.busy = False
            assert not failures, failures
            summary.update(ordered_original_pages=[2,1,3], order_preview=True,
                           activity_indicators='all seven tools constructed; inactive after jobs',
                           cancellation='seven packaged engines honour token; busy restored',
                           file_drop='Windows native callbacks verified for all 7 tools',
                           selector_preview_pages={name:sorted(pages) for name,pages in selector_pages.items()})
            # Exercise new edit operations in every frozen distribution.
            extra = folder / 'packaged-extra.pdf'
            with pymupdf.open() as document:
                for index in range(2):
                    document.new_page(width=240, height=160).insert_text((20,30), f'IMPORTED {index+1}')
                document.save(extra)
            page.selector.expression.set('2')
            page.add_paths([extra])
            root.after(100, finish_edit_import)
        except Exception as error:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    def finish_edit_import():
        page = app.get_page('organize')
        if app.busy and time.monotonic() - started < 125:
            root.after(100, finish_edit_import)
            return
        try:
            selector = page.selector
            assert selector.order == (2,4,5,1,3), selector.order
            selector.expression.set('3')
            selector.delete_selected()
            assert selector.order == (2,4,1,3)
            selector.undo()
            assert selector.order == (2,4,5,1,3)
            selector.undo(redo=True)
            assert selector.order == (2,4,1,3)
            selector.reset_order()
            assert selector.order == (1,2,3)
            selector.undo()
            assert selector.order == (2,4,1,3)
            page.prefix.set('organized-with-import')
            page.start()
            root.after(100, finish_edit_export)
        except Exception:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    def finish_edit_export():
        page = app.get_page('organize')
        if app.busy and time.monotonic() - started < 125:
            root.after(100, finish_edit_export)
            return
        try:
            assert page.destination and not app.busy, page.status.get()
            from pdf_lover.features.organize.service import organize_pdf
            with pymupdf.open(page.plan.outputs[0].path) as result:
                assert result.page_count == 4
                assert 'IMPORTED 1' in result[1].get_text()
                for slot, identity in enumerate(page.selector.order):
                    source_index, number = page.selector.references[identity]
                    with pymupdf.open(page.selector.sources[source_index].path) as source_document:
                        assert result[slot].get_pixmap().samples == source_document[number-1].get_pixmap().samples
            app.busy = True
            page.cancel_button.invoke()
            try:
                organize_pdf(page.plan, cancel=page.cancel_event)
            except Cancelled:
                pass
            else:
                raise AssertionError('Packaged edit engine ignored cancellation')
            app.busy = False
            summary.update(organize_import_delete_undo_redo=True, organize_native_pixels=True,
                           organize_cancel=True)
            start_numbers()
        except Exception:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    def start_numbers():
        assert app.show_tool('page-numbers')
        native_drop(root, [app.merge.destination])
        root.after(100, prepare_numbers)

    def prepare_numbers():
        page = app.get_page('page-numbers')
        if app.busy and time.monotonic()-started < 125:
            root.after(100, prepare_numbers)
            return
        try:
            assert page.info and not app.busy
            page.output.set(str(folder)); page.prefix.set('numbered')
            page.selector.expression.set('1,3')
            page.number_format.set('page');page.thai_digits.set(True)
            page.number_sequence.set('selected')
            page.show_view('preview')
            page.start()
            root.after(100, finish_numbers)
        except Exception as error:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    def finish_numbers():
        page = app.get_page('page-numbers')
        if app.busy and time.monotonic()-started < 125:
            root.after(100, finish_numbers)
            return
        try:
            assert page.destination and not app.busy, page.status.get()
            page.preview.render()
            if not all(page.preview.cache.get(k) for k in page.preview.keys()) and time.monotonic()-started < 125:
                root.after(100, finish_numbers)
                return
            assert all(page.preview.cache.get(k) for k in page.preview.keys())
            from pdf_lover.features.page_numbers.service import number_pdf, stamp_page
            from pdf_lover.core.cancellation import Cancelled
            with pymupdf.open(page.plan.outputs[0].path) as doc,pymupdf.open(app.merge.destination) as before:
                assert 'หน้า ๑' in doc[0].get_text() and 'หน้า ๒' in doc[2].get_text()
                assert doc[1].get_pixmap().samples == before[1].get_pixmap().samples
                key=page.preview.keys()[1]
                p=doc[key[3]];factor=min(key[5]/p.rect.width,key[6]/p.rect.height)
                pix=p.get_pixmap(matrix=pymupdf.Matrix(factor,factor),alpha=False,colorspace=pymupdf.csRGB)
                assert page.preview.cache[key] == (pix.width,pix.height,pix.samples)
                fonts=[font for font in doc[0].get_fonts(full=True) if 'NotoSansThai' in font[3].replace(' ', '')]
                assert fonts and all(doc.extract_font(f[0])[3] for f in fonts)
            assert hashlib.sha256(app.merge.destination.read_bytes()).hexdigest() == page_tool_source_hash
            app.busy=True;page.cancel_button.invoke()
            try:number_pdf(page.plan,cancel=page.cancel_event)
            except Cancelled:pass
            else:raise AssertionError('Packaged numbering ignored cancellation')
            app.busy=False
            summary.update(page_numbers=True,numbered_selected_pages=[1,3],thai_font_embedded=True,
                numbered_preview_matches_output=True,activity_indicators='all eight tools',
                cancellation='eight packaged engines honour token; busy restored',
                file_drop='Windows native callbacks verified for all8 tools')
            assert not failures,failures
            complete(summary)
        except Exception as error:
            complete({'passed':False,'errors':failures+[traceback.format_exc()]})

    root.after(150, finish)
    root.after(120000, lambda: complete({'passed': False, 'errors': failures +
                                       [f'Smoke timeout: route={app.route}, busy={app.busy}, status={app.active_page.status.get()}']}))
    root.mainloop()
