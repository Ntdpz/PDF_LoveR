"""Native retained-state, preview lifecycle/budgets and rapid request regression."""
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/ui')]
import customtkinter as ctk
import pymupdf
from pdf_lover.app import App
from pdf_lover.version import VERSION
from verify_merge import pump


def main():
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'resource fixture.pdf'
        with pymupdf.open() as doc:
            for i in range(240):doc.new_page().insert_text((72,72),f'Page {i+1}')
            doc.save(path)
        root = ctk.CTk();root.report_callback_exception = lambda kind,value,trace:errors.append(str(value))
        app = App(root)
        for tool in ('pdf-png','merge','split','extract-pages','delete-pages','rotate','organize'):
            app.show_tool(tool);app.active_page.add_paths([path])
            end = time.monotonic()+20
            while app.busy and time.monotonic()<end:pump(root,.05)
            assert not app.busy
            pump(root,1)
            assert len(app.preview_coordinator.outstanding)<=16
            for name,page in app.views.items():
                for attr in ('cards','selector','preview'):
                    widget = getattr(page,attr,None)
                    if not widget:continue
                    assert widget.worker.coordinator is app.preview_coordinator
                    assert widget.cache.resident_bytes<=widget.cache.max_bytes
                    if name!=tool:
                        assert not widget.pending and not widget.cache and not widget.worker.mailbox
        rotate = app.get_page("rotate");app.show_tool("rotate");rotate.selector.expression.set('2-3');rotate.angle.set('90')
        for _ in range(20):
            app.show_tool('split');app.active_page.selector.move(1);pump(root,.02)
            app.show_tool('merge');pump(root,.02)
            app.show_tool('rotate');rotate.preview.move(1);rotate.rotate_step(90);pump(root,.02)
        rotate.preview.page=2;rotate.angle.set('90');rotate.preview.render()
        end=time.monotonic()+20
        while not all(rotate.preview.cache.get(key) for key in rotate.preview.keys()) and time.monotonic()<end:
            pump(root,.05)
        assert all(rotate.preview.cache.get(key) for key in rotate.preview.keys())
        for key in rotate.preview.keys():
            with pymupdf.open(path) as doc:
                page=doc[key[3]];page.set_rotation((page.rotation+key[4])%360)
                factor=min(key[5]/page.rect.width,key[6]/page.rect.height)
                pix=page.get_pixmap(matrix=pymupdf.Matrix(factor,factor),colorspace=pymupdf.csRGB,alpha=False)
                assert rotate.preview.cache[key]==(pix.width,pix.height,pix.samples)
        assert rotate.selector.expression.get()=='2-3'
        child=app.preview_coordinator.process;assert child and child.is_alive()
        app.show_home();assert app.preview_coordinator.process is None
        assert all(not getattr(page,'selector',None) or not page.selector.cache for page in app.views.values())
        app.show_tool('rotate');assert rotate.selector.expression.get()=='2-3'
        pump(root,1);assert app.preview_coordinator.process and app.preview_coordinator.process.is_alive()
        app.close();assert app.preview_coordinator.process is None;assert not errors,errors
    report={'passed':True,'preview_process_limit':1,'home_preview_processes':0,'request_limit':16,
            'navigation_cycles':20,'hidden_caches_released':True,'retained_selection':True,
            'latest_preview_pixels_match':True,'cleanup':True,'tk_errors':errors}
    (ROOT/f'docs/resource-verification-{VERSION}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
