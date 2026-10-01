"""Exercise the native Windows TkDnD entrypoints, including child hit targets."""
import ctypes
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import customtkinter as ctk
import pymupdf
from PIL import ImageGrab
from pdf_lover.app import App
from verify_merge_cards import pump


def enter(root, target, paths):
    data = root.tk.call('list', *(str(path) for path in paths))
    action = root.tk.call('tkdnd::olednd::HandleDragEnter', target._w,
                         ('CF_HDROP',), ('copy',), (),
                         target.winfo_rootx() + 5, target.winfo_rooty() + 5,
                         ('CF_HDROP',), data)
    return data, action


def drop(root, target, paths):
    data, action = enter(root, target, paths)
    if action == 'refuse_drop':
        root.tk.call('tkdnd::olednd::HandleDragLeave', target._w)
        return action
    result = root.tk.call('tkdnd::olednd::HandleDrop', target._w, (),
                          target.winfo_rootx() + 5, target.winfo_rooty() + 5,
                          'CF_HDROP', data)
    root.tk.call('tkdnd::olednd::HandleDragLeave', target._w)
    pump(root, 0.12)
    return result


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lover-file-drop-') as directory:
        folder = Path(directory)
        paths = [folder / 'เอกสาร ไทย {ฉบับแรก}.PDF', folder / 'Agreement [signed] 2026.pdf',
                 folder / 'Résumé budget.pdf']
        for index, path in enumerate(paths):
            with pymupdf.open() as doc:
                page = doc.new_page()
                page.insert_text((30, 30), f'DOCUMENT {index}')
                doc.save(path)
        other = folder / 'notes.txt'
        other.write_text('not a PDF', encoding='utf-8')
        corrupt = folder / 'broken.pdf'
        corrupt.write_bytes(b'not a PDF')
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root)
        root.geometry('1080x900+40+40')
        pump(root, 0.25)
        assert app.file_drop.version
        assert drop(root, app.home.search_entry._entry, paths[:2]) == 'copy'
        assert app.route == 'merge' and app.merge.files == paths[:2]
        assert drop(root, app.merge.cards.canvas, [paths[0], paths[2], other, folder]) == 'copy'
        assert app.merge.files == paths, app.merge.files
        assert app.file_drop.pending == []
        assert drop(root, app.merge.output_entry._entry, [corrupt]) == 'copy'
        assert app.merge.files == paths and 'เพิ่มบางไฟล์ไม่ได้' in app.merge.status.get()
        before = list(app.merge.files)
        assert drop(root, app.merge.cards.canvas, [other, folder, folder/'missing.pdf']) == 'refuse_drop'
        assert app.merge.files == before
        app.show_tool('pdf-png')
        pump(root)
        assert drop(root, app.png.output_entry._entry, paths[:2]) == 'copy'
        assert app.png.files == paths[:2] and app.merge.files == paths
        assert drop(root, app.png.add_button._canvas, paths[:2]) == 'copy'
        assert app.png.files == paths[:2]
        app.busy = True
        assert drop(root, app.png.output_entry._entry, [paths[2]]) == 'refuse_drop'
        assert app.png.files == paths[:2]
        app.busy = False
        app.show_tool('merge')
        app.merge.changed()
        app.merge.output.set('รวมเอกสาร.pdf')
        pump(root)
        _, action = enter(root, app.merge.cards.canvas, [paths[0]])
        assert action == 'copy' and app.file_drop.banner.winfo_ismapped()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ImageGrab.grab(window=hwnd).save(ROOT/'docs/images/file-drop.png')
        root.tk.call('tkdnd::olednd::HandleDragLeave', app.merge.cards.canvas._w)
        assert not app.file_drop.banner.winfo_ismapped()
        assert not errors, errors
        app.close()
        assert app.file_drop.closed and app.file_drop.pending_timer is None
    report = {'passed': True, 'native_library': 'tkdnd',
              'checks': ['Windows OLE Tcl enter/drop/leave callbacks',
                         'child Canvas and entry hit targets resolve to root',
                         'home opens merge', 'multiple files preserve incoming order',
                         'Thai, Unicode, spaces and braces in filenames',
                         'case-insensitive PDF extension', 'duplicate suppression',
                         'mixed unsupported files and folders', 'missing and corrupt files',
                         'PNG and merge queues remain independent', 'busy drop refusal',
                         'hover feedback and cancellation', 'cleanup without callback errors']}
    (ROOT/'docs/file-drop-verification.json').write_text(json.dumps(report, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
