"""Hallmark · Catalogue · modern-minimal · Cobalt native adaptation.
Pre-emit critique: P5 H5 E4 S5 R5 V4. No decorative motion.
"""
import tkinter as tk
import customtkinter as ctk

from pdf_lover.catalog import CATEGORIES, TOOLS, find_tools
from pdf_lover.version import VERSION
from pdf_lover.ui.theme import COLORS as C, FONTS, RADIUS, SPACE as S


from pdf_lover.ui.icons import tool_icon


class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C["paper"], corner_radius=0)
        self.app = app
        self.category = "all"
        self.ready_only = True
        self.query = tk.StringVar()
        self.columns = 2
        self.cards = []
        self.visible_tools = []
        self.filter_job = None
        self.detail_window = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_sidebar()
        self._build_content()
        self.query.trace_add("write", self._schedule_filter)
        self.render_tools()

    def label(self, parent, text, **kwargs):
        return self.app.label(parent, text, **kwargs)

    def _build_sidebar(self):
        # Full-width identity bar replaces the catalogue sidebar.
        self.sidebar=ctk.CTkFrame(self,fg_color=C['graphite'],corner_radius=0)
        self.sidebar.grid(row=0,column=0,sticky='ew');self.sidebar.grid_columnconfigure(1,weight=1)
        self.label(self.sidebar,'PDF LoveR',font=self.app.font_title,color='accent-ink').grid(row=0,column=0,padx=S['xl'],pady=S['lg'])
        self.label(self.sidebar,'โต๊ะทำงานเอกสาร',font=self.app.font_body,color='graphite-muted').grid(row=0,column=1,sticky='w')
        self.label(self.sidebar,f'ออฟไลน์ · v{VERSION}',font=self.app.font_small,color='graphite-muted').grid(row=0,column=2,padx=S['xl'])
        self.nav_buttons={}

    def _choose_documents(self):
        if self.app.show_tool('merge'):self.app.merge.add_files()

    def _build_content(self):
        main=ctk.CTkFrame(self,fg_color='transparent',corner_radius=0)
        main.grid(row=1,column=0,sticky='nsew',padx=S['xl'],pady=S['lg'])
        main.grid_columnconfigure(0,weight=1);main.grid_rowconfigure(3,weight=1)
        welcome=ctk.CTkFrame(main,fg_color=C['tint'],corner_radius=RADIUS['panel'])
        welcome.grid(row=0,column=0,sticky='ew',pady=(0,S['lg']));welcome.grid_columnconfigure(0,weight=1)
        self.label(welcome,'วันนี้จะจัดการเอกสารอะไร?',font=ctk.CTkFont(family=FONTS['body'],size=30,weight='bold')).grid(row=0,column=0,sticky='w',padx=S['xl'],pady=(S['lg'],0))
        self.label(welcome,'เลือกงานด้านล่าง หรือวาง PDF ที่นี่เพื่อรวมเอกสาร',font=self.app.font_small,color='muted').grid(row=1,column=0,sticky='w',padx=S['xl'],pady=(S['xs'],S['lg']))
        self.app.button(welcome,'เพิ่ม PDF เพื่อรวม',self._choose_documents,primary=True,width=200).grid(row=0,column=1,rowspan=2,padx=S['xl'])
        search=ctk.CTkFrame(main,fg_color='transparent');search.grid(row=1,column=0,sticky='ew',pady=(0,S['md']));search.grid_columnconfigure(0,weight=1)
        self.search_entry=ctk.CTkEntry(search,height=44,font=self.app.font_body,placeholder_text='ค้นหางาน เช่น รวม PDF หรือหมุนหน้า',placeholder_text_color=C['muted'],fg_color=C['surface'],text_color=C['ink'],border_color=C['rule'],border_width=1,corner_radius=RADIUS['control'])
        self.search_entry.grid(row=0,column=0,sticky='ew',padx=(0,S['sm']))
        self.search_entry.bind('<KeyRelease>',lambda _:self.query.set(self.search_entry.get()))
        self.search_entry.bind('<<Paste>>',lambda _:self.after(0,lambda:self.query.set(self.search_entry.get())))
        self.app._entry_focus(self.search_entry)
        categories={'ทุกหมวด':'all',**{c.title:c.id for c in CATEGORIES}}
        self.category_menu=ctk.CTkOptionMenu(search,values=list(categories),height=44,width=180,font=self.app.font_small,dropdown_font=self.app.font_body,fg_color=C['surface'],text_color=C['ink'],button_color=C['soft'],button_hover_color=C['rule'],command=lambda text:self.select_category(categories[text]))
        self.category_menu.grid(row=0,column=1,padx=(0,S['sm']))
        self.category_menu._canvas.configure(takefocus=1)
        self.category_menu._canvas.bind('<FocusIn>',lambda _:self.category_menu.configure(button_color=C['tint']))
        self.category_menu._canvas.bind('<FocusOut>',lambda _:self.category_menu.configure(button_color=C['soft']))
        for key in ('<Return>','<space>','<Alt-Down>'):self.category_menu._canvas.bind(key,lambda _:self.category_menu._open_dropdown_menu())
        self.reset_button=self.app.button(search,'ล้าง',self.reset_filters,width=72);self.reset_button.grid(row=0,column=2)
        toolbar=ctk.CTkFrame(main,fg_color='transparent');toolbar.grid(row=2,column=0,sticky='ew',pady=(0,S['sm']));toolbar.grid_columnconfigure(0,weight=1)
        self.section_title=self.label(toolbar,'เลือกงาน',font=self.app.font_bold);self.section_title.grid(row=0,column=0,sticky='w')
        self.result_label=self.label(toolbar,'',font=self.app.font_small,color='muted');self.result_label.grid(row=1,column=0,sticky='w')
        self.ready_button=self.app.button(toolbar,'ดูเครื่องมือในแผนด้วย',self.toggle_ready,width=220);self.ready_button.grid(row=0,column=1,rowspan=2)
        self.scroll=ctk.CTkScrollableFrame(main,fg_color='transparent',corner_radius=0,scrollbar_button_color=C['rule'])
        self.scroll.grid(row=3,column=0,sticky='nsew');self.scroll.grid_columnconfigure(0,weight=1)
        self.grid_area=ctk.CTkFrame(self.scroll,fg_color='transparent',corner_radius=0);self.grid_area.grid(row=0,column=0,sticky='ew')
        self.scroll._parent_canvas.bind('<Configure>',self._on_resize,add='+')
        self.label(main,'เลือกเอกสาร  ·  ตั้งค่าและเลือกหน้า  ·  ตรวจผล  ·  บันทึกไฟล์ใหม่',font=self.app.font_small,color='muted').grid(row=4,column=0,sticky='w',pady=(S['sm'],0))

    def _schedule_filter(self, *_):
        if self.search_entry.get() != self.query.get():
            self.search_entry.delete(0, "end")
            self.search_entry.insert(0, self.query.get())
        if self.filter_job:
            self.after_cancel(self.filter_job)
        self.filter_job = self.after(180, self.render_tools)

    def _on_resize(self, event):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        width = event.width / scale
        columns = 3 if width >= 1180 else 2 if width >= 700 else 1
        if columns != self.columns:
            self.columns = columns
            self.render_tools(reset_scroll=False)
        card_width = max(240, (width - S["lg"] * (self.columns - 1)) / self.columns)
        for card, description in self.cards:
            description.configure(wraplength=max(140,card_width - 160))

    def select_category(self, category):
        self.category = category
        self.render_tools()

    def toggle_ready(self):
        self.ready_only = not self.ready_only
        self.render_tools()

    def reset_filters(self):
        self.query.set("")
        self.category = "all"
        self.ready_only = True
        self.render_tools()

    def render_tools(self, reset_scroll=True):
        if self.filter_job:
            self.after_cancel(self.filter_job)
            self.filter_job = None
        for widget in self.grid_area.winfo_children():
            widget.destroy()
        self.cards.clear()
        self.visible_tools = find_tools(self.query.get(), self.category, self.ready_only)
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        viewport = max(300, self.scroll._parent_canvas.winfo_width() / scale)
        card_width = (viewport - S["lg"] * (self.columns - 1)) / self.columns
        titles = {category.id: category.title for category in CATEGORIES}
        self.section_title.configure(text=titles.get(self.category, "งานที่พร้อมทำ" if self.ready_only else "เครื่องมือทั้งหมด"))
        self.category_menu.set(titles.get(self.category,"ทุกหมวด"))
        for key, button in self.nav_buttons.items():
            active = key == self.category
            button.configure(fg_color=C["tint"] if active else C["surface"], text_color=C["accent"] if active else C["ink"],
                             border_color=C["accent"] if active else C["surface"])
        self.ready_button.configure(text="ดูเครื่องมือในแผนด้วย" if self.ready_only else "กลับไปเครื่องมือพร้อมใช้",
                                    fg_color=C["tint"] if self.ready_only else C["surface"])
        ready = sum(tool.ready for tool in self.visible_tools)
        self.result_label.configure(text=f"{len(self.visible_tools)} เครื่องมือ · พร้อมใช้ {ready} · ยังไม่พร้อมใช้ {len(self.visible_tools) - ready}")
        self.reset_button.configure(state="normal" if self.query.get() or self.category != "all" or not self.ready_only else "disabled")
        for column in range(3):
            self.grid_area.grid_columnconfigure(column, weight=1 if column < self.columns else 0, uniform="tools" if column < self.columns else "")
        if not self.visible_tools:
            self._empty_state()
        for index, tool in enumerate(self.visible_tools):
            card = ctk.CTkFrame(self.grid_area,fg_color=C['surface'],border_color=C['rule'],border_width=1,corner_radius=RADIUS['panel'])
            card.grid(row=index//self.columns,column=index%self.columns,sticky='nsew',padx=(0,S['md'] if index%self.columns!=self.columns-1 else 0),pady=(0,S['md']))
            card.grid_columnconfigure(1,weight=1)
            self.label(card,'',image=tool_icon(tool.icon,'accent' if tool.ready else 'muted',32),width=40).grid(row=0,column=0,rowspan=2,padx=(S['lg'],S['md']),pady=S['lg'])
            self.label(card,tool.title,font=self.app.font_bold).grid(row=0,column=1,sticky='w',pady=(S['md'],0))
            description=self.label(card,tool.description if tool.ready else 'ยังไม่พร้อมใช้ · '+tool.description,font=self.app.font_small,color='muted',wraplength=max(140,card_width-160),justify='left',height=48)
            description.grid(row=1,column=1,sticky='ew',pady=(0,S['md']))
            action=self.app.button(card,'เปิด' if tool.ready else 'ข้อมูล',lambda key=tool.id:self.app.show_tool(key),width=64)
            action.grid(row=0,column=2,rowspan=2,padx=S['md'],pady=S['lg'])
            self.cards.append((card, description))
        if reset_scroll:
            self.scroll._parent_canvas.yview_moveto(0)

    def _empty_state(self):
        empty = ctk.CTkFrame(self.grid_area, fg_color="transparent")
        empty.grid(row=0, column=0, columnspan=self.columns, sticky="ew", pady=S["3xl"])
        self.label(empty, "ไม่พบเครื่องมือที่ตรงกัน", font=self.app.font_bold).pack()
        self.label(empty, "ลองค้นหาคำอื่น หรือแสดงทุกหมวดเครื่องมือ", color="muted").pack(pady=(S["sm"], S["lg"]))
        self.app.button(empty, "แสดงเครื่องมือทั้งหมด", self.reset_filters, width=210).pack()

    def show_detail(self, tool):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.lift()
            return self.detail_window
        dialog = ctk.CTkToplevel(self)
        self.detail_window = dialog
        dialog.title(tool.title + " · PDF LoveR")
        dialog.configure(fg_color=C["surface"])
        dialog.resizable(False, False)
        scale = ctk.ScalingTracker.get_window_scaling(self.app.root)
        x = self.app.root.winfo_rootx() + int((self.app.root.winfo_width() - 560 * scale) / 2)
        y = self.app.root.winfo_rooty() + int((self.app.root.winfo_height() - 380 * scale) / 2)
        dialog.geometry(f"560x380+{max(0, x)}+{max(0, y)}")
        dialog.transient(self.app.root)
        self.label(dialog, tool.title, font=ctk.CTkFont(family=FONTS["body"], size=25, weight="bold"), image=tool_icon(tool.icon, "accent", 32), compound="left").pack(anchor="w", padx=S["2xl"], pady=(S["2xl"], S["md"]))
        self.label(dialog, "ยังไม่พร้อมใช้ · อยู่ในแผนพัฒนา", font=self.app.font_bold, color="accent").pack(anchor="w", padx=S["2xl"])
        self.label(dialog, tool.description, color="muted", wraplength=480, justify="left").pack(anchor="w", padx=S["2xl"], pady=(S["lg"], S["md"]))
        self.label(dialog, tool.note or "เครื่องมือนี้ยังไม่เปิดใช้งาน และยังไม่มีกำหนดวันเปิดใช้งาน", font=self.app.font_small, color="muted", wraplength=480, justify="left").pack(anchor="w", padx=S["2xl"])
        footer = ctk.CTkFrame(dialog, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=S["2xl"], pady=S["xl"])
        close = self.app.button(footer, "กลับไปเลือกเครื่องมือ", lambda: self.close_detail(), width=224)
        close.pack(side="right")
        dialog.bind("<Escape>", lambda _: self.close_detail())
        dialog.protocol("WM_DELETE_WINDOW", self.close_detail)
        dialog.after(100, lambda: (dialog.grab_set(), close._canvas.focus_set()) if dialog.winfo_exists() else None)
        return dialog

    def close_detail(self):
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.grab_release()
            self.detail_window.destroy()
        self.detail_window = None
        self.search_entry.focus_set()
