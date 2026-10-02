"""Real native workbench geometry, states and visual evidence at desktop scales."""
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/ui')]
import customtkinter as ctk
import pymupdf
from pdf_lover.app import App
from pdf_lover.version import VERSION
from verify_merge import pump,capture
from verify_split import wait


def contained(widget,root):
    x,y=widget.winfo_rootx(),widget.winfo_rooty()
    assert widget.winfo_ismapped(),str(widget)
    assert x>=root.winfo_rootx() and y>=root.winfo_rooty(),str(widget)
    assert x+widget.winfo_width()<=root.winfo_rootx()+root.winfo_width()+2,str(widget)
    assert y+widget.winfo_height()<=root.winfo_rooty()+root.winfo_height()+2,str(widget)


def main():
    errors=[];measurements=[]
    ctk.set_appearance_mode('light');ctk.set_widget_scaling(1);ctk.set_window_scaling(1)
    with tempfile.TemporaryDirectory() as tmp:
        paths=[]
        for index in (1,2):
            path=Path(tmp)/f'รายงานประจำเดือน {index}.pdf'
            with pymupdf.open() as doc:
                for number in range(1,13):
                    p=doc.new_page();p.insert_text((55,65),f'MONTHLY REPORT / {index}',fontsize=24)
                    p.insert_text((55,110),f'Page {number} / Document review',fontsize=18)
                    for y in range(155,650,32):p.draw_line((55,y),(540,y),color=(.7,.75,.8))
                    p.draw_rect((55,190,260,360),color=(.1,.3,.6),fill=(.9,.94,.98))
                doc.save(path)
            paths.append(path)
        root=ctk.CTk();root.report_callback_exception=lambda k,v,t:errors.append(str(v));app=App(root)
        for scale in (1,1.25):
            ctk.set_widget_scaling(scale);ctk.set_window_scaling(scale)
            for size in ('920x700','1080x780','1440x900'):
                root.geometry(size+'+0+0');pump(root,1)
                app.show_home();app.home.reset_filters();pump(root,.3)
                assert len(app.home.visible_tools)==6 and all(t.ready for t in app.home.visible_tools)
                contained(app.home.search_entry,root);contained(app.home.ready_button,root)
                if size=='920x700':capture(root,f'after-home-{scale}.png')
                for tool in ('pdf-png','merge','split','extract-pages','delete-pages','rotate'):
                    app.show_tool(tool);page=app.active_page;pump(root,.2)
                    if scale==1 and size=='920x700':
                        capture(root,f'empty-{tool}.png')
                        page.add_paths(paths if tool in ('pdf-png','merge','rotate') else paths[:1]);wait(root,app)
                        if tool=='delete-pages':page.selector.expression.set('2,4')
                        if tool=='rotate':page.rotate_step(90)
                    pump(root,.5)
                    for w in (page.add_button,page.start_button,page.open_button):contained(w,root)
                    if tool=='merge':
                        assert page.files and not page.empty.winfo_ismapped(), 'Empty state overlays loaded merge cards'
                    if hasattr(page,'selector'):
                        selector=page.selector;contained(selector.canvas,root)
                        assert selector.canvas.winfo_height()/scale>=180,(tool,size,selector.canvas.winfo_height()/scale)
                        assert selector.canvas.xview()==(0.,1.) and len(selector.visible)<=24
                        measurements.append({'tool':tool,'size':size,'scale':scale,'viewport_height':round(selector.canvas.winfo_height()/scale,1),'columns':selector.columns})
                    if hasattr(page,'results'):
                        contained(page.results,root)
                        assert page.results.winfo_height()/scale>=85,(tool,size,page.results.winfo_height()/scale)
                    if tool=='split':
                        page.mode.set('chunks');pump(root,.1);contained(page.results,root)
                        page.mode.set('ranges');page.chunk_size.set('2')
                    if size=='920x700':
                        if tool=='rotate':
                            deadline=__import__('time').monotonic()+10
                            while not all(k in page.preview.cache for k in page.preview.keys()) and __import__('time').monotonic()<deadline:pump(root,.1)
                            assert page.preview.labels[1].winfo_ismapped()
                            assert max(page.preview.images[page.preview.keys()[1]].cget('size'))>=190
                            page.preview.tabs[0].invoke();assert page.preview.shown==0
                            page.preview.tabs[1].invoke()
                        capture(root,f'after-{tool}-{scale}.png')
        app.show_tool('delete-pages');page=app.active_page;page.selector.expression.set('12-1')
        assert page.plan is None and page.start_button.cget('state')=='disabled'
        capture(root,'redesign-error.png')
        app.show_home();assert not app.preview_coordinator.process
        assert all(not p.selector.images for p in app.views.values() if hasattr(p,'selector'))
        app.close();assert not errors,errors
    report={'version':VERSION,'passed':True,'scaling':[1,1.25],'window_sizes':[[920,700],[1080,780],[1440,900]],
            'all_six_tools':True,'ready_home_default':True,'fixed_save_controls_visible':True,
            'result_table_min_height':85,'selector_min_height':180,'comparison_tabs':True,
            'empty_loaded_error_disabled_states':True,'cleanup':True,'tk_errors':errors,'measurements':measurements}
    (ROOT/f'docs/workbench-verification-{VERSION}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
