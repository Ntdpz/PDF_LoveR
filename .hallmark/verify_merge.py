"""Native merge workflow and independent Poppler rendering verification."""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageChops, ImageGrab
from pdf_to_png import App
from test_pdf_merge import make_pdf


def pump(root, seconds=0.3):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def capture(root, name):
    root.update()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ImageGrab.grab(window=hwnd).save(ROOT/'.hallmark'/name)


def wait_for_merge(root, app):
    deadline = time.monotonic() + 20
    while app.busy and time.monotonic() < deadline:
        pump(root, 0.1)
    assert not app.busy and not app.merge.busy


def dispose(root):
    for timer in root.tk.call('after', 'info'):
        root.after_cancel(timer)
    root.destroy()


def main():
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    original_cwd = Path.cwd()
    callback_errors = []
    with tempfile.TemporaryDirectory(prefix='pdf-merge-ui-') as sandbox:
        folder = Path(sandbox)
        a, b = folder/'Project Brief.pdf', folder/'Product Guide.pdf'
        make_pdf(a, ['Brief page 1', 'Brief page 2'], field='Alpha')
        make_pdf(b, ['Guide page 1'], width=340, height=200, field='Beta')
        bad = folder/'เสีย.pdf'; bad.write_bytes(b'not a PDF')
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: callback_errors.append(str(value))
        app = App(root)
        root.geometry('1080x780+40+40')
        root.resizable(False, False)
        assert app.show_tool('merge') and app.route == 'merge'
        pump(root)
        capture(root, 'merge-empty.png')
        merge = app.merge
        merge.start()
        assert not app.busy and 'อย่างน้อย 2' in merge.status.get()
        merge.add_paths([a, a, b, bad])
        assert merge.files == [a, b] and 'เพิ่มบางไฟล์ไม่ได้' in merge.status.get()
        merge.move_file(b, -1)
        assert merge.files == [b, a]
        merge.remove_file(a)
        assert merge.files == [b]
        merge.add_paths([a])
        merge.start()
        assert not app.busy and 'ที่บันทึก' in merge.status.get()
        merge.output.set(str(a))
        merge.start()
        assert not app.busy and 'ต้นฉบับ' in merge.status.get()
        existing = folder/'existing.pdf'; existing.write_bytes(b'KEEP')
        merge.output.set(str(existing)); merge.start()
        assert existing.read_bytes() == b'KEEP' and not app.busy
        os.chdir(folder)
        try:
            merge.output.set('รวมเอกสาร.pdf')
            merge.changed()
            assert app.show_home()
            assert app.show_tool('pdf-png')
            assert app.show_tool('merge')
            assert merge.files == [b, a] and merge.output.get() == 'รวมเอกสาร.pdf'
            pump(root)
            capture(root, 'merge-ready.png')
            merge.start()
            assert app.busy and merge.busy
            assert not app.show_home() and not app.show_tool('pdf-png')
            merge.move_file(a, -1); merge.clear_files(); merge.add_paths([bad])
            assert merge.files == [b, a]
            merge.start()
            wait_for_merge(root, app)
            assert merge.destination == folder/'รวมเอกสาร.pdf'
            assert merge.open_button.cget('state') == 'normal'
            capture(root, 'merge-success.png')
            with pymupdf.open(merge.destination) as result:
                assert result.page_count == 3
                assert [page.get_text().splitlines()[0] for page in result] == ['Guide page 1', 'Brief page 1', 'Brief page 2']
            # A removed source fails without partial output and unlocks the UI.
            gone = folder/'gone.pdf'; make_pdf(gone, ['Gone'])
            merge.clear_files(); merge.add_paths([a, gone]); gone.unlink()
            merge.output.set('failed.pdf'); merge.start()
            wait_for_merge(root, app)
            assert not (folder/'failed.pdf').exists()
            assert 'gone.pdf' in merge.status.get()
            assert merge.start_button.cget('state') == 'normal'
            merge.clear_files(); merge.add_paths([b, a]); merge.output.set('รวมเอกสาร.pdf'); merge.changed()
            root.geometry('920x700+40+40'); pump(root)
            capture(root, 'merge-compact.png')
            assert not callback_errors, callback_errors
            dispose(root)
            ctk.set_widget_scaling(1.25); ctk.set_window_scaling(1.25)
            root = ctk.CTk()
            root.report_callback_exception = lambda kind, value, trace: callback_errors.append(str(value))
            app = App(root); app.show_tool('merge'); app.merge.add_paths([b, a])
            root.geometry('1080x780+10+10'); pump(root)
            capture(root, 'merge-scaled.png')
            assert not callback_errors, callback_errors
            dispose(root)
            renderer = shutil.which('pdftoppm')
            assert renderer, 'Poppler pdftoppm is required for independent rendering verification'
            for source, label in [(b, 'before-b'), (a, 'before-a'), (folder/'รวมเอกสาร.pdf', 'after')]:
                subprocess.run([renderer, '-r', '72', '-png', str(source), str(folder/label)], check=True, capture_output=True)
            before = sorted(folder.glob('before-b-*.png')) + sorted(folder.glob('before-a-*.png'))
            after = sorted(folder.glob('after-*.png'))
            assert len(before) == len(after) == 3
            for source, result in zip(before, after):
                with Image.open(source) as source_image, Image.open(result) as result_image:
                    assert source_image.size == result_image.size
                    assert ImageChops.difference(source_image, result_image).getbbox() is None
        finally:
            os.chdir(original_cwd)
    report = {'passed': True, 'merged_pages': 3, 'ready_tools': 2,
              'checks': ['adding/reordering/removing files', 'invalid PDF rejected', 'input/output overwrite guard',
                         'retained merge state across tools', 'busy navigation/reorder/start guards',
                         'successful merge and file order', 'missing source recovery', 'Poppler pixel equivalence',
                         '920x700 layout', '125% scaling', 'no callback errors']}
    (ROOT/'docs/merge-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
