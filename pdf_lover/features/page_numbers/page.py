"""Shared selection worker lifecycle with a bounded, exact numbered preview."""
import tkinter as tk
import customtkinter as ctk
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.features.page_numbers.service import NumberSettings, build_plan, number_pdf, label_for, POSITIONS
from pdf_lover.core.document import DocumentError
from pdf_lover.ui.workbench import shell, save_bar, output_settings
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.page_preview import PagePreview
from pdf_lover.ui.theme import COLORS as C, SPACE as S


class NumberPreview(PagePreview):
    def __init__(self, parent, app):
        self.number_plan = None
        super().__init__(parent, app)
        self.title.configure(text='ภาพก่อน–หลังใส่หมายเลข')

    def keys(self):
        if not self.info:
            return ()
        base = (self.info.path, self.info.signature[3], self.info.signature[2], self.page-1, 0, 320, 400)
        plan = self.number_plan
        if plan and self.page in plan.selected:
            text = label_for(plan.settings, self.page, plan.selected.index(self.page), self.info.page_count, len(plan.selected))
            return (base, base + ('page-numbers', text, plan.settings))
        return (base, base)

    def move(self, delta):
        if self.enabled and self.number_plan:
            pages = self.number_plan.selected
            index = pages.index(self.page) if self.page in pages else 0
            self.page = pages[max(0, min(len(pages)-1, index+delta))]
            self.render()

    def render(self):
        super().render()
        if self.info and self.number_plan and self.page in self.number_plan.selected:
            plan = self.number_plan
            self.caption.configure(text=f'หน้าเดิม {self.page} → ' + label_for(plan.settings, self.page,
                plan.selected.index(self.page), self.info.page_count, len(plan.selected)))
            index = plan.selected.index(self.page)
            self.previous.configure(state='normal' if self.enabled and index else 'disabled')
            self.next.configure(state='normal' if self.enabled and index < len(plan.selected)-1 else 'disabled')


class PageNumbersPage(SelectionPage):
    TITLE = 'ใส่หมายเลขหน้า PDF'
    SUFFIX = '_หมายเลขหน้า'
    SAVE_LABEL = 'ใส่เลขและบันทึก PDF ใหม่'
    EVENT_LIMIT = 32
    export = staticmethod(number_pdf)

    def __init__(self, parent, app):
        self.number_start = tk.StringVar(master=app.root, value='1')
        self.number_size = tk.StringVar(master=app.root, value='12')
        self.number_color = tk.StringVar(master=app.root, value='#000000')
        self.number_sequence = tk.StringVar(master=app.root, value='original')
        self.number_position = tk.StringVar(master=app.root, value='bottom-center')
        self.number_format = tk.StringVar(master=app.root, value='number')
        self.thai_digits = tk.BooleanVar(master=app.root, value=False)
        self.view = 'select'
        super().__init__(parent, app)
        for var in self.number_variables:
            var.trace_add('write', self._settings_changed)

    @property
    def number_variables(self):
        return (self.number_start, self.number_size, self.number_color, self.number_sequence,
                self.number_position, self.number_format, self.thai_digits)

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
        source, body, rail = shell(self, 'เลขหน้า', 'เลือกหน้า · ตั้งหมายเลข · ตรวจภาพผลลัพธ์ · บันทึกใหม่', scroll_review=True)
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
        for index,(title,view) in enumerate((('เลือกหน้า','select'),('ตรวจภาพเลข','preview'))):
            button = self.button(tabs,title,lambda v=view:self.show_view(v),width=110)
            button.grid(row=0,column=index,padx=S['xs'],pady=S['xs'],sticky='ew')
            self.controls.append(button)
        self.selector = PageSelector(self.stage,self.app,self._settings_changed,title='หน้าที่จะใส่หมายเลข',hint='ทุกหน้า หรือช่วง เช่น 1-3,5')
        self.selector.grid(row=1,column=0,sticky='nsew')
        self.preview = NumberPreview(self.stage,self.app)
        self.mode_buttons = []
        self.summary = self.label(rail,'',font=self.font_small,wraplength=290,justify='left')
        self.summary.grid(row=0,column=0,sticky='ew',padx=S['sm'])
        settings = ctk.CTkFrame(rail,fg_color='transparent')
        settings.grid(row=1,column=0,sticky='ew',padx=S['sm'])
        settings.grid_columnconfigure(0,weight=1)
        self._menu(settings,0,'วิธีนับเลข',self.number_sequence,(('original','ตามลำดับหน้าเดิม'),('selected','ต่อเนื่องเฉพาะหน้าที่เลือก')))
        self.label(settings,'เลข = เริ่มต้น + (หน้าเดิม − 1)\nหรือ เริ่มต้น + ลำดับในหน้าที่เลือก\nตัวหาร / = จำนวนหน้าทั้ง PDF\nหรือจำนวนหน้าที่เลือก ไม่ใช่เลขสุดท้าย',font=self.font_small,wraplength=285,justify='left').grid(row=2,column=0,sticky='w')
        self._menu(settings,3,'รูปแบบ',self.number_format,(('number','1'),('page','หน้า 1'),('total','1 / 10')))
        self._menu(settings,5,'ตำแหน่งในหน้าที่มองเห็น',self.number_position,tuple(zip(POSITIONS,('บนซ้าย','บนกลาง','บนขวา','ล่างซ้าย','ล่างกลาง','ล่างขวา'))))
        for row,title,var in ((7,'เลขเริ่มต้น (1–999999)',self.number_start),(9,'ขนาด (6–72 pt)',self.number_size),(11,'สี #RRGGBB',self.number_color)):
            self.label(settings,title,font=self.font_small).grid(row=row,column=0,sticky='w')
            self._entry(settings,var).grid(row=row+1,column=0,sticky='ew',pady=S['xs'])
        digits = ctk.CTkCheckBox(settings,text='ใช้เลขไทย ๑ ๒ ๓',variable=self.thai_digits,font=self.font_small)
        digits.grid(row=13,column=0,sticky='w',pady=S['sm'])
        for key in ('<Return>', '<space>'):
            digits._canvas.bind(key, lambda _: digits.toggle() if not self.busy else None)
        self.controls.append(digits)
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

    def build_plan(self, info, directory, prefix, expression, mode):
        try:
            settings = NumberSettings(int(self.number_start.get()), self.number_sequence.get(),
                self.number_position.get(), int(self.number_size.get()), self.number_color.get(),
                self.number_format.get(), self.thai_digits.get())
        except ValueError as error:
            raise DocumentError('เลขเริ่มต้นและขนาดต้องเป็นจำนวนเต็ม') from error
        return build_plan(info,directory,prefix,expression,settings)

    def render_outputs(self):
        self.preview.number_plan = self.plan
        self.preview.set_document(self.info)
        if self.plan and self.preview.page not in self.plan.selected:
            self.preview.page = self.plan.selected[0]
            self.preview.render()
        if self.plan:
            self.summary.configure(text=f'ใส่เลข {len(self.plan.selected)} หน้า · เก็บทุก {self.info.page_count} หน้า\nขอบห่าง 12 pt · ฝัง Noto Sans Thai')
        self.preview.set_enabled(not self.busy)

    def _settings_changed(self, *_):
        if hasattr(self,'preview') and not self.busy:
            self.destination = None
            self.open_button.configure(state='disabled')
            self.progress.set(0)
            self.refresh_plan()

    def process_events(self):
        super().process_events()
        self.preview.process_events()
