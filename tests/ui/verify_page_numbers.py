"""Native numbering/preview, keyboard/scaling, cancellation and Poppler evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/ui')]
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageChops
from pdf_lover.app import App
from pdf_lover.core.cancellation import checkpoint
from pdf_lover.features.page_numbers.service import stamp_page, label_for
from tests.unit.test_pdf_merge import make_pdf
from verify_merge import pump,capture,dispose
from verify_split import wait


def main():
    errors=[]
    ctk.set_appearance_mode('light')
    with tempfile.TemporaryDirectory(prefix='number-ui-') as sandbox:
        folder=Path(sandbox);source=folder/'ไทย.pdf'
        make_pdf(source,[f'Original {i}' for i in range(4)],width=400,height=600,field='KEEP')
        with pymupdf.open(source) as doc:
            for i,page in enumerate(doc):
                if i==3:page.set_mediabox((0,0,500,700))
                page.set_cropbox((20,30,380,550));page.set_rotation(i*90)
            doc.save(folder/'fixture.pdf')
        source=folder/'fixture.pdf';digest=hashlib.sha256(source.read_bytes()).hexdigest()
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(1)
            root=ctk.CTk();root.report_callback_exception=lambda k,v,t:errors.append(str(v))
            app=App(root);root.geometry('920x700+20+20');app.show_tool('page-numbers')
            page=app.active_page;page.add_paths([source]);wait(root,app)
            page.output.set(str(folder));page.prefix.set(f'out-{scale}')
            page.number_format.set('page');page.thai_digits.set(True);page.number_start.set('5')
            page.number_sequence.set('selected');page.selector.expression.set('1,3-4')
            page.show_view('preview');pump(root,.3)
            assert page.plan and page.plan.selected==(1,3,4)
            assert page.preview.winfo_height()>200
            assert page.start_button.winfo_rooty()+page.start_button.winfo_height() <= root.winfo_rooty()+root.winfo_height()
            root.lift();root.focus_force()
            for target in page.review_focus:
                target.focus_force();pump(root,.03)
                canvas=page.review_rail._parent_canvas
                assert target.winfo_rooty() >= canvas.winfo_rooty()-2
                assert target.winfo_rooty()+target.winfo_height() <= canvas.winfo_rooty()+canvas.winfo_height()+2
            page.review_rail._parent_canvas.yview_moveto(0)
            for number in page.plan.selected:
                page.preview.page=number;page.preview.render()
                deadline=time.monotonic()+20
                while not all(page.preview.cache.get(k) for k in page.preview.keys()) and time.monotonic()<deadline:pump(root,.05)
                assert all(page.preview.cache.get(k) for k in page.preview.keys()),page.status.get()
                key=page.preview.keys()[1]
                with pymupdf.open(source) as doc:
                    p=doc[number-1];stamp_page(p,key[8],key[9]);factor=min(320/p.rect.width,400/p.rect.height)
                    pix=p.get_pixmap(matrix=pymupdf.Matrix(factor,factor),colorspace=pymupdf.csRGB,alpha=False)
                    assert page.preview.cache[key]==(pix.width,pix.height,pix.samples)
            capture(root,f'page-numbers-{scale}.png')
            # Stale-setting keys are replaced and hidden resources are released.
            old=page.preview.keys()[1];page.number_format.set('total');pump(root,.1)
            assert old not in page.preview.worker.required
            page.number_color.set('bad');assert page.plan is None
            page.number_color.set('#003366');assert page.plan
            entered=threading.Event()
            def blocked(plan,progress=None,cancel=None):
                entered.set();cancel.wait(5);checkpoint(cancel)
            with patch.object(page,'export',blocked):
                page.start();pump(root,.1);assert entered.is_set();page.request_cancel();wait(root,app)
            assert not app.busy and not page.plan.outputs[0].path.exists()
            plan=page.plan;page.start();wait(root,app)
            target=plan.outputs[0].path;assert target.exists(),page.status.get()
            with pymupdf.open(target) as result,pymupdf.open(source) as original:
                for number in plan.selected:
                    assert label_for(plan.settings,number,plan.selected.index(number),4,3) in result[number-1].get_text()
                    expected=original[number-1];stamp_page(expected,label_for(plan.settings,number,plan.selected.index(number),4,3),plan.settings)
                    assert result[number-1].get_pixmap().samples==expected.get_pixmap().samples
                assert result[1].get_pixmap().samples==original[1].get_pixmap().samples
            # Poppler reads embedded Thai independently; pixels outside overlay remain identical.
            for name,path in (('before',source),('after',target)):
                subprocess.run(['pdftoppm','-cropbox','-png','-r','72',str(path),str(folder/name)],check=True,capture_output=True)
            with Image.open(folder/'before-2.png') as a,Image.open(folder/'after-2.png') as b:assert ImageChops.difference(a,b).getbbox() is None
            for i in (1,3,4):
                with Image.open(folder/f'before-{i}.png') as a,Image.open(folder/f'after-{i}.png') as b:
                    assert ImageChops.difference(a,b).getbbox() is not None
                    assert ImageChops.difference(a.crop((0,0,a.width,a.height-65)),b.crop((0,0,b.width,b.height-65))).getbbox() is None, (i,a.size,ImageChops.difference(a,b).getbbox())
            subprocess.run(['pdffonts',str(target)],check=True,capture_output=True)
            app.show_home();assert app.preview_coordinator.process is None and not page.preview.cache
            app.show_tool('page-numbers');assert page.selector.expression.get()=='1,3-4'
            dispose(root)
        assert digest==hashlib.sha256(source.read_bytes()).hexdigest()
        assert not errors,errors
    report={'passed':True,'version':'1.12.0','scaling':[1,1.25],'window':[920,700],
        'preview_matches_output':True,'poppler_unchanged_regions':True,'thai_embedded':True,
        'rotations':[0,90,180,270],'cropbox':True,'cancel_retry':True,'source_unchanged':True,
        'limitations':['Windows10 development host; no physical4GB/HDD or Windows11 certification','Poppler independent renderer; another physical computer not used']}
    (ROOT/'docs/page-numbers-verification-1.12.0.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
