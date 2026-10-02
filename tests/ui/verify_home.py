"""Exercise discovery, planned-tool safety, navigation and real PNG conversion."""
import ctypes
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / 'build-verification' / 'ui'
sys.path.insert(0, str(ROOT))
import customtkinter as ctk
import pymupdf
from PIL import ImageGrab, Image
from pdf_lover.app import App
from pdf_lover.catalog import TOOLS, CATEGORIES, find_tools


def pump(root, seconds=0.25):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def capture(root, name):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    root.update()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ImageGrab.grab(window=hwnd).save(ARTIFACTS / name)


def dispose(root):
    for timer in root.tk.call('after', 'info'):
        root.after_cancel(timer)
    root.destroy()


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    assert len({tool.id for tool in TOOLS}) == len(TOOLS) == 34
    assert len({category.id for category in CATEGORIES}) == 7
    assert all(tool.category in {item.id for item in CATEGORIES} for tool in TOOLS)
    assert [tool.id for tool in find_tools(ready_only=True)] == ['pdf-png', 'merge', 'split', 'delete-pages', 'extract-pages', 'rotate']
    assert {tool.id for tool in find_tools('excel')} == {'pdf-excel', 'excel-pdf'}
    assert {tool.id for tool in find_tools(' PPTX ')} == {'pdf-ppt', 'ppt-pdf'}
    assert [tool.id for tool in find_tools('รวม PDF', category='organize')] == ['merge']
    assert not find_tools('no-matching-tool')
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    root = ctk.CTk()
    errors = []
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    app = App(root)
    assert not app.views, 'Home eagerly constructed feature pages'
    assert app.png is app.png and set(app.views) == {'pdf-png'}
    assert app.merge is app.merge and set(app.views) == {'pdf-png', 'merge'}
    root.geometry('1080x780+40+40')
    root.resizable(False, False)
    pump(root, 0.6)
    timers = root.tk.call('after', 'info')
    for _ in range(50):
        for page in app.views.values():
            page.process_events()
    assert root.tk.call('after', 'info') == timers, 'Feature polling created extra timer chains'
    assert app.route == 'home' and app.home.winfo_ismapped()
    assert not app.png.winfo_ismapped()
    capture(root, 'home-default.png')
    app.home.select_category('security')
    assert len(app.home.visible_tools) == 5
    assert all(tool.category == 'security' for tool in app.home.visible_tools)
    capture(root, 'home-security.png')
    assert app.show_tool('protect') is False
    pump(root)
    assert app.route == 'home' and app.home.detail_window.winfo_exists()
    dialog = app.home.detail_window
    hwnd = ctypes.windll.user32.GetParent(dialog.winfo_id())
    ImageGrab.grab(window=hwnd).save(ARTIFACTS / 'home-planned.png')
    app.home.close_detail()
    app.home.reset_filters()
    app.home.query.set('Excel')
    pump(root)
    assert {tool.id for tool in app.home.visible_tools} == {'excel-pdf', 'pdf-excel'}
    capture(root, 'home-search.png')
    app.home.query.set('no-matching-tool')
    pump(root)
    assert not app.home.visible_tools
    capture(root, 'home-empty.png')
    app.home.reset_filters()
    app.home.toggle_ready()
    assert [tool.id for tool in app.home.visible_tools] == ['pdf-png', 'merge', 'split', 'delete-pages', 'extract-pages', 'rotate']
    assert not app.show_tool('unknown')
    with tempfile.TemporaryDirectory(prefix='pdf-lover-navigation-') as sandbox:
        folder = Path(sandbox)
        source = folder / 'ตัวอย่าง.pdf'
        with pymupdf.open() as document:
            for _ in range(2):
                document.new_page(width=144, height=72)
            document.save(source)
        assert app.show_tool('pdf-png')
        pump(root)
        assert app.png.winfo_ismapped() and not app.home.winfo_ismapped()
        app.png.add_paths([source])
        app.png.output.set(str(folder/'output'))
        app.png.dpi.set('150')
        assert app.show_home()
        assert app.show_tool('pdf-png')
        assert app.png.files == [source] and app.png.dpi.get() == '150'
        app.png.start()
        assert app.busy and not app.show_home()
        deadline = time.monotonic() + 15
        while app.busy and time.monotonic() < deadline:
            pump(root, 0.1)
        assert not app.busy and not app.png.errors
        outputs = sorted((folder/'output'/source.stem).glob('*.png'))
        assert len(outputs) == 2
        with Image.open(outputs[0]) as image:
            assert image.size == (300, 150)
        capture(root, 'home-converter-success.png')
        assert app.show_home()
        app.home.reset_filters()
    root.geometry('920x700+40+40')
    pump(root)
    capture(root, 'home-compact.png')
    root.geometry('1440x900+10+10')
    pump(root)
    assert app.home.columns == 3
    capture(root, 'home-wide.png')
    assert not errors, errors
    dispose(root)
    ctk.set_widget_scaling(1.25)
    ctk.set_window_scaling(1.25)
    root = ctk.CTk()
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    app = App(root)
    root.geometry('1080x780+10+10')
    pump(root, 0.6)
    capture(root, 'home-scaled.png')
    assert not errors, errors
    dispose(root)
    report = {'passed': True, 'tools': len(TOOLS), 'categories': len(CATEGORIES), 'ready': 6,
              'checks': ['lazy page creation and retained instances', 'shell owns the only event polling timer', 'Thai/English search', 'category/status filtering', 'planned details', 'empty state',
                         'queue/settings retained', 'busy navigation guard', 'real two-page PNG conversion',
                         '920/1080/1440 widths', '100%/125% scaling', 'no callback errors']}
    (ARTIFACTS/'home-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
