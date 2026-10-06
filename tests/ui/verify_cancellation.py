"""Native stop/retry checks: keep busy until real worker cleanup, all six tools."""
import csv
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import customtkinter as ctk
import pymupdf
from pdf_lover.app import App
from pdf_lover.version import VERSION
from tests.ui.verify_png import pump, screenshot
from tests.ui.verify_activity import wait

ROOT=Path(__file__).resolve().parents[2]


def until(root, condition):
    deadline=time.monotonic()+15
    while not condition() and time.monotonic()<deadline:pump(root,0.02)
    assert condition(),'Worker did not reach safe checkpoint'


def main():
    cases=[];errors=[]
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary);sources=[folder/'first.pdf',folder/'second.pdf']
        for path in sources:
            with pymupdf.open() as doc:
                for n in range(3):doc.new_page(width=144,height=72).insert_text((10,30),f'Original {n}')
                doc.save(path)
        hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(scale)
            root=ctk.CTk();root.report_callback_exception=lambda k,v,t:errors.append(str(v))
            app=App(root);root.geometry('920x700+15+15')
            for tool in ('pdf-png','merge','split','extract-pages','delete-pages','rotate'):
                app.show_tool(tool);page=app.active_page;pump(root,0.1)
                page.add_paths(sources if tool in ('merge','pdf-png') else [sources[0]])
                wait(root,app)
                output=folder/f'{scale}-{tool}';output.mkdir()
                page.output.set(str(output/'merged.pdf') if tool=='merge' else str(output))
                if tool=='delete-pages':page.selector.expression.set('2')
                if tool=='rotate':page.rotation_buttons[1].invoke()
                if tool=='pdf-png':page.dpi.set('72')
                page_module=importlib.import_module(type(page).__module__)
                function={'pdf-png':'convert_pdf','merge':'merge_pdfs','split':'split_pdf','rotate':'rotate_pdf'}.get(tool)
                owner=page_module if function else page
                function=function or 'export'
                engine=getattr(owner,function);ready=threading.Event();gate=threading.Event()
                def delayed(*args,**kwargs):
                    args=list(args);index=3 if tool=='pdf-png' else 2 if tool=='merge' else 1
                    progress=args[index]
                    def boundary(*event):
                        progress(*event)
                        if not ready.is_set():ready.set();assert gate.wait(15)
                    args[index]=boundary
                    return engine(*args,**kwargs)
                with patch.object(owner,function,delayed):
                    try:
                        page.start();until(root,ready.is_set);pump(root,0.1)
                        assert app.busy and page.cancel_button.winfo_ismapped(),(tool,scale,app.busy,page.status.get())
                        page.cancel_button.invoke();token=page.cancel_event
                        page.request_cancel();assert token is page.cancel_event and token.is_set()
                        assert page.cancel_button.cget('state')=='disabled'
                        assert app.busy and page.activity_indicator.running
                        assert not app.show_home()
                        pump(root,0.1)
                        assert "กำลังยกเลิก" in page.status.get(),page.status.get()
                        assert page.home_button.winfo_rootx()+page.home_button.winfo_width()<=root.winfo_rootx()+root.winfo_width()
                        assert page.cancel_button.winfo_rootx()>=page.activity_indicator.winfo_rootx()+page.activity_indicator.winfo_width()
                        for attempt in range(3):
                            try:
                                screenshot(root,f'cancellation-{tool}-{scale}.png');break
                            except OSError:
                                if attempt==2:raise
                                pump(root,0.1)
                    finally:
                        gate.set();wait(root,app)
                assert not page.activity_indicator.running and not page.cancel_button.winfo_ismapped()
                assert 'ยกเลิก' in page.status.get(),page.status.get()
                assert page.start_button.cget('state')=='normal'
                assert not list(output.glob('.pdf-lover-*'))
                if tool=='pdf-png':
                    images=list(output.rglob('*.png'));assert len(images)==1
                    with (images[0].parent/'image_report.csv').open(encoding='utf-8-sig',newline='') as report:
                        assert len(list(csv.DictReader(report)))==1
                    assert page.file_states[sources[0]]=='หยุดแล้ว'
                    assert page.file_states[sources[1]]=='ไม่ได้เริ่ม'
                    assert page.destination==output and page.progress.get()<1
                else:
                    assert not list(output.glob('*.pdf'))
                    assert page.destination is None
                page.start();wait(root,app)
                assert page.cancel_event is not token and not page.cancel_event.is_set()
                assert page.destination and page.progress.get()==1,page.status.get()
                cases.append({'tool':tool,'scale':scale,'phase':'export-stop-retry','passed':True})
                # Inspection stop must not apply metadata or open a selection dialog.
                if tool!='merge':
                    method='_inspect_selection' if tool=='pdf-png' else '_inspect_worker'
                    worker=getattr(page,method);ready=threading.Event();gate=threading.Event()
                    def delayed_inspection(*args):ready.set();assert gate.wait(15);worker(*args)
                    with patch.object(page,method,delayed_inspection):
                        try:
                            page.choose_pages(sources[0]) if tool=='pdf-png' else page.add_paths([sources[1]])
                            until(root,ready.is_set);page.cancel_button.invoke()
                            assert app.busy
                        finally:gate.set();wait(root,app)
                    assert 'ยกเลิก' in page.status.get()
                    if tool=='pdf-png':assert page.selection_window is None
                    elif tool!='rotate':assert page.info is None
                    else:assert all(info.path!=sources[1] for info in page.inputs)
                    cases.append({'tool':tool,'scale':scale,'phase':'inspection-stop','passed':True})
            assert hashes==[hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
            assert not errors,errors
            app.show_home();pump(root,0.1)
            assert app.preview_coordinator.process is None
            for timer in root.tk.call('after','info'):root.after_cancel(timer)
            root.destroy()
    result={'passed':True,'version':VERSION,'cases':cases,'source_hashes_preserved':True,
            'pdf_rollback':True,'image_partial_csv_retained':True,'single_cancel_token_per_job':True,
            'busy_until_cleanup':True,'preview_cleanup':True,'tk_errors':errors,
            'limitations':['Development Windows PC, not physical 2-core/4-GiB/HDD certification',
                           'Gates at actual engine progress checkpoints simulate native I/O delay; native calls finish before stopping']}
    (ROOT/f'docs/cancellation-verification-{VERSION}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('PASS: six tools stop/retry, five inspection paths, safe partial output, source hashes, 100%/125% layout and cleanup')


if __name__=='__main__':main()
