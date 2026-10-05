"""Native Canvas merge interaction and real PDF output checks on Windows."""
import ctypes
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import customtkinter as ctk
import pymupdf
from PIL import ImageGrab
from pdf_lover.app import App


def pump(root, seconds=0.18):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)


def pointer(canvas, event, x, y):
    canvas.event_generate(event, x=int(x - canvas.winfo_rootx()), y=int(y - canvas.winfo_rooty()),
                          rootx=int(x), rooty=int(y))


def wait_for(root, predicate, timeout=2):
    """Wait for a real frame, rather than assuming Tk paints in a fixed sleep."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        pump(root, 0.02)
    assert predicate(), 'Canvas did not reach the expected visual state'


def drag(root, grid, source, target, after=False, wait=True):
    canvas = grid.canvas
    x, y = grid.card_center(source)
    pointer(canvas, '<ButtonPress-1>', x, y)
    assert grid.drag and grid.drag['path'] == source
    x, y = grid.card_center(target, after)
    pointer(canvas, '<B1-Motion>', x, y)
    if wait:
        wait_for(root, lambda: grid.ghost is not None)
        assert grid.ghost is not None
    pointer(canvas, '<ButtonRelease-1>', x, y)
    assert grid.drag is None and grid.ghost is None and grid.grab_current() is None


def main():
    errors = []
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    with tempfile.TemporaryDirectory(prefix='lover-canvas-') as folder:
        folder = Path(folder)
        names = ['Project Brief', 'Quotation', 'Agreement', 'Invoice', 'Delivery Note', 'Receipt']
        paths = []
        for index in range(30):
            path = folder/(names[index] + '.pdf' if index < 6 else f'Document {index + 1:02}.pdf')
            with pymupdf.open() as doc:
                page = doc.new_page(width=300, height=400)
                page.draw_rect((20, 22, 280, 86), color=None, fill=(0.055, 0.27, 0.6))
                page.insert_text((34, 50), f'DOCUMENT {index + 1:02}', color=(1, 1, 1), fontsize=16)
                page.insert_text((34, 70), 'PDF LoveR / sample document', color=(1, 1, 1), fontsize=8)
                page.insert_text((24, 118), names[index] if index < 6 else 'Supporting document', fontsize=14)
                for line in range(8):
                    page.draw_line((24, 150 + line * 20), (276, 150 + line * 20), color=(0.7, 0.74, 0.8))
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
        pump(root, 0.7)
        grid.canvas.focus_force();pump(root, 0.05)
        assert grid.columns >= 4 and 0 < len(grid.visible) <= 15
        sx, sy = grid.card_center(paths[0])
        tx, ty = grid.card_center(paths[2], after=True)
        # Desktop focus can arrive late after earlier native suites close.
        # Retry the gesture only if focus loss cancelled it; still require real painted state.
        for attempt in range(3):
            grid.canvas.focus_force();pump(root, 0.15)
            pointer(grid.canvas, '<ButtonPress-1>', sx, sy)
            pointer(grid.canvas, '<B1-Motion>', tx, ty)
            pump(root, 0.3)
            if grid.drag is not None:
                break
        wait_for(root, lambda: grid.ghost is not None and grid.marker is not None
                 and grid.canvas.coords(grid.marker)[3] - grid.canvas.coords(grid.marker)[1] > 100 * grid.scaling)
        assert grid.ghost is not None and grid.marker is not None
        marker_height = grid.canvas.coords(grid.marker)[3] - grid.canvas.coords(grid.marker)[1]
        assert marker_height > 100 * grid.scaling, marker_height
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        ImageGrab.grab(window=hwnd).save(ROOT/'docs/images/merge-dragging.png')
        pointer(grid.canvas, '<ButtonRelease-1>', tx, ty)
        assert grid.marker is None and grid.ghost is None
        page.reorder_file(paths[0], 0)
        pump(root, 0.1)
        grid.motion_enabled = False
        sx, sy = grid.card_center(paths[0])
        tx, ty = grid.card_center(paths[2], after=True)
        pointer(grid.canvas, '<ButtonPress-1>', sx, sy)
        pointer(grid.canvas, '<B1-Motion>', tx, ty)
        wait_for(root, lambda: grid.marker is not None)
        assert grid.marker is not None
        reduced_height = grid.canvas.coords(grid.marker)[3] - grid.canvas.coords(grid.marker)[1]
        assert reduced_height == round(grid.HEIGHT * grid.scaling) - round(20 * grid.scaling)
        grid.cancel_drag()
        grid.motion_enabled = True
        drag(root, grid, paths[0], paths[2], after=True)
        assert page.files[:3] == [paths[1], paths[2], paths[0]]
        drag(root, grid, paths[0], paths[1])
        assert page.files == paths[:6]
        drag(root, grid, paths[0], paths[5], after=True)
        assert page.files == paths[1:6] + [paths[0]]
        grid.canvas.focus_force()
        grid.selected = paths[0]
        grid.canvas.event_generate('<Left>')
        assert page.files[-2:] == [paths[0], paths[5]]
        before = list(page.files)
        canvas = grid.canvas
        x, y = grid.card_center(paths[1])
        pointer(canvas, '<ButtonPress-1>', x, y)
        pointer(canvas, '<B1-Motion>', x + 50, y)
        canvas.event_generate('<Escape>')
        assert grid.drag is None and page.files == before
        pointer(canvas, '<ButtonPress-1>', x, y)
        pointer(canvas, '<B1-Motion>', root.winfo_rootx() + 5, root.winfo_rooty() + 5)
        pointer(canvas, '<ButtonRelease-1>', root.winfo_rootx() + 5, root.winfo_rooty() + 5)
        assert page.files == before and grid.drag is None
        pointer(canvas, '<ButtonPress-1>', x, y)
        pointer(canvas, '<ButtonRelease-1>', x, y)
        assert page.files == before
        pointer(canvas, '<ButtonPress-1>', x, y)
        pointer(canvas, '<B1-Motion>', x + 50, y)
        app.show_home()
        pump(root)
        assert grid.drag is None and grid.grab_current() is None
        app.show_tool('merge')
        pump(root)
        x1, y1, x2, y2 = grid.card_bounds(paths[5])
        pointer(canvas, '<ButtonPress-1>', x2 - 22, y1 + 22)
        assert paths[5] not in page.files
        page.add_paths(paths[5:])
        pump(root, 0.35)
        assert len(page.files) == 30 and len(grid.visible) <= 30
        assert len(canvas.find_all()) <= 250, len(canvas.find_all())
        canvas.yview_moveto(0)
        pump(root)
        source = page.files[0]
        x, y = grid.card_center(source)
        pointer(canvas, '<ButtonPress-1>', x, y)
        edge_x, edge_y = canvas.winfo_rootx() + 50, canvas.winfo_rooty() + canvas.winfo_height() - 8
        pointer(canvas, '<B1-Motion>', edge_x, edge_y)
        pump(root, 0.7)
        assert canvas.yview()[0] > 0, canvas.yview()
        pointer(canvas, '<ButtonRelease-1>', edge_x, edge_y)
        assert page.files.index(source) > 0
        app.busy = page.busy = True
        page.render_files()
        before = list(page.files)
        pointer(canvas, '<ButtonPress-1>', *grid.card_center(before[0]))
        assert grid.drag is None and page.files == before
        app.busy = page.busy = False
        page.render_files()
        for width, height, scaling in [(920, 700, 1), (1440, 900, 1), (1080, 780, 1.25)]:
            ctk.set_widget_scaling(scaling)
            ctk.set_window_scaling(scaling)
            root.geometry(f'{width}x{height}+10+10')
            pump(root, 0.25)
            assert len(grid.visible) <= grid.columns * 5
            last = grid._bounds(grid.columns - 1)
            assert last[2] <= canvas.winfo_width() + 1
            assert last[2] >= canvas.winfo_width() - 35
            assert canvas.xview() == (0.0, 1.0)
        ctk.set_widget_scaling(1)
        ctk.set_window_scaling(1)
        root.geometry('1080x900+40+40')
        page.clear_files()
        page.add_paths(paths[:6])
        pump(root, 0.6)
        canvas.yview_moveto(0)
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
              'checks': ['native Canvas press/drag/drop', 'cross-row reorder', 'keyboard and remove',
                         'escape/outside/navigation cancellation', 'edge autoscroll', 'busy guard',
                         '920/1080/1440 widths', '125% scaling', 'visible-card virtualization',
                         'reduced motion uses final visual state',
                         'merged PDF follows card order', 'no callback errors']}
    (ROOT/'docs/merge-cards-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
