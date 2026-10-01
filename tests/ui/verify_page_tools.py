"""Native extract/delete workbench, bounded preview and independent Poppler check."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT),str(ROOT/'tests/ui'),str(ROOT/'tests/unit')]
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageChops
import pdf_lover.app as app_module
from pdf_lover.features.registry import PAGE_FACTORIES
from pdf_lover.features.extract.page import ExtractPage
from pdf_lover.features.delete_pages.page import DeletePagesPage
from pdf_lover.diagnostics.self_test import native_drop
from test_pdf_merge import make_pdf
from verify_merge import pump, capture, dispose
from verify_split import wait


def main():
    ctk.set_appearance_mode('light');ctk.set_widget_scaling(1);ctk.set_window_scaling(1)
    errors=[];verified=[]
    with tempfile.TemporaryDirectory(prefix='pdf-page-tools-ui-') as sandbox:
        folder=Path(sandbox);source=folder/'ต้นฉบับตัวอย่าง.pdf'
        make_pdf(source,[f'PAGE {i}' for i in range(1,11)],field='Value')
        before=hashlib.sha256(source.read_bytes()).hexdigest()
        root=ctk.CTk();root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
        app=app_module.App(root);root.geometry('1080x780+40+40');pump(root)
        for tool,selected,expected in [('extract-pages','1-3,5,8-10',(1,2,3,5,8,9,10)),('delete-pages','3-4,6-7',(1,2,5,8,9,10))]:
            assert app.show_tool(tool);page=app.active_page
            capture(root,tool+'-empty.png')
            page.start();assert page.plan is None and not app.busy
            native_drop(root,[source]);assert app.file_drop.pending==[source]
            pump(root,0.05);wait(root,app)
            assert page.info.page_count==10
            if page.DELETE:assert page.plan is None and page.selector.expression.get()==''
            page.output.set(str(folder));page.selector.expression.set(selected)
            assert page.plan.outputs[0].pages==expected
            assert [page.results.item(r,'values')[0] for r in page.results.get_children()]==[f'{i} (เดิม {p})' for i,p in enumerate(expected,1)]
            deadline=time.monotonic()+15
            while len(page.selector.cache)<4 and time.monotonic()<deadline:pump(root,0.1)
            assert len(page.selector.cache)==4 and all(page.selector.cache.values())
            was_selected = 2 in page.selector.selection()
            page.selector.toggle(2);assert (2 in page.selector.selection()) != was_selected
            page.selector.none_button.invoke();assert page.plan is None
            page.selector.all_button.invoke()
            assert (page.plan is None)==page.DELETE
            for invalid in ('0','11','4-2','3,2','1-3,3','1,,2'):
                page.selector.expression.set(invalid);page.start();assert page.plan is None and not app.busy
            page.selector.expression.set(selected)
            for prefix in ('CON','bad/name',''):
                page.prefix.set(prefix);assert page.plan is None
            page.prefix.set(tool);page.output.set(str(folder/'missing'));assert page.plan is None
            page.output.set(str(folder))
            existing=page.plan.outputs[0].path;existing.write_bytes(b'keep')
            page.refresh_plan();assert page.plan is None
            assert existing.read_bytes()==b'keep';page.prefix.set(tool+'-ใหม่')
            retained=page;assert app.show_home();assert app.show_tool(tool) and app.active_page is retained
            capture(root,tool+'-preview.png')
            plan=page.plan;page.start();assert app.busy and not app.show_home()
            wait(root,app);assert page.destination and page.progress.get()==1,page.status.get()
            assert page.start_button.cget('state')=='disabled'
            with pymupdf.open(plan.outputs[0].path) as result:
                assert [p.get_text().splitlines()[0] for p in result]==[f'PAGE {p}' for p in expected]
            # Independent renderer compares each saved page with its original page.
            for index,number in enumerate(expected,1):
                images=[]
                for name,pdf,pagenum in [('original',source,number),('result',plan.outputs[0].path,index)]:
                    prefix=folder/(name+str(index))
                    subprocess.run(['pdftoppm','-f',str(pagenum),'-l',str(pagenum),'-singlefile','-r','72','-png',str(pdf),str(prefix)],check=True,capture_output=True)
                    with Image.open(str(prefix)+'.png') as im:images.append(im.convert('RGB'))
                assert images[0].size==images[1].size and ImageChops.difference(*images).getbbox() is None
            capture(root,tool+'-success.png')
            if not page.DELETE:
                page.mode.set('pages');page.prefix.set('รายหน้า');plan=page.plan;page.start();wait(root,app)
                assert len(plan.outputs)==len(expected)
                for output in plan.outputs:
                    with pymupdf.open(output.path) as pdf:assert pdf.page_count==1
            page.add_paths([folder/'missing.pdf']);wait(root,app)
            assert page.info is None and page.plan is None and page.start_button.cget('state')=='disabled'
            page.add_paths([source]);wait(root,app)
            assert page.info.page_count==10
            assert hashlib.sha256(source.read_bytes()).hexdigest()==before
            verified.append({'tool':tool,'saved_original_pages':list(expected),'poppler_pixel_match':True,'existing_file_preserved':True,'source_unchanged':True})
        large=folder/'หลายหน้า.pdf';make_pdf(large,[f'PAGE {i}' for i in range(1,241)])
        for tool in ('extract-pages','delete-pages'):
            assert app.show_tool(tool);page=app.active_page;page.add_paths([large]);wait(root,app)
            page.selector.expression.set('1-239' if page.DELETE else '1-240')
            assert len(page.results.get_children())<=25
            page.selector.expression.set('1' if page.DELETE else '1-240')
            assert len(page.preview_rows()) == (239 if page.DELETE else 240)
            page.move_outputs(1);assert page.preview_offset==25
            for _ in range(6):page.selector.move(1);pump(root,0.15)
            assert len(page.selector.pending)<=4 and len(page.selector.cache)<=32
            root.geometry('920x700+20+20');pump(root)
            for widget in (page.selector,page.results,page.start_button,page.open_button,page.output_entry):
                assert widget.winfo_rootx()>=root.winfo_rootx()
                assert widget.winfo_rooty()+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height()
            capture(root,tool+'-minimum.png')
            ctk.set_widget_scaling(1.25);ctk.set_window_scaling(1.25);root.geometry('920x700+20+20');pump(root)
            capture(root,tool+'-125-percent.png')
            ctk.set_widget_scaling(1);ctk.set_window_scaling(1)
        workers=[p.selector.worker for p in app.views.values() if hasattr(p,'selector')]
        dispose(root)
        assert all(w.process is None or not w.process.is_alive() for w in workers)
        assert not errors,errors
    report={'passed':True,'tools':verified,'extract_modes':['single','pages'],'delete_all_blocked':True,'bounded_preview':{'thumbnails_visible':4,'cache':32,'table_rows':25,'document_pages':240},'native_drop':True,'busy_guard':True,'workers_closed':True,'tk_errors':errors,'minimum_window':[920,700],'scaling':[1,1.25]}
    (ROOT/'docs/page-tools-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    if '--preflight' in sys.argv:
        tools=tuple(replace(t,ready=True) if t.id in ('extract-pages','delete-pages') else t for t in app_module.TOOLS)
        with patch.object(app_module,'TOOLS',tools),patch.object(app_module,'validate_registry',lambda:None),patch.dict(PAGE_FACTORIES,{'extract-pages':ExtractPage,'delete-pages':DeletePagesPage}):main()
    else:main()
