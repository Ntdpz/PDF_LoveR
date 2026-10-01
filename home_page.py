"""Hallmark · Catalogue · modern-minimal · Cobalt native adaptation.
Pre-emit critique: P5 H5 E4 S5 R5 V4. No decorative motion.
"""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw

from tool_catalog import CATEGORIES, TOOLS, find_tools
from app_version import VERSION
from ui_theme import COLORS as C, FONTS, RADIUS, SPACE as S


def tool_icon(kind, color="muted", size=28):
    """A single outline vocabulary for document tools, rendered locally at 2x."""
    image = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(image)
    ink = C[color]
    if kind in ("image", "slides"):
        draw.rounded_rectangle((10, 14, 54, 50), radius=3, outline=ink, width=3)
        if kind == "image":
            draw.ellipse((37, 21, 43, 27), outline=ink, width=2)
            draw.line([(13, 46), (26, 32), (35, 40), (42, 33), (51, 45)], fill=ink, width=3)
        else:
            draw.line([(32, 50), (32, 58)], fill=ink, width=3)
            draw.line([(23, 58), (41, 58)], fill=ink, width=3)
            draw.line([(19, 25), (45, 25)], fill=ink, width=3)
            draw.line([(19, 34), (38, 34)], fill=ink, width=3)
    elif kind == "lock":
        draw.arc((20, 8, 44, 40), 180, 360, fill=ink, width=3)
        draw.rounded_rectangle((14, 28, 50, 55), radius=3, outline=ink, width=3)
        draw.line([(32, 38), (32, 46)], fill=ink, width=3)
    elif kind == "crop":
        draw.line([(18, 8), (18, 46), (56, 46)], fill=ink, width=3)
        draw.line([(8, 18), (46, 18), (46, 56)], fill=ink, width=3)
    elif kind == "table":
        draw.rounded_rectangle((10, 12, 54, 52), radius=2, outline=ink, width=3)
        for y in (25, 38):
            draw.line([(10, y), (54, y)], fill=ink, width=2)
        for x in (25, 40):
            draw.line([(x, 12), (x, 52)], fill=ink, width=2)
    elif kind in ("import", "export", "compress", "split"):
        draw.line([(16, 12), (16, 52), (48, 52), (48, 12)], fill=ink, width=3)
        if kind == "split":
            draw.line([(23, 25), (41, 25)], fill=ink, width=3)
            draw.line([(23, 39), (41, 39)], fill=ink, width=3)
        else:
            down = kind != "export"
            start, end = (9, 36) if down else (38, 10)
            draw.line([(32, start), (32, end)], fill=ink, width=3)
            delta = -8 if down else 8
            draw.line([(24, end + delta), (32, end), (40, end + delta)], fill=ink, width=3)
    elif kind == "edit":
        draw.line([(14, 49), (18, 37), (43, 12), (52, 21), (27, 46), (14, 49)], fill=ink, width=3)
        draw.line([(36, 19), (45, 28)], fill=ink, width=3)
    else:
        if kind == "pages":
            draw.line([(10, 17), (10, 55), (41, 55)], fill=ink, width=3)
        draw.line([(19, 9), (41, 9), (53, 21), (53, 48), (19, 48), (19, 9)], fill=ink, width=3)
        draw.line([(41, 9), (41, 21), (53, 21)], fill=ink, width=3)
        draw.line([(26, 29), (45, 29)], fill=ink, width=3)
        draw.line([(26, 37), (40, 37)], fill=ink, width=3)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C["paper"], corner_radius=0)
        self.app = app
        self.category = "all"
        self.ready_only = False
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
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=C["surface"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(4, weight=1)
        identity = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        identity.grid(row=0, column=0, sticky="ew", padx=S["xl"], pady=(S["2xl"], S["xl"]))
        self.label(identity, "PDF LoveR", font=ctk.CTkFont(family=FONTS["display"], size=23, weight="bold")).pack(anchor="w")
        self.label(identity, "พื้นที่ทำงานเอกสารของคุณ", font=self.app.font_small, color="muted").pack(anchor="w", pady=(S["xs"], 0))
        self.nav_buttons = {}
        self.all_button = self.app.button(self.sidebar, "เครื่องมือทั้งหมด", lambda: self.select_category("all"), width=188, anchor="w")
        self.all_button.grid(row=1, column=0, padx=S["lg"], sticky="ew")
        self.nav_buttons["all"] = self.all_button
        self.label(self.sidebar, "หมวดเครื่องมือ", color="muted", font=self.app.font_small).grid(row=2, column=0, sticky="w", padx=S["xl"], pady=(S["xl"], S["sm"]))
        navigation = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        navigation.grid(row=3, column=0, sticky="ew", padx=S["lg"])
        navigation.grid_columnconfigure(0, weight=1)
        for row, category in enumerate(CATEGORIES):
            button = self.app.button(navigation, category.title, lambda key=category.id: self.select_category(key),
                                     width=188, anchor="w", image=tool_icon(category.icon, size=20), compound="left")
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
        self.label(header, "ทุกงาน PDF เริ่มที่นี่", font=ctk.CTkFont(family=FONTS["body"], size=28, weight="bold")).grid(row=0, column=0, sticky="w")
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
        self.feature = ctk.CTkFrame(self.scroll, fg_color=C["tint"], corner_radius=RADIUS["panel"])
        self.feature.grid(row=0, column=0, sticky="ew", pady=(0, S["xl"]))
        self.feature.grid_columnconfigure(0, weight=1)
        self.label(self.feature, "PDF เป็น PNG", font=ctk.CTkFont(family=FONTS["body"], size=23, weight="bold"),
                   image=tool_icon("image", "accent", 32), compound="left").grid(row=0, column=0, sticky="w", padx=S["xl"], pady=(S["lg"], S["xs"]))
        self.label(self.feature, "ทุกหน้าเป็นภาพ พร้อมจัดเก็บในโฟลเดอร์ของแต่ละเอกสาร", color="muted").grid(row=1, column=0, columnspan=2, sticky="w", padx=S["xl"])
        self.label(self.feature, "พร้อมใช้ · หลายไฟล์ · 36–600 DPI · ออฟไลน์", font=self.app.font_small, color="muted").grid(row=2, column=0, sticky="w", padx=S["xl"], pady=(S["sm"], S["lg"]))
        self.feature_button = self.app.button(self.feature, "เปิดเครื่องมือ", lambda: self.app.show_tool("pdf-png"), primary=True, width=144)
        self.feature_button.grid(row=2, column=1, padx=(S["sm"], S["xl"]), pady=(S["sm"], S["lg"]))
        toolbar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, S["sm"]))
        toolbar.grid_columnconfigure(0, weight=1)
        self.section_title = self.label(toolbar, "เครื่องมือทั้งหมด", font=self.app.font_bold)
        self.section_title.grid(row=0, column=0, sticky="w")
        self.ready_button = self.app.button(toolbar, "เฉพาะที่พร้อมใช้", self.toggle_ready, width=160)
        self.ready_button.grid(row=0, column=1)
        self.result_label = self.label(self.scroll, "", font=self.app.font_small, color="muted")
        self.result_label.grid(row=2, column=0, sticky="w", pady=(0, S["lg"]))
        self.grid_area = ctk.CTkFrame(self.scroll, fg_color="transparent", corner_radius=0)
        self.grid_area.grid(row=3, column=0, sticky="ew")
        self.scroll._parent_canvas.bind("<Configure>", self._on_resize, add="+")
        self.label(main, "ฟีเจอร์ “เร็ว ๆ นี้” ยังไม่เปิดใช้งาน · เลือกดูรายละเอียดได้", font=self.app.font_small, color="muted").grid(row=3, column=0, sticky="w", pady=(S["lg"], 0))

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
        columns = 3 if width >= 780 else 2
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
        self.ready_only = False
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
        viewport = max(600, self.scroll._parent_canvas.winfo_width() / scale)
        card_width = (viewport - S["lg"] * (self.columns - 1)) / self.columns
        titles = {category.id: category.title for category in CATEGORIES}
        self.section_title.configure(text=titles.get(self.category, "เครื่องมือทั้งหมด"))
        for key, button in self.nav_buttons.items():
            active = key == self.category
            button.configure(fg_color=C["tint"] if active else C["surface"], text_color=C["accent"] if active else C["ink"],
                             border_color=C["accent"] if active else C["surface"])
        self.ready_button.configure(text="พร้อมใช้เท่านั้น ✓" if self.ready_only else "เฉพาะที่พร้อมใช้",
                                    fg_color=C["tint"] if self.ready_only else C["surface"])
        ready = sum(tool.ready for tool in self.visible_tools)
        self.result_label.configure(text=f"{len(self.visible_tools)} เครื่องมือ · พร้อมใช้ {ready} · เร็ว ๆ นี้ {len(self.visible_tools) - ready}")
        self.reset_button.configure(state="normal" if self.query.get() or self.category != "all" or self.ready_only else "disabled")
        self.feature.grid() if self.category == "all" and not self.query.get() and not self.ready_only else self.feature.grid_remove()
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
            self.label(card, "พร้อมใช้" if tool.ready else "เร็ว ๆ นี้", color="success" if tool.ready else "muted", font=self.app.font_small).grid(row=2, column=0, sticky="w", padx=S["lg"], pady=(S["xs"], 0))
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
        self.label(dialog, "เร็ว ๆ นี้ · อยู่ในแผนพัฒนา", font=self.app.font_bold, color="accent").pack(anchor="w", padx=S["2xl"])
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
