"""Native per-PDF image selection, bounded previews, source safety and layout."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import customtkinter as ctk
import pymupdf
from PIL import Image
from pdf_lover.app import App
from pdf_lover.version import VERSION
from tests.ui.verify_merge import pump,capture

ROOT=Path(__file__).resolve().parents[2]

def wait(root,app):
    deadline=time.monotonic()+30
    while app.busy and time.monotonic()<deadline:pump(root,0.02)
    assert not app.busy

def choose(root,page,path):
    page.selection_buttons[path].invoke()
    assert page.busy and page.activity_indicator.running
    wait(root,page.app)
    assert page.selection_window is not None
    pump(root,0.5)
    return page.selection_window

def main():
    errors=[];cases=[]
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);sources=[]
        for name,count in (("เอกสาร หนึ่ง",8),("second",3),("large",1000)):
            path=folder/(name+'.pdf')
            with pymupdf.open() as doc:
                for n in range(count):doc.new_page(width=144,height=72).insert_text((10,30),str(n+1))
                doc.save(path)
            sources.append(path.resolve())
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(scale)
            root=ctk.CTk();root.report_callback_exception=lambda k,v,t:errors.append(str(v))
            app=App(root);app.show_tool('pdf-png');root.geometry('920x700+15+15');pump(root,0.2)
            page=app.png;page.add_paths(sources[:2]);page.output.set(str(folder/f'out-{scale}'))
            window=choose(root,page,sources[0]);selector=window.selector
            assert len(selector.selection())==8
            page.start();assert not app.busy and page.selection_window is window
            for invalid in ('','9','3-1','1,1','5,2'):
                selector.expression.set(invalid);pump(root,0.02)
                assert window.apply_button.cget('state')=='disabled'
            selector.expression.set('1-3,5,8');selector.toggle(2)
            assert selector.selection()==(1,3,5,8)
            capture(window,f'image-selection-{scale}.png')
            assert selector.canvas.winfo_height()>=150*scale
            assert window.apply_button.winfo_rooty()+window.apply_button.winfo_height()<=window.winfo_rooty()+window.winfo_height()
            token=selector.worker.token
            window.apply_button.invoke();assert page.selection_window is None
            assert token not in app.preview_coordinator.clients
            assert page.selections[sources[0]][1]=='1,3,5,8'
            capture(root,f'image-queue-selection-{scale}.png')
            window=choose(root,page,sources[1]);window.selector.expression.set('2');window.apply_button.invoke()
            window=choose(root,page,sources[0]);assert window.selector.selection()==(1,3,5,8)
            window.selector.select_all();page.close_selection()
            assert page.selections[sources[0]][1]=='1,3,5,8' # cancel preserves committed choice
            app.show_home();app.show_tool('pdf-png');assert len(page.selections)==2
            page.dpi.set('72');page.start();assert app.busy
            page.choose_pages(sources[0]);assert page.selection_window is None
            wait(root,app);assert not page.errors,page.errors
            assert page.selection_buttons[sources[0]].cget('state')=='normal'
            for path,expected in ((sources[0],(1,3,5,8)),(sources[1],(2,))):
                out=Path(page.output.get())/path.stem
                assert sorted(p.name for p in out.glob('*.png'))==[f'{path.stem}_page_{n:03}.png' for n in expected]
                with (out/'image_report.csv').open(encoding='utf-8-sig') as f:assert len(list(csv.DictReader(f)))==len(expected)
                with pymupdf.open(path) as doc:
                    for n in expected:
                        with Image.open(out/f'{path.stem}_page_{n:03}.png') as image:
                            assert image.tobytes()==doc[n-1].get_pixmap(dpi=72,alpha=False).samples
            page.add_paths([sources[2]])
            window=choose(root,page,sources[2]);selector=window.selector
            assert len(selector.visible)<=24 and selector.cache.resident_bytes<=6*1048576
            assert selector.worker.coordinator is app.preview_coordinator
            assert len(app.preview_coordinator.outstanding)<=16
            selector.expression.set('1,500,1000');window.apply_button.invoke()
            window=choose(root,page,sources[2]);assert window.selector.selection()==(1,500,1000)
            app.show_home();assert page.selection_window is None
            assert app.preview_coordinator.process is None
            assert not selector.cache and selector.draw_timer is None
            app.show_tool('pdf-png');page.remove_file(sources[2]);assert sources[2] not in page.selections
            page.remove_file(sources[1]);assert sources[1] not in page.selections
            window=choose(root,page,sources[0]);window.selector.select_all();window.apply_button.invoke()
            assert page.selections[sources[0]][1]=='1-8'
            # Edited source invalidates the committed inspection snapshot before any output.
            if scale==1.25:
                sources[0].write_bytes(sources[0].read_bytes()+b'\n')
                page.output.set(str(folder/'changed'));page.start();wait(root,app)
                assert page.errors and not (folder/'changed'/sources[0].stem).exists()
                sources[0].write_bytes(sources[0].read_bytes()[:-1])
            page.clear_files();assert not page.selections
            broken=folder/'bad.pdf';broken.write_bytes(b'broken');page.add_paths([broken])
            page.choose_pages(broken.resolve());wait(root,app);assert page.selection_window is None
            assert not page.activity_indicator.running
            app.show_home()
            for timer in root.tk.call('after','info'):root.after_cancel(timer)
            root.destroy();cases.append({'scale':scale,'passed':True})
        for p in sources:assert hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p]
    assert not errors,errors
    report={'version':VERSION,'passed':True,'cases':cases,'checks':['per-document ascending ranges','thumbnail toggle and all pages','invalid and empty selections','cancel and retained state','actual selected PNG pixels and original filenames','CSV selected rows','changed source refusal before output','1000-page viewport/cache bound','inspection errors and busy guards','dialog close on navigation/removal/destruction'],'tk_errors':errors,'scope':'Windows development source app, synthetic PDFs; not physical low-spec certification'}
    (ROOT/f'docs/image-selection-verification-{VERSION}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
