"""Real Tk pointer/key events, responsive layout and ordered merge regression.

Run on Windows: python tests/verify_merge_cards.py
"""
import ctypes
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import customtkinter as ctk
import pymupdf
from PIL import ImageGrab
from pdf_to_png import App


def pump(root, seconds=0.25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def pointer(widget, event, x, y):
    widget.event_generate(event, x=int(x - widget.winfo_rootx()), y=int(y - widget.winfo_rooty()),
                          rootx=int(x), rooty=int(y))


def center(card, after=False):
    return card.winfo_rootx() + card.winfo_width() * (0.8 if after else 0.2), card.winfo_rooty() + 70


def drag(root, grid, source, target, after=False):
    widget = grid.previews[source]._label
    x, y = center(grid.cards[source])
    pointer(widget, '<ButtonPress-1>', x, y)
    assert grid.drag and grid.drag['path'] == source
    x, y = center(grid.cards[target], after)
    pointer(grid.cards[source]._canvas, '<B1-Motion>', x, y)
    pump(root, 0.08)
    assert grid.drag['active'] and grid.ghost, {'drag': grid.drag, 'ghost': str(grid.ghost), 'timer': grid.frame_timer}
    pointer(grid.cards[source]._canvas, '<ButtonRelease-1>', x, y)
    pump(root, 0.05)
    assert grid.drag is None and grid.ghost is None and grid.grab_current() is None


def main():
    errors = []
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    with tempfile.TemporaryDirectory(prefix='lover-cards-') as folder:
        folder = Path(folder)
        paths = []
        titles = ['Project Brief', 'Quotation', 'Agreement', 'Invoice', 'Delivery Note', 'Receipt']
        for index in range(30):
            path = folder / (titles[index] + '.pdf' if index < 6 else f'Document {index + 1:02}.pdf')
            with pymupdf.open() as doc:
                page = doc.new_page(width=300, height=400)
                page.draw_rect((20, 22, 280, 86), color=None, fill=(0.055, 0.27, 0.6))
                page.insert_text((34, 50), f'DOCUMENT {index + 1:02}', color=(1, 1, 1), fontsize=16)
                page.insert_text((34, 70), 'PDF LoveR / sample document', color=(1, 1, 1), fontsize=8)
                page.insert_text((24, 118), titles[index] if index < 6 else 'Supporting document', fontsize=14)
                for line in range(8):
                    page.draw_line((24, 150 + line * 20), (276 if line % 3 else 220, 150 + line * 20), color=(0.7, 0.74, 0.8))
                doc.save(path)
            paths.append(path)
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root)
        app.show_tool('merge')
        root.geometry('1080x900+40+40')
        page, grid = app.merge, app.merge.cards
        page.add_paths(paths[:6])
        page.output.set('รวมเอกสาร.pdf')
        pump(root, 0.8)
        assert grid.columns >= 4
        # Pointer press comes from the real preview label, not a helper callback.
        drag(root, grid, paths[0], paths[2], after=True)
        assert page.files[:3] == [paths[1], paths[2], paths[0]]
        drag(root, grid, paths[0], paths[1])
        assert page.files == paths[:6]
        # Row boundary, including insertion after the last card in a partial row.
        last = grid.cards[paths[5]]
        grid._parent_canvas.yview_moveto(0)
        pump(root)
        drag(root, grid, paths[0], paths[5], after=True)
        assert page.files == paths[1:6] + [paths[0]]
        # Keyboard ordering uses the same model and retains focus.
        card = grid.cards[paths[0]]
        card._canvas.focus_force()
        card._canvas.event_generate('<Left>')
        assert page.files[-2:] == [paths[0], paths[5]]
        # Escape and outside release leave order unchanged, and release capture.
        before = list(page.files)
        widget = grid.cards[paths[1]]._canvas
        x, y = center(grid.cards[paths[1]])
        pointer(widget, '<ButtonPress-1>', x, y)
        pointer(widget, '<B1-Motion>', x + 50, y)
        widget.event_generate('<Escape>')
        assert grid.drag is None and page.files == before
        pointer(widget, '<ButtonPress-1>', x, y)
        pointer(widget, '<B1-Motion>', root.winfo_rootx() + 5, root.winfo_rooty() + 5)
        pointer(widget, '<ButtonRelease-1>', root.winfo_rootx() + 5, root.winfo_rooty() + 5)
        assert page.files == before and grid.drag is None
        # Click without a drag does not change the order; remove stays separate.
        pointer(widget, '<ButtonPress-1>', x, y)
        pointer(widget, '<ButtonRelease-1>', x, y)
        assert page.files == before
        pointer(widget, '<ButtonPress-1>', x, y)
        pointer(widget, '<B1-Motion>', x + 50, y)
        app.show_home()
        pump(root)
        assert grid.drag is None and grid.grab_current() is None
        app.show_tool('merge')
        pump(root)
        grid.cards[paths[5]].close.invoke()
        assert paths[5] not in page.files
        page.add_paths(paths[5:])
        pump(root, 0.6)
        assert len(grid.cards) == 30
        grid._parent_canvas.yview_moveto(0)
        pump(root)
        source = page.files[0]
        widget = grid.cards[source]._canvas
        x, y = center(grid.cards[source])
        pointer(widget, '<ButtonPress-1>', x, y)
        canvas = grid._parent_canvas
        edge_x, edge_y = canvas.winfo_rootx() + 50, canvas.winfo_rooty() + canvas.winfo_height() - 8
        pointer(widget, '<B1-Motion>', edge_x, edge_y)
        pump(root, 0.7)
        assert canvas.yview()[0] > 0, canvas.yview()
        pointer(widget, '<ButtonRelease-1>', edge_x, edge_y)
        assert page.files.index(source) > 0
        # Busy controls, drag blocked and no changes from input while processing.
        app.busy = page.busy = True
        page.render_files()
        before = list(page.files)
        widget = grid.cards[before[0]]._canvas
        pointer(widget, '<ButtonPress-1>', *center(grid.cards[before[0]]))
        grid.cards[before[0]].close.invoke()
        assert grid.drag is None and page.files == before
        app.busy = page.busy = False
        page.render_files()
        # Rendered layout widths stay inside the viewport after resizing/scaling.
        for width, height, scaling in [(920, 700, 1), (1440, 900, 1), (1080, 780, 1.25)]:
            ctk.set_widget_scaling(scaling)
            ctk.set_window_scaling(scaling)
            root.geometry(f'{width}x{height}+10+10')
            pump(root, 0.4)
            for card in grid.cards.values():
                assert card.winfo_x() + card.winfo_width() <= grid.winfo_width() + 2
            end_of_row = grid.cards[page.files[grid.columns - 1]]
            assert end_of_row.winfo_x() + end_of_row.winfo_width() >= grid.winfo_width() - 20
            assert grid._parent_canvas.xview() == (0.0, 1.0)
        ctk.set_widget_scaling(1)
        ctk.set_window_scaling(1)
        root.geometry('1080x900+40+40')
        page.clear_files()
        page.add_paths(paths[:6])
        pump(root, 0.6)
        grid._parent_canvas.yview_moveto(0)
        pump(root)
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ImageGrab.grab(window=hwnd).save(ROOT/'docs/images/merge-cards.png')
        drag(root, grid, paths[0], paths[2], after=True)
        expected = list(page.files)
        page.output.set(str(folder/'ordered.pdf'))
        page.start()
        deadline = time.monotonic() + 20
        while app.busy and time.monotonic() < deadline:
            pump(root, 0.1)
        assert not app.busy and page.destination
        with pymupdf.open(page.destination) as result:
            assert result.page_count == 6
            assert [p.get_text().splitlines()[0] for p in result] == [f'DOCUMENT {paths.index(p) + 1:02}' for p in expected]
        assert not errors, errors
        root.destroy()
    report = {'passed': True, 'files_tested': 30, 'merged_pages': 6,
              'checks': ['real Tk drag events from preview label', 'left/right and cross-row drops',
                         'keyboard focus and reorder', 'escape/outside/navigation cancellation', 'remove button',
                         'edge autoscroll', 'busy guard', '920/1080/1440 widths', '125% scaling',
                         'preview rendering', 'merged order follows dropped cards', 'no callback errors']}
    (ROOT/'docs/merge-cards-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
