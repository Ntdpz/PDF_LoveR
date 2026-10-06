"""Shared selection worker lifecycle with a bounded, exact numbered preview."""
import tkinter as tk
from tkinter import filedialog
import queue
import threading
from pdf_lover.core.cancellation import checkpoint, Cancelled
import customtkinter as ctk
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.features.watermark.service import WatermarkSettings, build_plan, watermark_pdf, inspect_image, POSITIONS, FONTS
from pdf_lover.core.document import DocumentError
from pdf_lover.ui.workbench import shell, save_bar, output_settings
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.page_preview import PagePreview
from pdf_lover.ui.theme import COLORS as C, SPACE as S


class WatermarkPreview(PagePreview):
    def __init__(self, parent, app):
        self.watermark_plan = None
        super().__init__(parent, app)
        self.title.configure(text='ภาพก่อน–หลังใส่ลายน้ำ')

    def keys(self):
        if not self.info:
            return ()
        base = (self.info.path, self.info.signature[3], self.info.signature[2], self.page-1, 0, 320, 400)
        plan = self.watermark_plan
        if plan and self.page in plan.selected:
            return (base, base + ('watermark', plan.settings))
        return (base, base)

    def move(self, delta):
        if self.enabled and self.watermark_plan:
            pages = self.watermark_plan.selected
            index = pages.index(self.page) if self.page in pages else 0
            self.page = pages[max(0, min(len(pages)-1, index+delta))]
            self.render()

    def render(self):
        super().render()
        if self.info and self.watermark_plan and self.page in self.watermark_plan.selected:
            plan = self.watermark_plan
            self.caption.configure(text=f'หน้าเดิม {self.page} · ลายน้ำใหม่')
            index = plan.selected.index(self.page)
            self.previous.configure(state='normal' if self.enabled and index else 'disabled')
            self.next.configure(state='normal' if self.enabled and index < len(plan.selected)-1 else 'disabled')


