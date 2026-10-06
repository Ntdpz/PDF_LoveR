"""Native vertical page grid, latest-request pixels, input and bounded resources."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/ui')]
import customtkinter as ctk
import pymupdf
from PIL import Image
from pdf_lover.app import App
from pdf_lover.version import VERSION
from verify_merge import pump, capture
from verify_split import wait
from verify_order import native_focus


def settled(root, selector):
    end = time.monotonic()+20
    while time.monotonic()<end:
        pump(root,.05)
        if selector.worker.required and all(selector.cache.get(k) for k in selector.worker.required):return
    raise AssertionError('Visible page previews did not settle')


def main():
    ctk.set_appearance_mode('light');ctk.set_widget_scaling(1);ctk.set_window_scaling(1)
    errors=[]
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);small=folder/'เอกสาร 8 หน้า.pdf';large=folder/'1000 pages.pdf'
        for path,count in ((small,8),(large,1000)):
            with pymupdf.open() as doc:
                for number in range(1,count+1):
                    page=doc.new_page();page.insert_text((72,72),f'Document page {number}',fontsize=24)
                    page.draw_rect((72,110,360,360),color=(.1,.3,.8))
                doc.save(path)
        original=hashlib.sha256(small.read_bytes()).hexdigest()
        root=ctk.CTk();root.report_callback_exception=lambda kind,value,trace:errors.append(str(value))
        app=App(root);app.show_tool('delete-pages');root.geometry('1840x1000+0+0');pump(root)
        page=app.active_page;page.add_paths([small]);wait(root,app);selector=page.selector
        selector.expression.set('1-3');settled(root,selector)
        assert selector.columns==4 and len(selector.visible)==8
        assert len({box[1] for box in selector.visible.values()})==2
        assert selector.canvas.xview()==(0.,1.)
        assert 'เลื่อน' not in selector.counter.cget('text')
        # Capture the native window, so an unrelated foreground app cannot enter evidence.
        out=ROOT/'build-verification/ui';out.mkdir(parents=True,exist_ok=True)
        capture(root,'selector-workbench.png')
        x,y=selector.winfo_rootx()-root.winfo_rootx(),selector.winfo_rooty()-root.winfo_rooty()
        with Image.open(out/'selector-workbench.png') as shot:
            assert shot.size==(root.winfo_width(),root.winfo_height())
            shot.crop((x,y,x+selector.winfo_width(),y+selector.winfo_height())).save(out/'selector-vertical.png')
        box=selector.visible[8];x=int((box[0]+box[2])/2);y=int((box[1]+box[3])/2-selector.canvas.canvasy(0))
        selector.canvas.event_generate('<Motion>',x=x,y=y);pump(root,.05);assert selector.hovered==8
        selector.canvas.event_generate('<ButtonPress-1>',x=x,y=y);assert selector.pressed==8
        selector.canvas.event_generate('<ButtonRelease-1>',x=x,y=y);assert selector.expression.get()=='1-3,8'
        native_focus(root,selector.canvas)
        selector.canvas.event_generate('<Home>');selector.canvas.event_generate('<Right>')
        selector.canvas.event_generate('<space>');assert selector.expression.get()=='1,3,8'
        called=[];start=page.start;page.start=lambda:called.append(True)
        selector.canvas.event_generate('<Control-Return>');pump(root,.05);page.start=start
        assert called and selector.expression.get()=='1,3,8', 'Grid consumed the global save shortcut'
        selector.expression.set('8-1');assert selector.entry.cget('border_color')==__import__('pdf_lover.ui.theme',fromlist=['COLORS']).COLORS['error']
        selector.expression.set('1-3');page.add_paths([large]);wait(root,app);settled(root,selector)
        assert len(selector.visible)<=24 and len(selector.canvas.find_all())<=24*4
        before=selector.offset;selector.canvas.event_generate('<MouseWheel>',delta=-120);pump(root,.1)
        assert selector.canvas.canvasy(0)>0
        for _ in range(120):selector.canvas.event_generate('<MouseWheel>',delta=-120)
        pump(root,.2);settled(root,selector)
        assert selector.offset>before and len(selector.pending)<=16 and selector.cache.resident_bytes<=6*1048576
        native_focus(root,selector.canvas)
        assert selector.canvas.focus_get() is selector.canvas
        selector.canvas.event_generate('<End>');pump(root,.1);settled(root,selector)
        assert 1000 in selector.visible and selector.focused==1000
        for key in selector.worker.required:
            with pymupdf.open(large) as doc:
                p=doc[key[3]];factor=min(180/p.rect.width,200/p.rect.height)
                pix=p.get_pixmap(matrix=pymupdf.Matrix(factor,factor),alpha=False,colorspace=pymupdf.csRGB)
                assert selector.cache[key]==(pix.width,pix.height,pix.samples)
        selector.expression.set('1,1000');selector.set_enabled(False)
        selector.canvas.event_generate('<Return>');selector.canvas.event_generate('<Home>');assert selector.expression.get()=='1,1000'
        selector.set_enabled(True);last=selector.offset
        app.show_home();assert not selector.cache and not selector.images and selector.draw_timer is None
        assert app.preview_coordinator.process is None
        app.show_tool('delete-pages');pump(root,.1);assert selector.offset==last and selector.expression.get()=='1,1000'
        for tool in ('split','extract-pages','delete-pages','rotate'):
            app.show_tool(tool);p=app.active_page
            if tool!='delete-pages':p.add_paths([small]);wait(root,app)
            for scaling in (1,1.25):
                ctk.set_widget_scaling(scaling);ctk.set_window_scaling(scaling);root.geometry('920x700+0+0');pump(root,.3)
                s=p.selector;native_focus(root,s.canvas);pump(root,.1)
                assert 1<=s.columns<=4 and s.canvas.xview()==(0.,1.)
                assert s.counter.winfo_rooty()+s.counter.winfo_height()<=s.winfo_rooty()+s.winfo_height()
                assert s.canvas.winfo_rooty()+s.canvas.winfo_height()<=s.counter.winfo_rooty(), (tool,scaling,s.canvas.winfo_rooty(),s.canvas.winfo_height(),s.counter.winfo_rooty(),s.counter.winfo_ismapped())
        assert hashlib.sha256(small.read_bytes()).hexdigest()==original
        app.close();assert not errors,errors
    report={'version':VERSION,'passed':True,'layout':'responsive vertical viewport grid','eight_pages_in_two_rows':True,
            'vertical_mouse_wheel':True,'keyboard_navigation_and_selection':True,'global_save_shortcut_preserved':True,'all_four_page_tools':True,
            'native_states':['default','hover','focus','pressed','disabled','loading','error','selected'],
            'document_pages':1000,'visible_card_limit':24,'shared_request_limit':16,'cache_limit':32,'cache_bytes':6*1048576,
            'latest_pixels_match':True,'retained_scroll_and_selection':True,'source_unchanged':True,
            'scaling':[1,1.25],'minimum_window':[920,700],'tk_errors':errors,'cleanup':True}
    (ROOT/f'docs/selector-verification-{VERSION}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
