"""Native Canvas load check: 100 PDFs, fast pointer input and live Tk heartbeat."""
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import customtkinter as ctk
import pymupdf
from pdf_to_png import App
from verify_merge_cards import pointer, pump


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lover-canvas-load-') as folder:
        paths = []
        for index in range(100):
            path = Path(folder)/f'Document {index:03}.pdf'
            with pymupdf.open() as doc:
                page = doc.new_page()
                page.insert_text((30, 30), f'DOCUMENT {index:03}')
                doc.save(path)
            paths.append(path)
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root)
        app.show_tool('merge')
        root.geometry('1080x900+40+40')
        app.merge.add_paths(paths)
        pump(root, 0.35)
        grid = app.merge.cards
        canvas = grid.canvas
        assert len(grid.visible) < 30 and len(canvas.find_all()) < 250
        source = paths[0]
        pointer(canvas, '<ButtonPress-1>', *grid.card_center(source))
        target_x, target_y = grid.card_center(paths[2], True)
        before = grid.paints
        start = time.perf_counter()
        for _ in range(1000):
            pointer(canvas, '<B1-Motion>', target_x, target_y)
        dispatch_ms = (time.perf_counter() - start) * 1000
        assert grid.frame_timer and grid.drag['pointer'] == (int(target_x), int(target_y))
        pump(root, 0.08)
        assert grid.ghost is not None
        assert grid.paints - before <= 6, grid.paints - before
        before = grid.paints
        for offset in range(20):
            grid.drag['pointer'] = (target_x + offset / 4, target_y)
            grid._target()
        assert grid.paints == before, 'Same drop position repainted cards'
        frame_times = []
        max_paints = 0
        for index in range(120):
            target = paths[1 + index % (grid.columns - 1)]
            grid.drag['pointer'] = grid.card_center(target, bool(index % 2))
            before = grid.paints
            start = time.perf_counter()
            grid._drag_frame()
            root.update_idletasks()
            frame_times.append((time.perf_counter() - start) * 1000)
            max_paints = max(max_paints, grid.paints - before)
        assert max_paints <= 3, max_paints
        heartbeat = []
        live = True
        def beat():
            if live:
                heartbeat.append(time.perf_counter())
                root.after(10, beat)
        beat()
        cache_size = len(grid.cache)
        deadline = time.perf_counter() + 0.6
        while time.perf_counter() < deadline:
            pointer(canvas, '<B1-Motion>', target_x, target_y)
            root.update()
            time.sleep(0.005)
        live = False
        assert len(heartbeat) >= 10, heartbeat
        assert len(grid.cache) == cache_size, 'Images were applied during drag'
        max_gap_ms = max(b - a for a, b in zip(heartbeat, heartbeat[1:])) * 1000
        assert max_gap_ms < 250 and max(frame_times) < 250
        pointer(canvas, '<ButtonRelease-1>', target_x, target_y)
        assert app.merge.files[2] == source and grid.drag is None and grid.grab_current() is None
        source = app.merge.files[2]
        pointer(canvas, '<ButtonPress-1>', *grid.card_center(source))
        x, y = grid.card_center(app.merge.files[0])
        pointer(canvas, '<B1-Motion>', x, y)
        pointer(canvas, '<ButtonRelease-1>', x, y)
        assert app.merge.files[0] == source and grid.frame_timer is None
        pump(root, 0.35)
        assert len(grid.cache) > cache_size, 'Preview display did not resume'
        canvas.yview_moveto(0)
        pump(root, 0.08)
        source = app.merge.files[0]
        pointer(canvas, '<ButtonPress-1>', *grid.card_center(source))
        edge_x = canvas.winfo_rootx() + 50
        edge_y = canvas.winfo_rooty() + canvas.winfo_height() - 8
        pointer(canvas, '<B1-Motion>', edge_x, edge_y)
        scroll_heartbeats = []
        live = True
        def scroll_beat():
            if live:
                scroll_heartbeats.append(time.perf_counter())
                root.after(10, scroll_beat)
        scroll_beat()
        deadline = time.perf_counter() + 0.8
        while time.perf_counter() < deadline:
            root.update()
            time.sleep(0.005)
        live = False
        assert canvas.yview()[0] > 0
        assert len(scroll_heartbeats) >= 15
        max_scroll_gap_ms = max(b - a for a, b in zip(scroll_heartbeats, scroll_heartbeats[1:])) * 1000
        assert max_scroll_gap_ms < 250
        assert len(grid.visible) < 30 and len(canvas.find_all()) < 250
        pointer(canvas, '<ButtonRelease-1>', edge_x, edge_y)
        assert app.merge.files.index(source) > 0
        canvas.yview_moveto(1)
        pump(root, 0.08)
        assert len(grid.visible) < 30 and len(canvas.find_all()) < 250
        assert grid.pending, 'Expected new visible thumbnails'
        worker_process = grid.worker.process
        assert worker_process and worker_process.is_alive()
        worker_process.terminate()
        worker_process.join(timeout=1)
        pump(root, 0.25)
        assert not grid.pending and grid.worker.failed and grid.worker.process is None
        assert not errors, errors
        root.destroy()
    report = {'passed': True, 'cards': 100, 'burst_motion_events': 1000,
              'burst_dispatch_ms': round(dispatch_ms, 2), 'render_frames': len(frame_times),
              'mean_frame_ms': round(sum(frame_times)/len(frame_times), 2),
              'max_frame_ms': round(max(frame_times), 2),
              'max_card_paints_per_frame': max_paints,
              'max_heartbeat_gap_ms': round(max_gap_ms, 2),
              'max_scroll_heartbeat_gap_ms': round(max_scroll_gap_ms, 2),
              'checks': ['single Canvas viewport', 'at most 30 visible cards',
                         'latest pointer wins', 'same drop position does not repaint',
                         'event loop heartbeat during drag and edge scrolling', 'quick release',
                         'preview pause/resume and worker recovery', 'no callback errors']}
    (ROOT/'docs/drag-performance-1.1.3.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
