"""Native split UI, independent rendering and bounded preview verification."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/ui'), str(ROOT / 'tests/unit')]
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageChops
from pdf_lover.app import App
from pdf_lover.diagnostics.self_test import native_drop
from test_pdf_merge import make_pdf
from verify_merge import pump, capture, dispose


def wait(root, app, seconds=20):
    deadline = time.monotonic() + seconds
    while app.busy and time.monotonic() < deadline:
        pump(root, 0.05)
    assert not app.busy, 'split worker timed out'


def main():
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    errors = []
    with tempfile.TemporaryDirectory(prefix='pdf-split-ui-') as sandbox:
        folder = Path(sandbox)
        source = folder / 'เอกสารตัวอย่าง.pdf'
        make_pdf(source, [f'PAGE {i}' for i in range(1, 11)], field='Value')
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root)
        assert app.show_tool('split')
        page = app.active_page
        root.geometry('1080x780+40+40')
        pump(root)
        capture(root, 'split-empty.png')
        page.start()
        assert not app.busy and page.plan is None
        native_drop(root, [source])
        assert app.file_drop.pending == [source]
        pump(root, 0.05)
        wait(root, app)
        assert page.info.page_count == 10
        page.add_paths([source])
        assert app.busy and not app.show_home()
        wait(root, app)
        page.output.set(str(folder))
        page.mode.set('ranges')
        page.selector.expression.set('1-3,5,8-10')
        assert [list(output.pages) for output in page.plan.outputs] == [[1, 2, 3], [5], [8, 9, 10]]
        rows = [page.results.item(row, 'values') for row in page.results.get_children()]
        assert len(rows) == 3 and rows[0][0] == '1–3'
        deadline = time.monotonic() + 15
        while len(page.selector.cache) < 4 and time.monotonic() < deadline:
            pump(root, 0.1)
        assert len(page.selector.cache) == 4 and all(page.selector.cache.values())
        page.selector.toggle(2)
        assert page.selector.expression.get() == '1,3,5,8-10'
        page.selector.select_all()
        assert page.selector.selection() == tuple(range(1, 11))
        page.selector.none_button.invoke()
        assert page.plan is None and page.start_button.cget('state') == 'disabled'
        for expression in ('0', '11', '4-2', '3,2', '1-3,3', '1,,2'):
            page.selector.expression.set(expression)
            page.start()
            assert page.plan is None and not app.busy
        page.selector.expression.set('1-3,5,8-10')
        page.prefix.set('CON')
        assert page.plan is None
        page.prefix.set('ชุดเอกสาร')
        page.output.set('')
        assert page.plan is None
        page.output.set(str(folder))
        conflict = page.plan.outputs[1].path
        conflict.write_bytes(b'KEEP')
        page.refresh_plan()
        assert page.plan is None and conflict.read_bytes() == b'KEEP'
        conflict.unlink()
        page.refresh_plan()
        page.add_paths([source, source])
        assert not app.busy and 'หนึ่งไฟล์' in page.status.get()
        page.refresh_plan()
        assert app.show_home() and app.show_tool('merge') and app.show_tool('split')
        assert app.active_page is page and page.selector.expression.get() == '1-3,5,8-10'
        pump(root)
        capture(root, 'split-ready.png')
        planned = page.plan
        page.start()
        assert app.busy and not app.show_home()
        assert page.selector.entry.cget('state') == 'disabled'
        page.add_paths([source]); page.start(); page.selector.toggle(1)
        wait(root, app)
        assert page.destination == folder and page.open_button.cget('state') == 'normal', page.status.get()
        capture(root, 'split-success.png')
        for output in planned.outputs:
            with pymupdf.open(output.path) as result:
                assert result.page_count == len(output.pages)
                assert [p.get_text().splitlines()[0] for p in result] == [f'PAGE {i}' for i in output.pages]
        renderer = shutil.which('pdftoppm')
        assert renderer, 'Poppler required'
        subprocess.run([renderer, '-r', '72', '-png', str(source), str(folder / 'before')], check=True, capture_output=True)
        for index, output in enumerate(planned.outputs):
            subprocess.run([renderer, '-r', '72', '-png', str(output.path), str(folder / f'after{index}')], check=True, capture_output=True)
            for number, result in zip(output.pages, sorted(folder.glob(f'after{index}-*.png'))):
                original = next(path for path in folder.glob('before-*.png') if int(path.stem.split('-')[-1]) == number)
                with Image.open(original) as a, Image.open(result) as b:
                    assert a.size == b.size and ImageChops.difference(a, b).getbbox() is None
        for mode, chunk, counts in [('chunks', '3', [3, 3, 3, 1]), ('pages', '1', [1]*10)]:
            page.prefix.set(mode)
            page.mode.set(mode)
            page.chunk_size.set(chunk)
            assert [len(output.pages) for output in page.plan.outputs] == counts
            if mode == 'chunks':
                for invalid in ('0', '11', '2.5', 'abc'):
                    page.chunk_size.set(invalid)
                    assert page.plan is None
                page.chunk_size.set(chunk)
            plan = page.plan
            page.start(); wait(root, app)
            assert all(output.path.exists() for output in plan.outputs)
        gone = folder / 'gone.pdf'; make_pdf(gone, ['Gone'])
        page.add_paths([gone]); wait(root, app)
        page.output.set(str(folder)); page.prefix.set('missing')
        gone.unlink(); page.start(); wait(root, app)
        assert page.progress.get() == 0 and page.add_button.cget('state') == 'normal'
        bad = folder / 'bad.pdf'; bad.write_bytes(b'BAD')
        page.add_paths([bad]); wait(root, app)
        assert 'เปิด PDF ไม่ได้' in page.status.get()
        large = folder / 'many-pages.pdf'
        with pymupdf.open() as document:
            for _ in range(240):
                document.new_page(width=144, height=72)
            document.save(large)
        page.add_paths([large]); wait(root, app)
        page.output.set(str(folder)); page.mode.set('pages')
        assert len(page.plan.outputs) == 240 and len(page.results.get_children()) == 25
        page.move_outputs(1)
        assert page.results.item(page.results.get_children()[0], 'values')[0] == '26'
        page.mode.set('ranges')
        for _ in range(59):
            page.selector.move(1)
        assert page.selector.offset == 236 and len(page.selector.pending) <= 4
        pump(root, 0.5)
        assert len(page.selector.cache) <= 32
        page.add_paths([source]); wait(root, app)
        page.mode.set('ranges'); page.selector.expression.set('1-3,5,8-10'); page.output.set(str(folder))
        root.geometry('920x700+40+40'); pump(root)
        capture(root, 'split-compact.png')
        for widget in (page.selector, page.results, page.start_button, page.open_button):
            assert widget.winfo_rooty() + widget.winfo_height() <= root.winfo_rooty() + root.winfo_height()
        for widget in (*page.selector.cards, page.selector.previous, page.selector.next):
            assert widget.winfo_rooty() + widget.winfo_height() <= page.selector.winfo_rooty() + page.selector.winfo_height()
        worker = page.selector.worker.process
        dispose(root)
        assert page.selector.worker.process is None and worker is not None
        ctk.set_widget_scaling(1.25); ctk.set_window_scaling(1.25)
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root); app.show_tool('split'); page = app.active_page
        page.add_paths([source]); wait(root, app)
        root.geometry('1080x780+10+10'); pump(root)
        capture(root, 'split-scaled.png')
        dispose(root)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before
        assert not errors, errors
    report = {'passed': True, 'modes': ['pages', 'ranges', 'chunks'], 'range_output_pages': [3, 1, 3],
              'checks': ['native drop and one-document guard', 'async inspection', 'page thumbnails and multi-selection',
                         'range syntax/order/duplicates/bounds', 'N validation and final remainder',
                         'preview filenames and output conflicts', 'original SHA256 unchanged', 'Poppler pixel equivalence',
                         'retained state and busy guards', 'missing/corrupt source recovery',
                         '240-page bounded thumbnails and paged output preview',
                         '920x700 and 125% scaling', 'preview child cleanup', 'no Tk callback errors']}
    (ROOT / 'docs/split-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
