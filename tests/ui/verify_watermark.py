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
from pdf_lover.features.watermark.service import stamp_page
from tests.unit.test_pdf_merge import make_pdf
from verify_merge import pump,capture,dispose
from verify_split import wait
from verify_order import native_focus


def main():
    errors=[]
    ctk.set_appearance_mode('light')
    with tempfile.TemporaryDirectory(prefix='number-ui-') as sandbox:
        folder=Path(sandbox);source=folder/'ไทย.pdf'
        make_pdf(source,[f'Original {i}' for i in range(4)],width=400,height=600,field='KEEP')
        with pymupdf.open(source) as doc:
            for i,page in enumerate(doc):
                if i==3:page.set_mediabox((0,0,500,700))
                page.set_cropbox((20,30,480,650) if i==3 else (20,30,380,550));page.set_rotation(i*90)
            doc.save(folder/'fixture.pdf')
        source=folder/'fixture.pdf';digest=hashlib.sha256(source.read_bytes()).hexdigest()
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(1)
            root=ctk.CTk();root.report_callback_exception=lambda k,v,t:errors.append(str(v))
            app=App(root);root.geometry('920x700+20+20');app.show_tool('watermark')
            page=app.active_page;page.add_paths([source]);wait(root,app)
            page.output.set(str(folder));page.prefix.set(f'out-{scale}')
            page.watermark_text.set('ไทย English');page.watermark_size.set('24')
            page.watermark_angle.set('30');page.selector.expression.set('1,3-4')
            page.show_view('preview');pump(root,.3)
            assert page.plan and page.plan.selected==(1,3,4)
            assert page.preview.winfo_height()>200
            assert page.start_button.winfo_rooty()+page.start_button.winfo_height() <= root.winfo_rooty()+root.winfo_height()
            root.lift();root.focus_force()
            for target in page.review_focus:
                deadline=time.monotonic()+3
                while root.focus_get()!=target and time.monotonic()<deadline:
                    root.lift();root.focus_force();target.focus_force();pump(root,.05)
                assert root.focus_get()==target
                pump(root,.03)
                canvas=page.review_rail._parent_canvas
                assert target.winfo_rooty() >= canvas.winfo_rooty()-2
                assert target.winfo_rooty()+target.winfo_height() <= canvas.winfo_rooty()+canvas.winfo_height()+2
            page.selector.canvas.focus_force();pump(root,.05)
            page.selector.canvas.event_generate('<KeyPress>',keysym='Home');pump(root,.05)
            page.review_rail._parent_canvas.yview_moveto(0)
            for number in page.plan.selected:
                page.preview.page=number;page.preview.render()
                deadline=time.monotonic()+20
                while not all(page.preview.cache.get(k) for k in page.preview.keys()) and time.monotonic()<deadline:pump(root,.05)
                assert all(page.preview.cache.get(k) for k in page.preview.keys()),page.status.get()
                key=page.preview.keys()[1]
                with pymupdf.open(source) as doc:
                    p=doc[number-1];stamp_page(p,key[8]);factor=min(320/p.rect.width,400/p.rect.height)
                    pix=p.get_pixmap(matrix=pymupdf.Matrix(factor,factor),colorspace=pymupdf.csRGB,alpha=False)
                    assert page.preview.cache[key]==(pix.width,pix.height,pix.samples)
            capture(root,f'watermark-{scale}.png')
            # Stale-setting keys are replaced and hidden resources are released.
            old=page.preview.keys()[1];page.watermark_position.set('bottom-center');pump(root,.1)
            assert old not in page.preview.worker.required
            page.watermark_color.set('bad');assert page.plan is None
            page.watermark_color.set('#003366');assert page.plan
            entered=threading.Event()
            def blocked(plan,progress=None,cancel=None):
                entered.set();cancel.wait(5);checkpoint(cancel)
            with patch.object(page,'export',blocked):
                native_focus(root,root)
                root.event_generate('<Control-Return>');pump(root,.1)
                assert entered.is_set(),'Ctrl+Enter did not start watermark'
                page.request_cancel();wait(root,app)
            assert not app.busy and not page.plan.outputs[0].path.exists()
            plan=page.plan;page.start();wait(root,app)
            target=plan.outputs[0].path;assert target.exists(),page.status.get()
            with pymupdf.open(target) as result,pymupdf.open(source) as original:
                for number in plan.selected:
                    assert 'ไทย English' in result[number-1].get_text()
                    expected=original[number-1];stamp_page(expected,plan.settings)
                    assert result[number-1].get_pixmap().samples==expected.get_pixmap().samples
                assert result[1].get_pixmap().samples==original[1].get_pixmap().samples
            # Poppler reads embedded Thai independently; pixels outside overlay remain identical.
            for name,path in (('before',source),('after',target)):
                subprocess.run(['pdftoppm','-cropbox','-png','-r','72',str(path),str(folder/name)],check=True,capture_output=True)
            with Image.open(folder/'before-2.png') as a,Image.open(folder/'after-2.png') as b:assert ImageChops.difference(a,b).getbbox() is None
            for i in (1,3,4):
                with Image.open(folder/f'before-{i}.png') as a,Image.open(folder/f'after-{i}.png') as b:
                    assert ImageChops.difference(a,b).getbbox() is not None
                    assert ImageChops.difference(a.crop((0,0,a.width,a.height-160)),b.crop((0,0,b.width,b.height-160))).getbbox() is None, (i,a.size,ImageChops.difference(a,b).getbbox())
            fonts=subprocess.run(['pdffonts',str(target)],check=True,capture_output=True,text=True).stdout
            assert any('NotoSansThai' in line.replace(' ','') and 'yes' in line for line in fonts.splitlines()),fonts
            extracted=subprocess.run(['pdftotext','-raw',str(target),'-'],check=True,capture_output=True,encoding='utf-8').stdout
            assert 'ไทย' in extracted and 'English' in extracted,repr(extracted)
            # Independently render the same in-memory placement saved as a PDF.
            with pymupdf.open(source) as expected:
                for number in plan.selected:stamp_page(expected[number-1],plan.settings)
                expected.save(folder/'expected.pdf')
            subprocess.run(['pdftoppm','-cropbox','-png','-r','72',str(folder/'expected.pdf'),str(folder/'expected')],check=True,capture_output=True)
            for number in range(1,5):
                with Image.open(folder/f'expected-{number}.png') as a,Image.open(folder/f'after-{number}.png') as b:
                    assert ImageChops.difference(a,b).getbbox() is None
            # Image import is asynchronous, preserves alpha, and reuses the same preview.
            image=folder/'透明.png';Image.new('RGBA',(200,100),(255,0,0,128)).save(image)
            page.prefix.set(f'image-{scale}');page.add_image(image);wait(root,app)
            assert page.image_info and page.watermark_kind.get()=='image' and page.plan,page.status.get()
            page.watermark_position.set('center');page.watermark_width.set('25');page.watermark_opacity.set('50')
            page.preview.page=1;page.preview.render()
            deadline=time.monotonic()+20
            while not all(page.preview.cache.get(k) for k in page.preview.keys()) and time.monotonic()<deadline:pump(root,.05)
            assert all(page.preview.cache.get(k) for k in page.preview.keys())
            image_plan=page.plan;page.start();wait(root,app)
            with pymupdf.open(image_plan.outputs[0].path) as after,pymupdf.open(source) as expected:
                stamp_page(expected[0],image_plan.settings)
                expected.save(folder/'image-expected.pdf')
                with pymupdf.open(folder/'image-expected.pdf') as saved:
                    assert after[0].get_pixmap().samples==saved[0].get_pixmap().samples
                key=page.preview.keys()[1]
                factor=min(320/after[0].rect.width,400/after[0].rect.height)
                pix=after[0].get_pixmap(matrix=pymupdf.Matrix(factor,factor),colorspace=pymupdf.csRGB,alpha=False)
                assert page.preview.cache[key]==(pix.width,pix.height,pix.samples)
                assert after[0].get_images()[0][1]>0
            capture(root,f'watermark-image-{scale}.png')
            app.show_home();assert app.preview_coordinator.process is None and not page.preview.cache
            app.show_tool('watermark');assert page.selector.expression.get()=='1,3-4'
            dispose(root)
        assert digest==hashlib.sha256(source.read_bytes()).hexdigest()
        assert not errors,errors
    report={'passed':True,'version':'1.14.0','scaling':[1,1.25],'window':[920,700],
        'preview_matches_output':True,'poppler_unchanged_regions':True,'thai_embedded':True,
        'rotations':[0,90,180,270],'cropbox':True,'cancel_retry':True,'source_unchanged':True,
        'limitations':['Windows10 development host; no physical4GB/HDD or Windows11 certification','Poppler independent renderer; another physical computer not used']}
    (ROOT/'docs/watermark-verification-1.14.0.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
