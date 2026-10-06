"""Native Shift/Ctrl/marquee selection, cancellation, output and pointer load."""
import hashlib
import json
import platform
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/ui')]
import customtkinter as ctk
import pymupdf
from pdf_lover.app import App
from pdf_lover.version import VERSION
from verify_merge import pump, capture
from verify_split import wait
from verify_selector import settled


def main():
    ctk.set_appearance_mode('light'); ctk.set_widget_scaling(1); ctk.set_window_scaling(1)
    errors = []
    with tempfile.TemporaryDirectory(prefix='lover-selection-') as tmp:
        folder = Path(tmp); small = folder / 'เลือกหน้า.pdf'; large = folder / '1000.pdf'
        for path, count in ((small, 8), (large, 1000)):
            with pymupdf.open() as doc:
                for number in range(1, count + 1):
                    doc.new_page().insert_text((72, 72), f'PAGE {number}', fontsize=24)
                doc.save(path)
        original = hashlib.sha256(small.read_bytes()).hexdigest()
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root); app.show_tool('extract-pages'); root.geometry('1840x1000+0+0'); pump(root)
        page = app.active_page; page.add_paths([small]); wait(root, app)
        s = page.selector; c = s.canvas; settled(root, s)

        def point(number):
            x1, y1, x2, y2 = s.visible[number]
            return int((x1 + x2) / 2), int((y1 + y2) / 2 - c.canvasy(0))

        def event(name, x, y, state=0):
            c.event_generate(name, x=int(x), y=int(y), state=state)

        def click(number, state=0):
            event('<ButtonPress-1>', *point(number), state)
            event('<ButtonRelease-1>', *point(number), state)

        def start_drag(state=0):
            event('<ButtonPress-1>', 1, 1, state)
            # A small box intersects pages 1,2,5,6 only.
            x = s.visible[2][2] - 10; y = s.visible[6][3] - 10 - c.canvasy(0)
            event('<B1-Motion>', x, y, state | 256)
            return x, y

        s.expression.set(''); click(2); click(6, 1); assert s.expression.get() == '2-6'
        click(4, 1); assert s.expression.get() == '2-4', 'Shift anchor moved or range did not shrink'
        click(8, 4); assert s.expression.get() == '2-4,8'
        click(6, 1); assert s.expression.get() == '6-8', 'Reverse range from Ctrl-click anchor'
        click(2, 5); assert s.expression.get() == '2-8'
        click(6, 4); assert s.expression.get() == '2-5,7-8'
        # Native focus can arrive asynchronously after a previous UI suite closes.
        deadline = time.monotonic() + 3
        while root.focus_get() != c and time.monotonic() < deadline:
            root.lift(); root.focus_force(); c.focus_force(); pump(root, .05)
        assert root.focus_get() == c, 'Canvas did not receive native keyboard focus'
        c.event_generate('<KeyPress>', keycode=65, state=4); assert s.expression.get() == '1-8', (s.expression.get(),s.enabled,s.editable,app.busy,root.focus_get())
        click(2); c.event_generate('<Shift-Right>'); assert s.expression.get() == '2-3'
        c.event_generate('<Shift-Right>'); assert s.expression.get() == '2-4'
        c.event_generate('<Shift-Left>'); assert s.expression.get() == '2-3'

        s.expression.set('8'); changes = []; changed = s.changed
        s.changed = lambda: (changes.append(s.expression.get()), changed())
        x, y = start_drag(); pump(root, .05)
        assert s.gesture['active'] and c.find_withtag('marquee') and s.expression.get() == '8'
        assert not changes, 'Drag rebuilt the PDF plan before release'
        capture(root, 'selector-marquee.png')
        event('<ButtonRelease-1>', x, y)
        assert s.expression.get() == '1-2,5-6' and changes == ['1-2,5-6']
        assert s.gesture is None and c.grab_current() is None and s.edge_timer is None
        assert page.plan.outputs[0].pages == (1, 2, 5, 6)
        x, y = start_drag(4); event('<ButtonRelease-1>', x, y, 4)
        assert s.expression.get() == ''  # Ctrl-marquee toggles those pages off.
        s.expression.set('8'); x, y = start_drag(1); event('<ButtonRelease-1>', x, y, 1)
        assert s.expression.get() == '1-2,5-6,8'
        start_drag(); c.event_generate('<Escape>'); pump(root, .1)
        assert s.expression.get() == '1-2,5-6,8' and s.gesture is None and c.grab_current() is None
        start_drag(); page.prefix_entry.focus_set(); pump(root, .1)
        assert s.gesture is None and c.grab_current() is None and s.expression.get() == '1-2,5-6,8'
        s.expression.set('8-1'); x, y = start_drag(); event('<ButtonRelease-1>', x, y)
        assert s.expression.get() == '1-2,5-6', 'Invalid typed selection did not recover through marquee'
        s.expression.set('1-2,5-6,8')
        start_drag(); s.set_enabled(False); assert s.gesture is None and s.edge_timer is None
        click(3, 1); assert s.expression.get() == '1-2,5-6,8'
        s.set_enabled(True, False); click(3, 4); start_drag()
        assert s.gesture is None and s.expression.get() == '1-2,5-6,8'
        s.set_enabled(True); s.changed = changed
        # Real exported pages follow the gesture-produced selection; source stays intact.
        s.expression.set('8'); x, y = start_drag(); event('<ButtonRelease-1>', x, y)
        page.output.set(str(folder)); page.prefix.set('เลือกด้วยเมาส์'); plan = page.plan
        page.start(); wait(root, app)
        with pymupdf.open(plan.outputs[0].path) as result:
            assert [p.get_text().strip() for p in result] == ['PAGE 1', 'PAGE 2', 'PAGE 5', 'PAGE 6']
        assert hashlib.sha256(small.read_bytes()).hexdigest() == original

        page.add_paths([large]); wait(root, app); settled(root, s); s.expression.set('1')
        changes = []; s.changed = lambda: changes.append(s.expression.get())
        renders = []; render = s.render
        def timed_render():
            begin = time.perf_counter(); render(); renders.append((time.perf_counter() - begin) * 1000)
        s.render = timed_render
        event('<ButtonPress-1>', 1, 1)
        x, y = point(6); before = len(renders); begin = time.perf_counter()
        for _ in range(1000): event('<B1-Motion>', x, y, 256)
        dispatch_ms = (time.perf_counter() - begin) * 1000
        assert len(renders) == before and s.draw_timer is not None and not changes
        pump(root, .06); assert len(s.visible) <= 24 and len(c.find_all()) <= 24 * 4 + 1
        heartbeat = []; running = True
        def beat():
            if running:
                heartbeat.append(time.perf_counter()); root.after(10, beat)
        beat(); end = time.perf_counter() + .6
        while time.perf_counter() < end:
            event('<B1-Motion>', x, y, 256); root.update(); time.sleep(.005)
        running = False
        assert len(heartbeat) >= 10 and not changes
        gap_ms = max(b - a for a, b in zip(heartbeat, heartbeat[1:])) * 1000
        # Edge auto-scroll extends a single marquee across offscreen rows.
        event('<B1-Motion>', x, c.winfo_height() + 25, 256)
        before_y = c.canvasy(0); pump(root, .7)
        assert c.canvasy(0) > before_y and s.edge_timer is not None
        event('<ButtonRelease-1>', x, c.winfo_height() + 25)
        assert len(changes) == 1 and max(s.selection()) > 12
        assert s.gesture is None and s.edge_timer is None and c.grab_current() is None
        assert gap_ms < 250 and max(renders) < 250
        s.render = render; s.changed = changed
        assert len(s.visible) <= 24 and len(s.pending) <= 16 and s.cache.resident_bytes <= 6 * 1048576
        event('<ButtonPress-1>', 1, 100); event('<B1-Motion>', x, -25, 256)
        before_y = c.canvasy(0); pump(root, .5); assert c.canvasy(0) < before_y
        c.event_generate('<Escape>'); assert s.edge_timer is None and c.grab_current() is None
        before_selection = s.expression.get()
        event('<ButtonPress-1>', 1, 1); event('<B1-Motion>', x, c.winfo_height() + 10, 256)
        app.show_home(); assert s.gesture is None and s.edge_timer is None and s.draw_timer is None
        assert c.grab_current() is None and app.preview_coordinator.process is None
        app.show_tool('extract-pages'); pump(root, .1); assert s.expression.get() == before_selection
        event('<ButtonPress-1>', 1, 1); event('<B1-Motion>', x, y, 256)
        root.geometry('1280x900'); pump(root, .1); assert s.gesture is None and c.grab_current() is None
        event('<ButtonPress-1>', 1, 1); event('<B1-Motion>', x, c.winfo_height() + 10, 256)
        s.set_document(s.info); assert s.gesture is None and s.edge_timer is None and c.grab_current() is None
        # The shared interaction is wired in every editable page tool.
        for tool in ('split', 'delete-pages', 'rotate'):
            app.show_tool(tool); p = app.active_page; p.add_paths([small]); wait(root, app)
            if tool == 'split': p.mode.set('ranges')
            s = p.selector; c = s.canvas; s.expression.set(''); pump(root, .1)
            click(1); click(3, 1); assert s.expression.get() == '1-3', tool
            assert s.gesture_hint.winfo_rooty() + s.gesture_hint.winfo_height() <= s.winfo_rooty() + s.winfo_height()
        app.close(); assert not errors, errors
    report = {'version': VERSION, 'passed': True, 'hardware': platform.platform(),
              'scope': 'Windows development host/source app; synthetic text PDFs; not physical 4-GiB/HDD certification',
              'checks': ['Shift-click forward/reverse/shrinking anchor', 'Ctrl-click toggle', 'Ctrl+Shift additive range',
                         'Shift-arrow extending/shrinking range', 'Ctrl+A', 'marquee replace/Ctrl toggle/Shift add',
                         'one plan update on release', 'Escape restores selection', 'busy/readonly guards',
                         'edge auto-scroll/offscreen selection/outside release', 'hide/resize/document/focus loss cancels grab and timers',
                         'four page tools', 'exported pages match selection and source hash unchanged'],
              'document_pages': 1000, 'burst_events': 1000, 'burst_dispatch_ms': round(dispatch_ms, 2),
              'max_frame_ms': round(max(renders), 2), 'max_heartbeat_gap_ms': round(gap_ms, 2),
              'visible_limit': 24, 'shared_request_limit': 16, 'cache_bytes': 6 * 1048576,
              'tk_errors': errors, 'cleanup': True}
    (ROOT / f'docs/page-gestures-verification-{VERSION}.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    # Tk synthesizes letter keysyms through the calling thread's keyboard layout.
    # Keep the native test deterministic on a Thai desktop; restore that thread.
    import ctypes
    user32 = ctypes.windll.user32
    user32.GetKeyboardLayout.restype = ctypes.c_void_p
    user32.ActivateKeyboardLayout.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    layout = user32.GetKeyboardLayout(0)
    user32.ActivateKeyboardLayout(0x04090409, 0)
    try:
        main()
    finally:
        user32.ActivateKeyboardLayout(layout, 0)
