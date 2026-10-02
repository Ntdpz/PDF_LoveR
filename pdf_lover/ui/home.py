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
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_content()
        self.query.trace_add("write", self._schedule_filter)
        self.render_tools()

    def label(self, parent, text, **kwargs):
        return self.app.label(parent, text, **kwargs)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=196, corner_radius=0, fg_color=C["surface"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)
        identity = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        identity.grid(row=0, column=0, sticky="ew", padx=S["xl"], pady=(S["2xl"], S["xl"]))
        self.label(identity, "PDF LoveR", font=ctk.CTkFont(family=FONTS["display"], size=23, weight="bold")).pack(anchor="w")
        self.label(identity, "งานเอกสารของคุณ", font=self.app.font_small, color="muted").pack(anchor="w", pady=(S["xs"], 0))
        self.nav_buttons = {}
        self.all_button = self.app.button(self.sidebar, "เครื่องมือทั้งหมด", lambda: self.select_category("all"), width=164, anchor="w")
        self.all_button.grid(row=1, column=0, padx=S["lg"], sticky="ew")
        self.nav_buttons["all"] = self.all_button
        self.label(self.sidebar, "หมวดเครื่องมือ", color="muted", font=self.app.font_small).grid(row=2, column=0, sticky="w", padx=S["xl"], pady=(S["xl"], S["sm"]))
        navigation = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        navigation.grid(row=3, column=0, sticky="ew", padx=S["lg"])
        navigation.grid_columnconfigure(0, weight=1)
        for row, category in enumerate(CATEGORIES):
            button = self.app.button(navigation, category.title, lambda key=category.id: self.select_category(key),
                                     width=164, anchor="w", image=tool_icon(category.icon, size=20), compound="left")
            button.grid(row=row, column=0, sticky="ew", pady=(0, S["xs"]))
            self.nav_buttons[category.id] = button
        foot = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        foot.grid(row=5, column=0, sticky="ew", padx=S["xl"], pady=S["xl"])
        self.label(foot, "พร้อมใช้บนเครื่องคุณ", font=self.app.font_small, color="muted").pack(anchor="w")
        self.label(foot, f"v{VERSION} · ทำงานออฟไลน์", font=self.app.font_small).pack(anchor="w", pady=(S["xs"], 0))

    def _build_content(self):
        main = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=(S["2xl"], S["xl"]), pady=(S["xl"], S["lg"]))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.label(header, "เลือกงานที่ต้องการทำ", font=ctk.CTkFont(family=FONTS["body"], size=28, weight="bold")).grid(row=0, column=0, sticky="w")
        self.label(header, "เลือกเครื่องมือ หรือวาง PDF เพื่อเปิดหน้ารวมไฟล์", color="muted").grid(row=1, column=0, sticky="w", pady=(S["xs"], 0))
        self.label(header, "Windows", color="muted", font=self.app.font_small).grid(row=0, column=1, sticky="e")
        search = ctk.CTkFrame(main, fg_color="transparent")
        search.grid(row=1, column=0, sticky="ew", pady=(S["lg"], S["lg"]))
        search.grid_columnconfigure(0, weight=1)
        self.label(search, "ค้นหาเครื่องมือ", font=self.app.font_small, color="muted").grid(row=0, column=0, sticky="w", pady=(0, S["xs"]))
        self.search_entry = ctk.CTkEntry(search, height=44, font=self.app.font_body,
                                       placeholder_text="เช่น รวม PDF, Word, OCR", placeholder_text_color=C["muted"],
                                       fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"], border_width=2,
                                       corner_radius=RADIUS["control"])
        self.search_entry.grid(row=1, column=0, sticky="ew", padx=(0, S["sm"]))
        self.search_entry.bind("<KeyRelease>", lambda _: self.query.set(self.search_entry.get()))
        self.search_entry.bind("<<Paste>>", lambda _: self.after(0, lambda: self.query.set(self.search_entry.get())))
        self.app._entry_focus(self.search_entry)
        self.reset_button = self.app.button(search, "ล้างตัวกรอง", self.reset_filters, width=124)
        self.reset_button.grid(row=1, column=1)
        self.scroll = ctk.CTkScrollableFrame(main, fg_color="transparent", corner_radius=0,
                                           scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        self.scroll.grid(row=2, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)
        toolbar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, S["sm"]))
        toolbar.grid_columnconfigure(0, weight=1)
        self.section_title = self.label(toolbar, "เครื่องมือทั้งหมด", font=self.app.font_bold)
        self.section_title.grid(row=0, column=0, sticky="w")
        self.ready_button = self.app.button(toolbar, "ดูเครื่องมือในแผนด้วย", self.toggle_ready, width=220)
        self.ready_button.grid(row=0, column=1)
        self.result_label = self.label(self.scroll, "", font=self.app.font_small, color="muted")
        self.result_label.grid(row=2, column=0, sticky="w", pady=(0, S["lg"]))
        self.grid_area = ctk.CTkFrame(self.scroll, fg_color="transparent", corner_radius=0)
        self.grid_area.grid(row=3, column=0, sticky="ew")
        self.scroll._parent_canvas.bind("<Configure>", self._on_resize, add="+")
        self.label(main, "เครื่องมือในแผนยังไม่พร้อมใช้ · ใช้งานได้เฉพาะรายการที่ระบุพร้อมใช้", font=self.app.font_small, color="muted").grid(row=3, column=0, sticky="w", pady=(S["lg"], 0))

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
        columns = 3 if width >= 840 else 2 if width >= 480 else 1
        if columns != self.columns:
            self.columns = columns
            self.render_tools(reset_scroll=False)
        card_width = max(240, (width - S["lg"] * (self.columns - 1)) / self.columns)
        for card, description in self.cards:
            description.configure(wraplength=card_width - 2 * S["lg"])

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
        self.section_title.configure(text=titles.get(self.category, "เครื่องมือพร้อมใช้" if self.ready_only else "เครื่องมือทั้งหมด"))
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
            card = ctk.CTkFrame(self.grid_area, fg_color=C["surface"], border_color=C["rule"], border_width=1,
                               corner_radius=RADIUS["panel"], height=200, width=240)
            card.grid(row=index // self.columns, column=index % self.columns, sticky="nsew",
                      padx=(0, S["lg"] if index % self.columns != self.columns - 1 else 0), pady=(0, S["lg"]))
            card.grid_columnconfigure(0, weight=1)
            self.label(card, tool.title, font=self.app.font_bold, image=tool_icon(tool.icon, "accent" if tool.ready else "muted"), compound="left").grid(row=0, column=0, sticky="w", padx=S["lg"], pady=(S["lg"], S["sm"]))
            description = self.label(card, tool.description, font=self.app.font_small, color="muted", wraplength=max(180, card_width - 2 * S["lg"]), justify="left", height=60)
            description.grid(row=1, column=0, sticky="ew", padx=S["lg"])
            self.label(card, "พร้อมใช้" if tool.ready else "ยังไม่พร้อมใช้", color="success" if tool.ready else "muted", font=self.app.font_small).grid(row=2, column=0, sticky="w", padx=S["lg"], pady=(S["xs"], 0))
            action = self.app.button(card, "เปิดเครื่องมือ" if tool.ready else "ดูรายละเอียด", lambda key=tool.id: self.app.show_tool(key), width=160)
            action.grid(row=3, column=0, sticky="ew", padx=S["lg"], pady=(S["sm"], S["lg"]))
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