class WatermarkPage(SelectionPage):
    TITLE = 'ใส่ลายน้ำ PDF'
    SUFFIX = '_ลายน้ำ'
    SAVE_LABEL = 'ใส่ลายน้ำและบันทึก PDF ใหม่'
    EVENT_LIMIT = 32
    export = staticmethod(watermark_pdf)

    def __init__(self, parent, app):
        self.watermark_text = tk.StringVar(master=app.root,value='สำเนา / COPY')
        self.watermark_kind = tk.StringVar(master=app.root,value='text')
        self.watermark_font = tk.StringVar(master=app.root,value='Noto Sans Thai')
        self.watermark_size = tk.StringVar(master=app.root,value='36')
        self.watermark_color = tk.StringVar(master=app.root,value='#808080')
        self.watermark_opacity = tk.StringVar(master=app.root,value='30')
        self.watermark_angle = tk.StringVar(master=app.root,value='0')
        self.watermark_position = tk.StringVar(master=app.root,value='center')
        self.watermark_width = tk.StringVar(master=app.root,value='40')
        self.image_info = None
        self._reading_image = False
        self.view = 'select'
        super().__init__(parent, app)
        for var in self.watermark_variables:
            var.trace_add('write', self._settings_changed)

    @property
    def watermark_variables(self):
        return (self.watermark_text,self.watermark_kind,self.watermark_font,self.watermark_size,
                self.watermark_color,self.watermark_opacity,self.watermark_angle,self.watermark_position,self.watermark_width)

    def _menu(self, parent, row, title, variable, choices):
        self.label(parent, title, font=self.font_small).grid(row=row, column=0, sticky='w')
        titles = dict(choices)
        menu = ctk.CTkOptionMenu(parent, values=list(titles.values()), height=44,
            font=self.font_small, dropdown_font=self.font_small, fg_color=C['soft'], text_color=C['ink'],
            button_color=C['rule'], command=lambda text: variable.set(next(k for k,v in titles.items() if v == text)))
        menu.set(titles[variable.get()])
        menu.grid(row=row+1, column=0, sticky='ew', pady=(0,S['xs']))
        variable.trace_add('write', lambda *_: menu.set(titles[variable.get()]))
        menu._canvas.configure(takefocus=1)
        for key in ('<Return>', '<space>', '<Alt-Down>'):
            menu._canvas.bind(key, lambda _: menu._open_dropdown_menu())
        self.controls.append(menu)

    def _build(self):
        source, body, rail = shell(self, 'ลายน้ำ', 'เลือกหน้า · ตั้งลายน้ำใหม่ · ตรวจภาพ · บันทึกใหม่', scroll_review=True)
        self.masthead_title.configure(font=self.font_bold)
        self.source_label = self.label(source, 'เลือก PDF หรือวางจาก Explorer', font=self.font_bold)
        self.source_label.grid(row=0, column=0, sticky='ew')
        self.add_button = self.button(source, 'เลือก PDF…', self.add_files, width=140)
        self.add_button.grid(row=0,column=1)
        self.controls.append(self.add_button)
        self.stage = ctk.CTkFrame(body, fg_color='transparent')
        self.stage.grid(row=0,column=0,sticky='nsew')
        self.stage.grid_columnconfigure(0,weight=1)
        self.stage.grid_rowconfigure(1,weight=1)
        tabs = ctk.CTkFrame(self.stage,fg_color='transparent')
        tabs.grid(row=0,column=0,sticky='ew')
        tabs.grid_columnconfigure((0,1),weight=1)
        for index,(title,view) in enumerate((('เลือกหน้า','select'),('ตรวจลายน้ำ','preview'))):
            button = self.button(tabs,title,lambda v=view:self.show_view(v),width=110)
            button.grid(row=0,column=index,padx=S['xs'],pady=S['xs'],sticky='ew')
            self.controls.append(button)
        self.selector = PageSelector(self.stage,self.app,self._settings_changed,title='หน้าที่จะใส่ลายน้ำ',hint='ทุกหน้า หรือช่วง เช่น 1-3,5')
        self.selector.grid(row=1,column=0,sticky='nsew')
        self.preview = WatermarkPreview(self.stage,self.app)
        self.mode_buttons = []
        self.summary = self.label(rail,'',font=self.font_small,wraplength=290,justify='left')
        self.summary.grid(row=0,column=0,sticky='ew',padx=S['sm'])
        settings = ctk.CTkFrame(rail,fg_color='transparent')
        settings.grid(row=1,column=0,sticky='ew',padx=S['sm'])
        settings.grid_columnconfigure(0,weight=1)
        self._menu(settings,0,'ชนิดลายน้ำ',self.watermark_kind,(('text','ข้อความ'),('image','ภาพ PNG/JPG')))
        self._menu(settings,2,'ฟอนต์ (ฝังใน PDF)',self.watermark_font,(('Noto Sans Thai','Noto Sans Thai'),('serif','Serif + ฟอนต์ไทย')))
        self._menu(settings,4,'ตำแหน่งในหน้าที่มองเห็น',self.watermark_position,tuple(zip(POSITIONS,('บนซ้าย','บนกลาง','บนขวา','กลางซ้าย','กลาง','กลางขวา','ล่างซ้าย','ล่างกลาง','ล่างขวา'))))
        for row,title,var in ((6,'ข้อความหนึ่งบรรทัด',self.watermark_text),(8,'ขนาดข้อความ 6–144 pt',self.watermark_size),(10,'สี #RRGGBB',self.watermark_color),(12,'ความทึบ 0–100% (0 = โปร่งใส)',self.watermark_opacity),(14,'มุม −180 ถึง 180° (+ ทวนเข็ม)',self.watermark_angle),(16,'ความกว้างภาพ 1–100% ของหน้า',self.watermark_width)):
            self.label(settings,title,font=self.font_small).grid(row=row,column=0,sticky='w')
            self._entry(settings,var).grid(row=row+1,column=0,sticky='ew',pady=S['xs'])
        self.image_button=self.button(settings,'เลือกภาพ PNG/JPG…',self.choose_image)
        self.image_button.grid(row=18,column=0,sticky='ew',pady=S['xs'])
        self.controls.append(self.image_button)
        self.image_label=self.label(settings,'ยังไม่เลือกภาพ',font=self.font_small,wraplength=285)
        self.image_label.grid(row=19,column=0,sticky='ew')
        self.label(settings,'พิกัดตามหน้าที่มองเห็นหลังหมุน/CropBox\nขอบ 12 pt · ภาพรักษาสัดส่วน\nขนาดก่อนหมุน; ไม่พอดีจะแจ้งให้ปรับ',font=self.font_small,wraplength=285,justify='left').grid(row=20,column=0,sticky='w')
        output_settings(self,rail,2,self.prefix,'ชื่อ PDF ใหม่ (ไม่ใส่ .pdf)')
        save_bar(self,self.SAVE_LABEL)
        # Tab focus must reveal settings below the fold at 920x700 / 125%.
        self.review_rail = rail
        self.review_focus = []
        for control in self.controls:
            if str(control).startswith(str(rail) + '.'):
                target = getattr(control, '_entry', getattr(control, '_canvas', control))
                target.configure(takefocus=1)
                target.bind('<FocusIn>', lambda event:self._reveal_setting(event.widget), add='+')
                self.review_focus.append(target)

    def _reveal_setting(self, widget):
        canvas = self.review_rail._parent_canvas
        top, bottom = canvas.winfo_rooty(), canvas.winfo_rooty()+canvas.winfo_height()
        y, end = widget.winfo_rooty(), widget.winfo_rooty()+widget.winfo_height()
        delta = y-top-8 if y < top else end-bottom+8 if end > bottom else 0
        box = canvas.bbox('all')
        if delta and box and box[3] > 0:
            canvas.yview_moveto(max(0, (canvas.canvasy(0)+delta)/box[3]))

    def show_view(self, view):
        if self.busy:
            return
        self.view = view
        self.selector.grid_remove()
        self.preview.grid_remove()
        (self.selector if view == 'select' else self.preview).grid(row=1,column=0,sticky='nsew')
        self.selector.set_preview_active(self.page_visible and view == 'select')
        self.preview.set_preview_active(self.page_visible and view == 'preview')

    def set_active(self, active):
        super().set_active(active)
        self.selector.set_preview_active(active and self.view == 'select')
        self.preview.set_preview_active(active and self.view == 'preview')

    def choose_image(self):
        if self.busy:
            return
        path=filedialog.askopenfilename(parent=self.root,title='เลือกภาพลายน้ำ',filetypes=[('PNG/JPG','*.png *.jpg *.jpeg')])
        if path:
            self.add_image(path)

    def add_image(self,path):
        if self.busy:
            return
        self._reading_image=True
        self._lock('กำลังตรวจภาพ · ยกเลิกได้')
        threading.Thread(target=self._inspect_image,args=(path,),daemon=True).start()

    def _inspect_image(self,path):
        try:
            checkpoint(self.cancel_event)
            info=inspect_image(path)
            checkpoint(self.cancel_event)
            self.events.put(('image-ready',info))
        except Cancelled as error:
            self.events.put(('cancelled',str(error)))
        except Exception as error:
            self.events.put(('error',str(error)))

    def build_plan(self, info, directory, prefix, expression, mode):
        try:
            settings=WatermarkSettings(self.watermark_kind.get(),self.watermark_text.get(),self.watermark_font.get(),
                float(self.watermark_size.get()),self.watermark_color.get(),float(self.watermark_opacity.get())/100,
                float(self.watermark_angle.get()),self.watermark_position.get(),float(self.watermark_width.get()),self.image_info)
        except ValueError as error:
            raise DocumentError('ขนาด ความทึบ มุม และความกว้างต้องเป็นตัวเลข') from error
        return build_plan(info,directory,prefix,expression,settings)

    def render_outputs(self):
        self.preview.watermark_plan = self.plan
        self.preview.set_document(self.info)
        if self.plan and self.preview.page not in self.plan.selected:
            self.preview.page = self.plan.selected[0]
            self.preview.render()
        if self.plan:
            self.summary.configure(text=f'ใส่ลายน้ำ {len(self.plan.selected)} หน้า · เก็บทุก {self.info.page_count} หน้า\nขอบ 12 pt · ไม่เปลี่ยนขนาด/หมุนหน้าเดิม')
        self.preview.set_enabled(not self.busy)

    def _settings_changed(self, *_):
        if hasattr(self,'preview') and not self.busy:
            self.destination = None
            self.open_button.configure(state='disabled')
            self.progress.set(0)
            self.refresh_plan()

    def process_events(self):
        if self._reading_image:
            try:
                event=self.events.get_nowait()
            except queue.Empty:
                return
            self._reading_image=False
            self.busy=False
            for control in self.controls:
                control.configure(state='normal')
            self.selector.set_enabled(True)
            self.refresh_plan()
            if event[0]=='image-ready' and not self.cancel_event.is_set():
                self.image_info=event[1]
                self.image_label.configure(text=self.shorten(self.image_info.path.name,28))
                self.watermark_kind.set('image')
                self.refresh_plan()
            else:
                self.status.set(event[1] if event[0]!='image-ready' else 'ยกเลิกการอ่านภาพแล้ว')
            return
        super().process_events()
        self.preview.process_events()
