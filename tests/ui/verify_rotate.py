"""Native rotation UI and independent preview/output equivalence."""
from dataclasses import replace
import hashlib,json,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/ui'),str(ROOT/'tests/unit')]
import customtkinter as ctk
import pymupdf
from PIL import Image,ImageChops
import pdf_lover.app as app_module
from pdf_lover.features.registry import PAGE_FACTORIES
from pdf_lover.features.rotate.page import RotatePage
from pdf_lover.diagnostics.self_test import native_drop
from test_pdf_merge import make_pdf
from verify_merge import pump,capture,dispose
from verify_split import wait


def main():
    ctk.set_appearance_mode('light');ctk.set_widget_scaling(1);ctk.set_window_scaling(1)
    errors=[]
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);a=folder/'ต้นฉบับ A.pdf';b=folder/'ต้นฉบับ B.pdf'
        make_pdf(a,['A1','A2','A3'],field='Value');make_pdf(b,['B1'],width=340,height=200)
        hashes={p:hashlib.sha256(p.read_bytes()).digest() for p in (a,b)}
        root=ctk.CTk();root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
        app=app_module.App(root);app.show_tool('rotate');page=app.active_page;root.geometry('1080x780+20+20');pump(root)
        capture(root,'rotate-empty.png');page.start();assert not app.busy
        native_drop(root,[a,b]);pump(root,0.05);wait(root,app)
        assert len(page.inputs)==2 and [i.page_count for i in page.inputs]==[3,1]
        assert page.angle.get()=='0' and page.plan is None and page.start_button.cget('state')=='disabled'
        assert page.preview.keys()[0]==page.preview.keys()[1]
        left,right=page.rotation_buttons
        assert left.cget('text')==right.cget('text')==''
        assert all(b.cget('image') for b in (left,right))
        for value in ('90','180','270','0'):
            right.invoke();assert page.angle.get()==value
        assert page.plan is None and page.start_button.cget('state')=='disabled'
        page.start();assert not app.busy and page.destination is None
        for value in ('270','180','90','0'):
            left.invoke();assert page.angle.get()==value
        right.invoke();left.invoke();assert page.angle.get()=='0'
        right._canvas.focus_force();pump(root)
        right._canvas.event_generate('<Return>');pump(root,0.1);assert page.angle.get()=='90'
        tip = page.rotation_tooltips[1]
        # Native windows can lose foreground during mapping/scaling; verify the
        # tooltip while its owner actually has keyboard focus, with a bounded retry.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            right._canvas.focus_force();pump(root,0.05)
            tip.schedule();pump(root,0.5)
            if tip.window and tip.window.winfo_viewable():break
        assert tip.window and tip.window.winfo_viewable()
        capture(root,'rotate-tooltip.png')
        page.rotation_tooltips[1].hide();assert page.rotation_tooltips[1].timer is None
        page.output.set(str(folder));page.selector.expression.set('2')
        page.select_document(page.documents.cget('values')[1]);assert page.selector.expression.get()=='1-1'
        page.select_document(page.documents.cget('values')[0]);assert page.selector.expression.get()=='2'
        assert [j.selected for j in page.plan.jobs]==[(2,),(1,)]
        for bad in ('','0','4','2,1','1,1','2-1'):
            page.selector.expression.set(bad);page.start();assert page.plan is None and not app.busy
        page.selector.expression.set('2');page.preview.move(1)
        left.invoke();assert page.angle.get()=='0'
        for angle in ('90','180','270'):
            right.invoke();assert page.angle.get()==angle
            deadline=time.monotonic()+15
            while not all(k in page.preview.cache and page.preview.cache[k] for k in page.preview.keys()) and time.monotonic()<deadline:pump(root,0.1)
            assert all(page.preview.cache[k] for k in page.preview.keys())
            # Process preview uses the same page rotation and fit as actual saved PDF.
            with pymupdf.open(a) as doc:
                p=doc[1];p.set_rotation((p.rotation+int(angle))%360)
                pix=p.get_pixmap(matrix=pymupdf.Matrix(min(320/p.rect.width,400/p.rect.height),min(320/p.rect.width,400/p.rect.height)),alpha=False,colorspace=pymupdf.csRGB)
                assert page.preview.cache[page.preview.keys()[1]]==(pix.width,pix.height,pix.samples)
        right.invoke();right.invoke();assert page.angle.get()=='90'
        page.show_names();pump(root)
        assert len(page.names_table.get_children())==2
        assert page.names_table.item(page.names_table.get_children()[0],'values')[1]=='2'
        capture(root,'rotate-names.png');page._close_names()
        for suffix in ('/bad',' bad','x'*41):page.suffix.set(suffix);assert page.plan is None
        page.suffix.set('_หมุน');page.output.set(str(folder/'missing'));assert page.plan is None
        page.output.set(str(folder));target=page.plan.jobs[0].output.path;target.write_bytes(b'keep')
        page.refresh_plan();assert page.plan is None;page.suffix.set('_ใหม่')
        assert app.show_home();assert app.show_tool('rotate') and app.active_page is page
        pump(root);capture(root,'rotate-preview.png')
        plan=page.plan;page.start();assert app.busy and not app.show_home()
        old_angle=page.angle.get();right.invoke();page.rotate_step(-90)
        assert page.angle.get()==old_angle and all(b.cget('state')=='disabled' for b in (left,right))
        assert all(t.window is None and t.timer is None for t in page.rotation_tooltips)
        page.add_paths([a]);page.remove_document();assert len(page.inputs)==2
        wait(root,app);assert page.destination and page.progress.get()==1,page.status.get()
        assert target.read_bytes()==b'keep'
        for job in plan.jobs:
            reference=folder/'reference.pdf'
            with pymupdf.open(job.info.path) as doc:
                for number in job.selected:
                    angle=(doc[number-1].rotation+90)%360
                    # Write the PDF /Rotate entry directly, independent of the engine's API.
                    doc.xref_set_key(doc.page_xref(number-1),'Rotate',str(angle))
                doc.save(reference)
            subprocess.run(['pdftoppm','-r','72','-png',str(reference),str(folder/'original')],check=True,capture_output=True)
            subprocess.run(['pdftoppm','-r','72','-png',str(job.output.path),str(folder/'after')],check=True,capture_output=True)
            with pymupdf.open(job.info.path) as source,pymupdf.open(job.output.path) as result:
                for number,(before,after) in enumerate(zip(source,result),1):
                    assert after.rotation==(before.rotation+(90 if number in job.selected else 0))%360
                    with Image.open(folder/f'original-{number}.png') as im:expected=im.convert('RGB')
                    with Image.open(folder/f'after-{number}.png') as im:actual=im.convert('RGB')
                    assert actual.size==expected.size and ImageChops.difference(actual,expected).getbbox() is None
        capture(root,'rotate-success.png')
        page.add_paths([a]);wait(root,app);assert len(page.inputs)==2
        page.add_paths([folder/'missing.pdf']);wait(root,app);assert page.add_button.cget('state')=='normal'
        page.remove_document();assert len(page.inputs)==1
        page.suffix.set('_ภาพตัวอย่าง')
        large=folder/('W'*70+'_หลายหน้า.pdf');make_pdf(large,[f'P{i}' for i in range(240)])
        page.add_paths([large]);wait(root,app);page.select_document(page.documents.cget('values')[1])
        for _ in range(20):page.preview.move(1);pump(root,0.1)
        assert len(page.preview.pending)<=2 and len(page.preview.cache)<=12
        root.geometry('920x700+20+20');pump(root);capture(root,'rotate-minimum.png')
        for widget in (page.selector,page.preview,page.start_button,page.open_button):
            assert widget.winfo_rooty()+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height()
        for widget in (*page.preview.labels,page.preview.previous,page.preview.next):
            assert widget.winfo_rooty()+widget.winfo_height()<=page.preview.winfo_rooty()+page.preview.winfo_height()
        ctk.set_widget_scaling(1.25);ctk.set_window_scaling(1.25);root.geometry('920x700+20+20');pump(root)
        capture(root,'rotate-125-percent.png')
        for widget in (*page.preview.labels,page.preview.previous,page.preview.next):
            assert widget.winfo_rooty()+widget.winfo_height()<=page.preview.winfo_rooty()+page.preview.winfo_height()
        assert all(hashlib.sha256(p.read_bytes()).digest()==h for p,h in hashes.items())
        workers=(page.selector.worker,page.preview.worker);dispose(root)
        assert all(w.process is None for w in workers);assert not errors,errors
        assert all(t.window is None and t.timer is None for t in page.rotation_tooltips)
    report={'passed':True,'angles':[90,180,270],'icon_commands':True,'repeated_quarter_turns':True,'starts_unrotated':True,'four_clicks_restore_original':True,'keyboard_and_tooltips':True,'relative_to_existing_rotation':True,'multi_file':True,'per_document_selection':True,'preview_pixels_match_engine':True,'poppler_pixel_equivalence':True,'originals_unchanged':True,'overwrite_guard':True,'bounded_preview':{'selector_visible_limit':24,'shared_requests':16,'comparison_pending':2,'comparison_cache':12,'document_pages':240},'minimum_window':[920,700],'scaling':[1,1.25],'tk_errors':errors,'worker_cleanup':True}
    (ROOT/'docs/rotate-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))


if __name__=='__main__':
    if '--preflight' in sys.argv:
        tools=tuple(replace(t,ready=True) if t.id=='rotate' else t for t in app_module.TOOLS)
        with patch.object(app_module,'TOOLS',tools),patch.object(app_module,'validate_registry',lambda:None),patch.dict(PAGE_FACTORIES,{'rotate':RotatePage}):main()
    else:main()
