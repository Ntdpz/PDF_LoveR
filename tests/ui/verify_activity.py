"""Real job lifecycle checks for shared activity feedback on all six tools."""
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import customtkinter as ctk
import pymupdf
from pdf_lover.app import App
from pdf_lover.version import VERSION
from tests.ui.verify_png import pump, screenshot

ROOT = Path(__file__).resolve().parents[2]


def wait(root, app):
    deadline = time.monotonic() + 20
    while app.busy and time.monotonic() < deadline:
        pump(root, 0.02)
    assert not app.busy, 'Worker timeout'


def main():
    cases, errors, gaps = [], [], []
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        sources = [folder / 'first.pdf', folder / 'second.pdf']
        for source in sources:
            with pymupdf.open() as doc:
                for index in range(3):
                    doc.new_page(width=144, height=72).insert_text((10, 30), f'Original {index}')
                doc.save(source)
        original_hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        for scale in (1, 1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(scale)
            root = ctk.CTk()
            root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
            app = App(root)
            root.geometry("920x700+15+15")
            def held(page, method, action, phase):
                gate = threading.Event(); worker = getattr(page, method)
                def delayed(*args):
                    gate.wait(10)
                    worker(*args)
                badge = page.activity_indicator
                badge.motion_enabled = scale == 1
                before = badge.frame_count
                with patch.object(page, method, delayed):
                    try:
                        action()
                        assert app.busy and badge.running and badge.started is not None
                        assert not app.show_home()
                        assert badge.text.cget('text').startswith('กำลังทำงาน')
                        angle = badge.canvas.itemcget(badge.arc, 'start')
                        end = time.monotonic() + (1.1 if app.route == 'pdf-png' else 0.3)
                        previous = time.monotonic()
                        while time.monotonic() < end:
                            root.update();time.sleep(0.01)
                            now = time.monotonic();gaps.append((now - previous) * 1000);previous=now
                        assert badge.frame_count > before if badge.motion_enabled else badge.frame_count == before
                        if not badge.motion_enabled:
                            assert badge.canvas.itemcget(badge.arc, 'start') == angle
                        if app.route == 'pdf-png':
                            assert badge.elapsed_seconds >= 1 and '00:01' in badge.text.cget('text')
                        assert page.home_button.winfo_rootx() + page.home_button.winfo_width() <= root.winfo_rootx() + root.winfo_width()
                        for attempt in range(3):
                            try:
                                screenshot(root, f'activity-{app.route}-{phase}-{scale}.png')
                                break
                            except OSError:
                                if attempt == 2:raise
                                pump(root,0.1)
                        cases.append({'tool': app.route, 'phase': phase, 'scale': scale, 'motion': badge.motion_enabled})
                    finally:
                        gate.set()
                        wait(root, app)
                assert not badge.running and badge.started is None
                assert badge.canvas.itemcget(badge.arc, 'state') == 'hidden'
                count = badge.frame_count;pump(root,0.1);assert badge.frame_count == count
            for tool in ('pdf-png','merge','split','extract-pages','delete-pages','rotate'):
                assert app.show_tool(tool);page=app.active_page;pump(root,0.1)
                if hasattr(page,'_inspect_worker'):
                    held(page,'_inspect_worker',lambda:page.add_paths([sources[0]]),'inspect')
                else:
                    page.add_paths(sources if tool == 'merge' else [sources[0]])
                output = folder / f'{scale}-{tool}';output.mkdir()
                page.output.set(str(output/'merged.pdf') if tool=='merge' else str(output))
                if tool=='delete-pages':page.selector.expression.set('2')
                if tool=='rotate':page.rotation_buttons[1].invoke()
                worker = {'pdf-png':'convert_all','merge':'_worker','split':'_split_worker'}.get(tool,'_export_worker')
                held(page,worker,page.start,'export')
                assert page.destination and page.progress.get()==1
                badge=page.activity_indicator;count=badge.frame_count
                assert app.show_home();pump(root,0.1);assert not badge.visible and badge.frame_count==count
            assert app.show_tool('split');page=app.active_page
            broken=folder/'broken.pdf';broken.write_bytes(b'not PDF')
            held(page,'_inspect_worker',lambda:page.add_paths([broken]),'error')
            assert page.info is None and not app.busy
            assert original_hashes == [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
            assert not errors,errors
            for timer in root.tk.call('after','info'):root.after_cancel(timer)
            root.destroy()
    gaps.sort()
    report={'passed':True,'version':VERSION,'cases':cases,'idle_hidden_frames':0,'animation_uses_existing_shell_poll':True,
            'elapsed_time_verified':True,'reduced_motion_verified':True,'source_hashes_preserved':True,
            'heartbeat_gap_p95_ms':round(gaps[int(len(gaps)*0.95)],2),'heartbeat_gap_max_ms':round(max(gaps),2),
            'tk_errors':errors,'limitations':['Development Windows PC; not physical 2-core/4-GiB/HDD proof','Worker gates simulate I/O delay before real inspection/export; heartbeat includes screenshots and test overhead']}
    (ROOT/f'docs/activity-verification-{VERSION}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: all six tools, inspection/export/error, elapsed time, idle/hidden cleanup, reduced motion and 100%/125% layout')


if __name__=='__main__':main()
