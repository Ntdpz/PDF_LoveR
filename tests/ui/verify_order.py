"""Real Tk ordering, cancellation/retry, bounded previews and independent fidelity."""
import hashlib
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests/ui'), str(ROOT / 'tests/unit')]
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageChops
from pdf_lover.app import App
from pdf_lover.core.cancellation import checkpoint
from pdf_lover.diagnostics.self_test import native_drop
from test_pdf_merge import make_pdf
from verify_merge import pump, capture, dispose
from verify_split import wait


def main():
    errors = []
    affinity = '--two-core' in sys.argv
    if affinity:
        assert ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(-1), ctypes.c_size_t(3))
    ctk.set_appearance_mode('light')
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    with tempfile.TemporaryDirectory(prefix='order-ui-') as sandbox:
        folder = Path(sandbox)
        source = folder / 'ต้นฉบับ เรียง.pdf'
        make_pdf(source, [f'PAGE {p}' for p in range(1, 9)], field='Preserve')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
        app = App(root)
        root.geometry('920x700+20+20')
        assert app.show_tool('organize')
        page = app.active_page
        native_drop(root, [source])
        pump(root, .1)
        wait(root, app)
        page.output.set(str(folder))
        selector = page.selector
        assert selector.order == tuple(range(1, 9))
        pump(root, .5)
        selector.expression.set('2,4')
        selector.nudge(1)
        assert selector.order == (1,3,5,2,4,6,7,8)
        selector._keyboard(SimpleNamespace(state=8, keysym='Left'))
        assert selector.order == (1,3,2,4,5,6,7,8)
        selector.reset_order()
        # Tk-generated pointer events use the actual viewport card geometry.
        selector.expression.set('1,3')
        x1,y1,x2,y2 = selector.visible[1]
        sx,sy = int((x1+x2)/2), int((y1+y2)/2-selector.canvas.canvasy(0))
        target = min(selector.visible.keys(), key=lambda p: -p)
        tx1,ty1,tx2,ty2 = selector.visible[target]
        tx,ty = int(tx2-3), int((ty1+ty2)/2-selector.canvas.canvasy(0))
        selector.canvas.event_generate('<ButtonPress-1>', x=sx, y=sy)
        selector.canvas.event_generate('<B1-Motion>', x=tx, y=ty)
        pump(root,.08)
        assert selector.drag and selector.drag['active']
        selector.canvas.event_generate('<ButtonRelease-1>', x=tx, y=ty)
        assert selector.order != tuple(range(1,9))
        assert selector.order.index(3) == selector.order.index(1)+1
        order = selector.order
        # Escape restores the committed order and releases the grab.
        x1,y1,x2,y2 = selector.visible[min(selector.visible)]
        selector._press(SimpleNamespace(x=int((x1+x2)/2),y=int((y1+y2)/2-selector.canvas.canvasy(0)),state=0))
        selector._motion(SimpleNamespace(x=tx,y=ty))
        selector._keyboard(SimpleNamespace(state=0,keysym='Escape'))
        assert selector.order == order and selector.canvas.grab_current() is None
        assert app.show_home() and app.show_tool('organize')
        assert page.selector.order == order
        page.refresh_plan()
        assert page.plan.outputs[0].pages == order
        assert page.results.item(page.results.get_children()[0],'values')[0] == f'1 (เดิม {order[0]})'
        # Hold a worker at a safe checkpoint so cancellation is deterministic.
        entered = threading.Event()
        def blocked(plan, progress=None, cancel=None):
            entered.set()
            cancel.wait(5)
            checkpoint(cancel)
        with patch.object(page,'export',blocked):
            page.start()
            pump(root,.1)
            assert entered.is_set() and app.busy
            assert page.cancel_button.cget('state') == 'normal'
            page.request_cancel()
            wait(root,app)
        assert not app.busy and page.progress.get() == 0
        assert not list(folder.glob('*_จัดเรียง.pdf'))
        plan = page.plan
        page.start()
        wait(root,app)
        assert page.progress.get() == 1, page.status.get()
        with pymupdf.open(plan.outputs[0].path) as result:
            assert [p.get_text().splitlines()[0] for p in result] == [f'PAGE {p}' for p in order]
        for index,original in enumerate(order,1):
            images = []
            for name,pdf,number in [('a',source,original),('b',plan.outputs[0].path,index)]:
                prefix = folder/name
                subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-singlefile','-r','72','-png',str(pdf),str(prefix)],check=True,capture_output=True)
                with Image.open(str(prefix)+'.png') as image:
                    images.append(image.convert('RGB'))
            assert images[0].size == images[1].size and ImageChops.difference(*images).getbbox() is None
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        # Multi-source editing uses original identities; history includes import/delete/move/reset.
        page.add_paths([source], replace=True)
        wait(root, app)
        extra = folder/'เพิ่มหน้าจากไฟล์อื่น.pdf'
        make_pdf(extra, ['EXTRA 1', 'EXTRA 2', 'EXTRA 3'], width=380, height=240, field='Independent')
        with pymupdf.open(extra) as document:
            document[1].set_cropbox(pymupdf.Rect(20,10,360,220))
            document[1].set_rotation(270)
            document.saveIncr()
        extra_digest = hashlib.sha256(extra.read_bytes()).hexdigest()
        selector.expression.set('2')
        page.add_paths([extra])
        wait(root, app)
        imported = (1,9,10,11,2,3,4,5,6,7,8)
        assert selector.order == imported, selector.order
        assert len(selector.sources) == 2 and selector.info.page_count == 11
        selector.expression.set('2,4')
        selector.delete_selected()
        edited = (1,10,2,3,4,5,6,7,8)
        assert selector.order == edited
        selector.undo()
        assert selector.order == imported and selector.selection() == (2,4)
        selector.undo(redo=True)
        assert selector.order == edited
        selector.reset_order()
        assert selector.order == tuple(range(1,9))
        selector.undo()
        assert selector.order == edited
        selector.expression.set('1-9')
        selector.delete_selected()
        assert selector.order == edited  # No empty output.
        selector.expression.set('')
        page.add_paths([extra])
        wait(root,app)
        assert selector.order == edited and 'อยู่ในโต๊ะงาน' in page.status.get()
        # Inspection cancellation preserves all committed edits and can restart.
        inspected = threading.Event()
        original_inspect = page.inspect
        def held(path):
            inspected.set()
            page.cancel_event.wait(5)
            checkpoint(page.cancel_event)
            return original_inspect(path)
        with patch.object(page, 'inspect', held):
            page.add_paths([source], replace=True)
            pump(root,.1)
            assert inspected.is_set() and app.busy
            page.request_cancel()
            wait(root,app)
        assert selector.order == edited and not app.busy
        page.prefix.set('mixed')
        mixed_plan = page.plan
        page.start()
        wait(root,app)
        assert page.progress.get() == 1, page.status.get()
        for index,identity in enumerate(edited,1):
            source_index,number = selector.references[identity]
            pdf = selector.sources[source_index].path
            images=[]
            for name,path,number in [('source',pdf,number),('mixed',mixed_plan.outputs[0].path,index)]:
                prefix=folder/name
                subprocess.run(['pdftoppm','-f',str(number),'-l',str(number),'-singlefile','-r','72','-png',str(path),str(prefix)],check=True,capture_output=True)
                with Image.open(str(prefix)+'.png') as image:
                    images.append(image.convert('RGB'))
            assert images[0].size == images[1].size and ImageChops.difference(*images).getbbox() is None
        assert hashlib.sha256(extra.read_bytes()).hexdigest() == extra_digest
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        large = folder/'240 หน้า.pdf'
        make_pdf(large,[f'PAGE {p}' for p in range(1,241)])
        page.add_paths([large], replace=True)
        wait(root,app)
        page.prefix.set('large')
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale)
            ctk.set_window_scaling(scale)
            root.minsize(round(920/scale), round(700/scale))
            root.geometry(f'{round(920/scale)}x{round(700/scale)}+20+20')
            pump(root,.3)
            assert abs(root.winfo_width()-920)<=2 and abs(root.winfo_height()-700)<=2
            selector.expression.set('2')
            selector.delete_selected()
            assert len(selector.order)==239
            selector.canvas.focus_force()
            selector.canvas.event_generate('<KeyPress>',keycode=90,state=4)
            pump(root,.1)
            assert len(selector.order)==240
            selector.canvas.event_generate('<KeyPress>',keycode=89,state=4)
            pump(root,.1)
            assert len(selector.order)==239
            selector.undo()
            for _ in range(5):
                selector.move(1)
                pump(root,.08)
            assert len(selector.visible) <= 24
            assert len(selector.pending) <= 16
            assert len(selector.cache) <= 32 and selector.cache.resident_bytes <= 6*1048576
            assert page.results.winfo_height() >= 60, page.results.winfo_height()
            for widget in (selector,page.results,page.start_button,page.open_button,page.output_entry,page.prev_outputs,page.next_outputs):
                assert widget.winfo_rootx() >= root.winfo_rootx()
                assert widget.winfo_rootx()+widget.winfo_width() <= root.winfo_rootx()+root.winfo_width()
                assert widget.winfo_rooty()+widget.winfo_height() <= root.winfo_rooty()+root.winfo_height()
            for widget in page.order_focus:
                if widget.cget('state') != 'disabled':
                    widget.focus_force()
                    pump(root,.04)
                    canvas = page.order_options._parent_canvas
                    assert widget.winfo_rooty() >= canvas.winfo_rooty(), (widget, 'above')
                    assert widget.winfo_rooty()+widget.winfo_height() <= canvas.winfo_rooty()+canvas.winfo_height(), (widget, 'below')
            page.order_options._parent_canvas.yview_moveto(0)
            pump(root,.2)
            capture(root,f'order-{scale}.png')
            assert not page.cancel_button.winfo_ismapped()
        # Coalesced rapid pointer input under a two-logical-core affinity when requested.
        selector.canvas.yview_moveto(0)
        pump(root,.1)
        selector.expression.set('1,3')
        x1,y1,x2,y2=selector.visible[1]
        sx,sy=int((x1+x2)/2),int((y1+y2)/2)
        selector._press(SimpleNamespace(x=sx,y=sy,state=0))
        gaps=[]
        timer=None
        def beat(previous=None):
            nonlocal timer
            now=time.perf_counter()
            if previous is not None:gaps.append((now-previous)*1000)
            timer=root.after(20,lambda:beat(now))
        beat()
        started=time.perf_counter()
        for i in range(1000):
            selector._motion(SimpleNamespace(x=sx+20+i%30,y=sy+20))
            if i%20==0:pump(root,.005)
        pump(root,.1)
        root.after_cancel(timer)
        selector._keyboard(SimpleNamespace(state=0,keysym='Escape'))
        assert max(gaps)<200, max(gaps)
        interaction={'pointer_events':1000,'elapsed_ms':round((time.perf_counter()-started)*1000,2),
                     'heartbeat_max_gap_ms':round(max(gaps),2),'cpu_affinity_logical_cores':2 if affinity else None}
        dispose(root)
        assert app.preview_coordinator.process is None
        assert not errors,errors
    report = {'passed':True,'order':list(order),'source_unchanged':True,'poppler_pixels_match':True,
              'multi_drag':True,'keyboard_move':True,'cancel_retry':True,'escape':True,
              'multi_source_insert_delete':True,'undo_redo_reset':True,'inspection_cancel_preserves_edits':True,
              'duplicate_source_rejected':True,'mixed_poppler_pixels_match':True,
              'document_pages':240,'visible_limit':24,'requests_limit':16,'cache_bytes_limit':6*1048576,
              'minimum_window':[920,700],'scaling':[1,1.25],'worker_cleanup':True,'tk_errors':errors}
    report['interaction']=interaction
    report['limitations']=['Development Windows host; affinity is not physical 2-core / 4-GiB / HDD certification']
    (ROOT/'docs/order-verification-1.13.0.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
