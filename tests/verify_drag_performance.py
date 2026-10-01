"""100-card drag load: real Tk events, bounded paints and event-loop heartbeat."""
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
from verify_merge_cards import center, pointer, pump


def main():
    errors = []
    with tempfile.TemporaryDirectory(prefix='lover-drag-load-') as folder:
        paths = []
        for index in range(100):
            path = Path(folder) / f'Document {index:03}.pdf'
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
        pump(root, 0.3)
        grid = app.merge.cards
        counts = {path: 0 for path in paths}
        for path, card in grid.cards.items():
            configure = card.configure
            def counted(*args, _path=path, _configure=configure, **kwargs):
                counts[_path] += 1
                return _configure(*args, **kwargs)
            card.configure = counted
        widget = grid.previews[paths[0]]._label
        pointer(widget, '<ButtonPress-1>', *center(grid.cards[paths[0]]))
        target_x, target_y = center(grid.cards[paths[2]], True)
        start = time.perf_counter()
        for _ in range(1000):
            pointer(grid.cards[paths[0]]._canvas, '<B1-Motion>', target_x, target_y)
        dispatch_ms = (time.perf_counter() - start) * 1000
        assert grid.frame_timer is not None and grid.drag['pointer'] == (int(target_x), int(target_y))
        pump(root, 0.08)
        assert grid.ghost is not None
        assert sum(counts.values()) <= 6, counts
        # Same-slot frames must not repaint a single card.
        paints_before = sum(counts.values())
        for offset in range(20):
            grid.drag['pointer'] = (target_x + offset / 4, target_y)
            grid._target()
        assert sum(counts.values()) == paints_before
        frame_times = []
        max_paints = 0
        for index in range(120):
            target = paths[1 + index % (grid.columns - 1)]
            grid.drag['pointer'] = center(grid.cards[target], bool(index % 2))
            before = sum(counts.values())
            start = time.perf_counter()
            grid._drag_frame()
            root.update_idletasks()
            frame_times.append((time.perf_counter() - start) * 1000)
            max_paints = max(max_paints, sum(counts.values()) - before)
        assert max_paints <= 3, max_paints
        # Give the native loop time to run while motion keeps arriving.
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
            pointer(grid.cards[paths[0]]._canvas, '<B1-Motion>', target_x, target_y)
            root.update()
            time.sleep(0.005)
        live = False
        assert len(heartbeat) >= 10, heartbeat
        assert len(grid.cache) == cache_size, 'Thumbnail application interrupted dragging'
        max_gap_ms = max(b - a for a, b in zip(heartbeat, heartbeat[1:])) * 1000
        # Generous limits detect freezes, not differences between machines.
        assert max_gap_ms < 250, max_gap_ms
        assert max(frame_times) < 250, max(frame_times)
        pointer(grid.cards[paths[0]]._canvas, '<ButtonRelease-1>', target_x, target_y)
        assert app.merge.files[2] == paths[0]
        assert grid.drag is None and grid.grab_current() is None
        # A fast release before a scheduled frame still uses the release point.
        source = app.merge.files[2]
        pointer(grid.cards[source]._canvas, '<ButtonPress-1>', *center(grid.cards[source]))
        x, y = center(grid.cards[app.merge.files[0]])
        pointer(grid.cards[source]._canvas, '<B1-Motion>', x, y)
        pointer(grid.cards[source]._canvas, '<ButtonRelease-1>', x, y)
        assert app.merge.files[0] == source and grid.frame_timer is None
        pump(root, 0.3)
        assert len(grid.cache) > cache_size, 'Previews did not resume after release'
        assert not errors, errors
        worker_process = grid.worker.process
        assert worker_process is not None and worker_process.is_alive()
        assert grid.pending
        worker_process.terminate()
        worker_process.join(timeout=1)
        pump(root, 0.3)
        assert not grid.pending and grid.worker.failed
        assert grid.worker.process is None
        assert not errors, errors
        root.destroy()
        assert grid.worker.process is None
    report = {'passed': True, 'cards': 100, 'burst_motion_events': 1000,
              'burst_dispatch_ms': round(dispatch_ms, 2), 'render_frames': len(frame_times),
              'mean_frame_ms': round(sum(frame_times) / len(frame_times), 2),
              'max_frame_ms': round(max(frame_times), 2), 'max_card_paints_per_frame': max_paints,
              'max_heartbeat_gap_ms': round(max_gap_ms, 2),
              'checks': ['latest-pointer frame coalescing', 'no same-slot card repaint',
                         'constant work with 100 cards', 'event loop heartbeat during dragging',
                         'thumbnail UI updates paused then resumed', 'correct quick release',
                         'worker crash recovery and lifecycle', 'no callback errors']}
    (ROOT/'docs/drag-performance-1.1.1.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
