"""Convert multiple PDF files to ordered PNG images."""

from __future__ import annotations

import queue
import threading
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pymupdf
from PIL import Image, ImageDraw

from ui_theme import COLORS as C, FONTS, RADIUS, SPACE as S


def available_folder(parent: Path, name: str) -> Path:
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name}_{number}"
        number += 1
    candidate.mkdir()
    return candidate


def convert_pdf(pdf_path: Path, output_root: Path, dpi: int, progress) -> Path:
    with pymupdf.open(pdf_path) as document:
        if document.page_count == 0:
            raise ValueError("PDF ไม่มีหน้า")
        output_folder = available_folder(output_root, pdf_path.stem)
        digits = max(3, len(str(document.page_count)))
        for index, page in enumerate(document, start=1):
            image = page.get_pixmap(dpi=dpi, alpha=False)
            image.save(output_folder / f"{pdf_path.stem}_page_{index:0{digits}d}.png")
            progress(index, document.page_count)
    return output_folder


def document_icon(size=48, color="accent"):
    """One consistent outline icon, drawn at 2x for crisp Windows scaling."""
    image = Image.new("RGBA", (96, 96))
    draw = ImageDraw.Draw(image)
    ink = C[color]
    draw.line([(28, 14), (56, 14), (72, 30), (72, 80), (28, 80), (28, 14)], fill=ink, width=4, joint="curve")
    draw.line([(56, 14), (56, 30), (72, 30)], fill=ink, width=4)
    draw.line([(39, 48), (61, 48)], fill=ink, width=4)
    draw.line([(39, 60), (55, 60)], fill=ink, width=4)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


class App:
    """PDF LoveR shell with a Catalogue home and the existing PNG workbench."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        root.title("PDF LoveR · เครื่องมือ PDF")
        icon_path = Path(__file__).resolve().parent / "assets" / "pdf_to_png.ico"
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
        root.geometry("1080x780")
        root.minsize(920, 700)
        root.configure(fg_color=C["paper"])
        self.files: list[Path] = []
        self.events: queue.Queue[tuple] = queue.Queue()
        self.output = tk.StringVar(value=str(Path.home() / "Pictures"))
        self.dpi = tk.StringVar(value="150")
        self.status = tk.StringVar(value="เลือกไฟล์ PDF แล้วเริ่มแปลงได้เลย")
        self.busy = False
        self.errors: list[str] = []
        self.destination: Path | None = None
        self.file_states: dict[Path, str] = {}
        self.row_status: dict[Path, ctk.CTkLabel] = {}
        self.filename_labels: dict[Path, ctk.CTkLabel] = {}
        self.controls: list = []
        self.font_body = ctk.CTkFont(family=FONTS["body"], size=16)
        self.font_small = ctk.CTkFont(family=FONTS["body"], size=14)
        self.font_bold = ctk.CTkFont(family=FONTS["body"], size=17, weight="bold")
        self.icon = document_icon()
        self.small_icon = document_icon(32, "muted")
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self.workbench = ctk.CTkFrame(root, fg_color=C["paper"], corner_radius=0)
        self.workbench.grid(row=0, column=0, sticky="nsew")
        self._build()
        self._render_files()
        from home_page import HomePage
        self.home = HomePage(root, self)
        self.home.grid(row=0, column=0, sticky="nsew")
        self.show_home()
        root.bind("<Control-o>", self._open_pdf_shortcut)
        root.bind("<Control-Return>", lambda _: self.start() if self.route == "pdf-png" else None)
        root.bind("<Control-f>", self._search_shortcut)
        root.bind("<Alt-Left>", lambda _: self.show_home())
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.process_events)

    def label(self, parent, text="", font=None, color="ink", **kwargs):
        return ctk.CTkLabel(parent, text=text, font=font or self.font_body,
                            text_color=C[color], anchor=kwargs.pop("anchor", "w"), **kwargs)

    def button(self, parent, text, command, primary=False, width=140, **kwargs):
        button = ctk.CTkButton(
            parent, text=text, command=command, width=width, height=44,
            corner_radius=RADIUS["control"], border_width=2,
            border_color=C["accent"] if primary else C["rule"],
            fg_color=C["accent"] if primary else C["surface"],
            hover_color=C["accent-hover"] if primary else C["soft"],
            text_color=C["accent-ink"] if primary else C["ink"],
            text_color_disabled=C["muted"], font=self.font_body, **kwargs,
        )
        # CustomTkinter buttons need explicit keyboard support and instant focus.
        button._canvas.configure(takefocus=1)
        resting_border = C["accent"] if primary else C["rule"]
        button._canvas.bind("<FocusIn>", lambda _: button.configure(border_color=C["focus"]))
        button._canvas.bind("<FocusOut>", lambda _: button.configure(border_color=resting_border))
        for key in ("<Return>", "<space>"):
            button._canvas.bind(key, lambda _, b=button: b.invoke())
        fill = C["accent"] if primary else C["surface"]
        pressed = C["accent-pressed"] if primary else C["soft"]
        def press(_):
            if button.cget("state") == "normal":
                button._resting_fill = button.cget("fg_color")
                button.configure(fg_color=pressed)
        def release(_):
            if button.cget("state") == "normal":
                button.configure(fg_color=getattr(button, "_resting_fill", fill))
        button.bind("<ButtonPress-1>", press)
        button.bind("<ButtonRelease-1>", release)
        return button

    def _build(self):
        root = self.workbench
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(root, fg_color=C["surface"], corner_radius=0, height=64)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        self.label(header, "", image=document_icon(36), width=40).grid(row=0, column=0, rowspan=2, padx=(S["2xl"], S["md"]), pady=S["sm"])
        self.label(header, "PDF to PNG", font=ctk.CTkFont(family=FONTS["display"], size=21, weight="bold")).grid(row=0, column=1, sticky="sw", pady=(S["md"], 0))
        self.label(header, "เครื่องมือแปลงเอกสารเป็นภาพ", font=self.font_small, color="muted").grid(row=1, column=1, sticky="nw", pady=(0, S["md"]))
        self.home_button = self.button(header, "เครื่องมือทั้งหมด", self.show_home, width=200)
        self.home_button.grid(row=0, column=2, rowspan=2, padx=S["2xl"])
        self.controls.append(self.home_button)
        intro = ctk.CTkFrame(root, fg_color="transparent")
        intro.grid(row=1, column=0, sticky="ew", padx=S["2xl"], pady=(S["lg"], S["lg"]))
        self.label(intro, "ทุกหน้า PDF เป็นภาพ PNG", font=ctk.CTkFont(family=FONTS["body"], size=28, weight="bold")).pack(anchor="w")
        self.label(intro, "เลือกหลายไฟล์ในครั้งเดียว แล้วบันทึกภาพเรียงตามหน้าในโฟลเดอร์ของแต่ละเอกสาร", color="muted").pack(anchor="w", pady=(S["xs"], 0))

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=S["2xl"])
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=324)
        body.grid_rowconfigure(0, weight=1)
        queue_panel = ctk.CTkFrame(body, fg_color=C["surface"], border_width=1,
                                   border_color=C["rule"], corner_radius=RADIUS["panel"])
        queue_panel.grid(row=0, column=0, sticky="nsew", padx=(0, S["xl"]))
        queue_panel.grid_columnconfigure(0, weight=1)
        queue_panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(queue_panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=S["xl"], pady=(S["lg"], S["md"]))
        toolbar.grid_columnconfigure(0, weight=1)
        self.count_label = self.label(toolbar, "รายการ PDF", font=self.font_bold)
        self.count_label.grid(row=0, column=0, sticky="w")
        self.add_button = self.button(toolbar, "+  เพิ่ม PDF", self.add_files, width=120)
        self.add_button.grid(row=0, column=1)
        self.controls.append(self.add_button)
        self.file_area = ctk.CTkFrame(queue_panel, fg_color="transparent", corner_radius=0)
        self.file_area.grid(row=1, column=0, sticky="nsew", padx=S["lg"])
        self.file_area.grid_columnconfigure(0, weight=1)
        self.file_area.grid_rowconfigure(0, weight=1)
        footer = ctk.CTkFrame(queue_panel, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=S["xl"], pady=S["md"])
        footer.grid_columnconfigure(0, weight=1)
        self.total_label = self.label(footer, "ยังไม่มีไฟล์ในรายการ", color="muted", font=self.font_small)
        self.total_label.grid(row=0, column=0, sticky="w")
        self.clear_button = self.button(footer, "ล้างรายการ", self.clear_files, width=104)
        self.clear_button.grid(row=0, column=1)
        self.controls.append(self.clear_button)

        settings = ctk.CTkScrollableFrame(body, fg_color="transparent", width=304, corner_radius=0,
                                         scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        settings.grid(row=0, column=1, sticky="nsew")
        settings.grid_columnconfigure(0, weight=1)
        self.label(settings, "ตั้งค่าการแปลง", font=self.font_bold).grid(row=0, column=0, sticky="w", pady=(S["sm"], S["lg"]))
        self.label(settings, "โฟลเดอร์ปลายทาง").grid(row=1, column=0, sticky="w", pady=(0, S["sm"]))
        output_row = ctk.CTkFrame(settings, fg_color="transparent")
        output_row.grid(row=2, column=0, sticky="ew", pady=(0, S["md"]))
        output_row.grid_columnconfigure(0, weight=1)
        self.output_entry = ctk.CTkEntry(output_row, textvariable=self.output, height=44, corner_radius=RADIUS["control"],
                                        fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"], border_width=2, font=self.font_small)
        self.output_entry.grid(row=0, column=0, sticky="ew", padx=(0, S["sm"]))
        self._entry_focus(self.output_entry)
        self.controls.append(self.output_entry)
        self.browse_button = self.button(output_row, "เลือก…", self.choose_output, width=80)
        self.browse_button.grid(row=0, column=1)
        self.controls.append(self.browse_button)
        self.label(settings, "ความละเอียดภาพ (36–600 DPI)").grid(row=4, column=0, sticky="w", pady=(0, S["sm"]))
        self.dpi_box = ctk.CTkComboBox(settings, variable=self.dpi, values=["72", "150", "200", "300"],
                                      height=44, corner_radius=RADIUS["control"], border_width=2,
                                      fg_color=C["surface"], border_color=C["rule"], button_color=C["rule"],
                                      button_hover_color=C["soft"], text_color=C["ink"], font=self.font_body,
                                      dropdown_font=self.font_body, dropdown_fg_color=C["surface"],
                                      dropdown_text_color=C["ink"], dropdown_hover_color=C["soft"], command=self.update_quality)
        self.dpi_box.grid(row=5, column=0, sticky="ew")
        self._entry_focus(self.dpi_box)
        self.controls.append(self.dpi_box)
        self.quality_hint = self.label(settings, "150 DPI · สมดุลระหว่างคุณภาพกับขนาดไฟล์", color="muted", font=self.font_small)
        self.quality_hint.grid(row=6, column=0, sticky="w", pady=(S["xs"], S["xs"]))
        self.dpi.trace_add("write", lambda *_: self.update_quality())

        naming = ctk.CTkFrame(settings, fg_color=C["graphite"], corner_radius=RADIUS["panel"])
        naming.grid(row=8, column=0, sticky="ew", pady=(S["md"], S["sm"]))
        self.label(naming, "รูปแบบไฟล์ผลลัพธ์", color="accent-ink", font=self.font_bold).pack(anchor="w", padx=S["lg"], pady=(S["lg"], S["sm"]))
        self.name_example = self.label(naming, "ชื่อเอกสาร_page_001.png", color="graphite-muted", font=self.font_small)
        self.name_example.pack(anchor="w", padx=S["lg"])
        self.label(naming, "หนึ่งโฟลเดอร์ต่อหนึ่ง PDF", color="graphite-muted", font=self.font_small).pack(anchor="w", padx=S["lg"], pady=(S["xs"], S["md"]))

        activity = ctk.CTkFrame(root, fg_color=C["surface"], border_width=1, border_color=C["rule"], corner_radius=RADIUS["panel"])
        activity.grid(row=3, column=0, sticky="ew", padx=S["2xl"], pady=(S["lg"], S["md"]))
        activity.grid_columnconfigure(0, weight=1)
        self.activity_title = self.label(activity, "พร้อมเริ่มเมื่อคุณเลือกไฟล์", font=self.font_bold)
        self.activity_title.grid(row=0, column=0, sticky="w", padx=S["xl"], pady=(S["lg"], 0))
        self.percent_label = self.label(activity, "0%", font=self.font_bold, color="muted")
        self.percent_label.grid(row=0, column=1, padx=S["xl"], pady=(S["lg"], 0))
        self.progress = ctk.CTkProgressBar(activity, height=6, corner_radius=3, fg_color=C["soft"], progress_color=C["accent"])
        self.progress.set(0)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=S["xl"], pady=S["md"])
        self.status_label = self.label(activity, textvariable=self.status, text="", font=self.font_small, color="muted")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=S["xl"], pady=(0, S["lg"]))
        self.start_button = self.button(activity, "เริ่มแปลงเป็น PNG", self.start, primary=True, width=220)
        self.start_button.grid(row=0, column=2, rowspan=3, padx=(S["sm"], S["xl"]), pady=S["lg"])

        bottom = ctk.CTkFrame(root, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=S["2xl"], pady=(0, S["md"]))
        bottom.grid_columnconfigure(0, weight=1)
        self.label(bottom, "Ctrl + O  เพิ่ม PDF     ·     Ctrl + Enter  เริ่มแปลง", font=self.font_small, color="muted").grid(row=0, column=0, sticky="w")
        self.error_button = self.button(bottom, "ดูข้อผิดพลาด", self.show_errors, width=132)
        self.open_button = self.button(bottom, "เปิดโฟลเดอร์ผลลัพธ์", self.open_output, width=200)
        self.open_button.grid(row=0, column=2)
        self.open_button.configure(state="disabled")
        self.root.bind("<Configure>", self._resize, add="+")

    def show_home(self):
        if self.busy:
            self.status.set("กำลังแปลงอยู่ · รอให้เสร็จก่อนกลับไปเลือกเครื่องมือ")
            return False
        self.workbench.grid_remove()
        self.home.grid()
        self.route = "home"
        self.root.title("PDF LoveR · เครื่องมือ PDF")
        return True

    def show_tool(self, tool_id):
        from tool_catalog import TOOLS
        tool = next((item for item in TOOLS if item.id == tool_id), None)
        if tool is None:
            return False
        if not tool.ready:
            self.home.show_detail(tool)
            return False
        if tool.id != "pdf-png":
            raise ValueError(f"No working view registered for tool: {tool.id}")
        self.home.close_detail() if self.home.detail_window else None
        self.home.grid_remove()
        self.workbench.grid()
        self.route = tool.id
        self.root.title("PDF เป็น PNG · PDF LoveR")
        self.add_button._canvas.focus_set()
        return True

    def _open_pdf_shortcut(self, _=None):
        if not self.busy:
            self.show_tool("pdf-png")
            self.add_files()
        return "break"

    def _search_shortcut(self, _=None):
        if self.show_home():
            self.home.search_entry.focus_set()
        return "break"

    def _entry_focus(self, entry):
        entry.bind("<FocusIn>", lambda _: entry.configure(border_color=C["focus"]))
        entry.bind("<FocusOut>", lambda _: entry.configure(border_color=C["rule"]))

    def _resize(self, event):
        if event.widget is self.root:
            # Keep filenames/status readable at every supported desktop size.
            scale = ctk.ScalingTracker.get_widget_scaling(self.root)
            self.status_label.configure(wraplength=max(260, event.width / scale - 420))
            for path, label in self.filename_labels.items():
                label.configure(text=self.fit_filename(path.name, max(140, event.width / scale - 660)))

    def update_quality(self, *_):
        hints = {"72": "72 DPI · ไฟล์เล็ก เหมาะสำหรับดูบนหน้าจอ",
                 "150": "150 DPI · สมดุลระหว่างคุณภาพกับขนาดไฟล์",
                 "200": "200 DPI · เพิ่มรายละเอียดของภาพ",
                 "300": "300 DPI · รายละเอียดสูง ใช้พื้นที่มากขึ้น"}
        self.quality_hint.configure(text=hints.get(self.dpi.get(), "DPI สูงขึ้น ภาพละเอียดและไฟล์ใหญ่ขึ้น"), wraplength=290, justify="left")

    @staticmethod
    def shorten(text, limit=42):
        if len(text) <= limit:
            return text
        return text[:limit - 15] + "…" + text[-14:]

    def fit_filename(self, text, width):
        if self.font_bold.measure(text) <= width:
            return text
        end = text[-10:]
        prefix = text[:-10]
        while prefix and self.font_bold.measure(prefix + "…" + end) > width:
            prefix = prefix[:-1]
        return prefix + "…" + end

    def _render_files(self):
        for widget in self.file_area.winfo_children():
            widget.destroy()
        self.row_status.clear()
        self.filename_labels.clear()
        self.count_label.configure(text=f"รายการ PDF  ·  {len(self.files)} ไฟล์" if self.files else "รายการ PDF")
        self.clear_button.configure(state="normal" if self.files and not self.busy else "disabled")
        if not self.files:
            empty = ctk.CTkFrame(self.file_area, fg_color="transparent")
            empty.grid(row=0, column=0)
            self.label(empty, "", image=self.icon, width=64, height=64, anchor="center").pack(pady=(0, S["lg"]))
            self.label(empty, "เริ่มจากไฟล์ PDF ของคุณ", font=self.font_bold, anchor="center").pack()
            self.label(empty, "เพิ่มเอกสารเพื่อแปลงทุกหน้าเป็นภาพ", color="muted", anchor="center").pack(pady=(S["xs"], S["lg"]))
            empty_add = self.button(empty, "เลือกไฟล์ PDF…", self.add_files, width=176)
            empty_add.pack()
            self.total_label.configure(text="เลือก PDF ได้หลายไฟล์พร้อมกัน")
            self.name_example.configure(text="ชื่อเอกสาร_page_001.png")
            return
        scroll = ctk.CTkScrollableFrame(self.file_area, fg_color="transparent", corner_radius=0,
                                        scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        total_size = 0
        for index, path in enumerate(self.files):
            try:
                size = path.stat().st_size
                total_size += size
                detail = f"PDF  ·  {size / 1024 / 1024:.2f} MB"
            except OSError:
                detail = "ไม่พบไฟล์ · เพิ่มไฟล์ใหม่อีกครั้ง"
            row = ctk.CTkFrame(scroll, fg_color=C["paper"], corner_radius=RADIUS["control"])
            row.grid(row=index, column=0, sticky="ew", pady=(0, S["sm"]))
            row.grid_columnconfigure(1, weight=1)
            self.label(row, "", image=self.small_icon, width=40).grid(row=0, column=0, rowspan=2, padx=(S["sm"], S["sm"]), pady=S["md"])
            scale = ctk.ScalingTracker.get_widget_scaling(self.root)
            name_label = self.label(row, self.fit_filename(path.name, max(140, self.root.winfo_width() / scale - 660)), font=self.font_bold)
            name_label.grid(row=0, column=1, sticky="w", pady=(S["md"], 0))
            self.filename_labels[path] = name_label
            self.label(row, detail, color="muted", font=self.font_small).grid(row=1, column=1, sticky="w", pady=(0, S["md"]))
            status = self.label(row, self.file_states.get(path, "รอแปลง"), color="muted", font=self.font_small)
            status.grid(row=0, column=2, rowspan=2, padx=S["sm"])
            self.row_status[path] = status
            remove = self.button(row, "×", lambda p=path: self.remove_file(p), width=44)
            remove.grid(row=0, column=3, rowspan=2, padx=(0, S["sm"]))
            if self.busy:
                remove.configure(state="disabled")
        self.total_label.configure(text=f"{len(self.files)} ไฟล์  ·  รวม {total_size / 1024 / 1024:.2f} MB")
        self.name_example.configure(text=self.shorten(self.files[0].stem + "_page_001.png", 34))

    def add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title="เลือกไฟล์ PDF", filetypes=[("PDF files", "*.pdf")])
        self.add_paths(paths)

    def add_paths(self, paths):
        if self.busy:
            return
        known = {os.path.normcase(str(path.resolve())) for path in self.files}
        for name in paths:
            path = Path(name).resolve()
            key = os.path.normcase(str(path))
            if path.suffix.lower() == ".pdf" and key not in known:
                self.files.append(path)
                known.add(key)
        self._render_files()
        self._queue_changed()

    def remove_file(self, path):
        if not self.busy and path in self.files:
            self.files.remove(path)
            self.file_states.pop(path, None)
            self._render_files()
            self._queue_changed()

    def clear_files(self):
        if not self.busy:
            self.files.clear()
            self.file_states.clear()
            self._render_files()
            self._queue_changed()

    def _queue_changed(self):
        self.progress.set(0)
        self.percent_label.configure(text="0%")
        self.errors = []
        self.error_button.grid_remove()
        self.start_button.configure(text="เริ่มแปลงเป็น PNG")
        self.activity_title.configure(text="พร้อมแปลงเป็น PNG" if self.files else "พร้อมเริ่มเมื่อคุณเลือกไฟล์", text_color=C["ink"])
        self.status.set(f"เลือกแล้ว {len(self.files)} ไฟล์ · ตั้งค่าปลายทางแล้วเริ่มแปลง" if self.files else "เลือกไฟล์ PDF แล้วเริ่มแปลงได้เลย")

    def choose_output(self):
        if self.busy:
            return
        path = filedialog.askdirectory(parent=self.root, title="เลือกโฟลเดอร์ปลายทาง")
        if path:
            self.output.set(path)

    def validation_error(self, message, field=None):
        self.activity_title.configure(text="ตรวจสอบข้อมูลก่อนเริ่มแปลง", text_color=C["error"])
        self.status.set(message)
        if field:
            field.focus_set()
            field.configure(border_color=C["error"])

    def start(self):
        if self.busy:
            return
        if self.route != "pdf-png":
            self.show_tool("pdf-png")
        if not self.files:
            self.validation_error("ยังไม่มี PDF · กดเพิ่ม PDF เพื่อเลือกอย่างน้อย 1 ไฟล์")
            return
        try:
            dpi = int(self.dpi.get())
            if not 36 <= dpi <= 600:
                raise ValueError
        except ValueError:
            self.validation_error("DPI ไม่ถูกต้อง · ใส่จำนวนเต็มระหว่าง 36 ถึง 600", self.dpi_box)
            return
        if not self.output.get().strip():
            self.validation_error("ยังไม่มีปลายทาง · เลือกโฟลเดอร์สำหรับบันทึกภาพ", self.output_entry)
            return
        output_root = Path(self.output.get().strip()).expanduser()
        try:
            output_root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.validation_error(f"เปิดโฟลเดอร์ไม่ได้ · {error}", self.output_entry)
            return
        self.busy = True
        self.errors = []
        self.error_button.grid_remove()
        self.open_button.configure(state="disabled")
        for control in self.controls:
            control.configure(state="disabled")
        self.start_button.configure(state="disabled", text="กำลังแปลง…", fg_color=C["soft"], border_color=C["rule"])
        self.file_states = {path: "รอแปลง" for path in self.files}
        self._render_files()
        self.progress.set(0)
        self.percent_label.configure(text="0%")
        self.activity_title.configure(text="กำลังแปลงเอกสาร", text_color=C["ink"])
        self.status.set("กำลังเปิด PDF · โปรแกรมยังทำงานต่อได้ตามปกติ")
        self.output_entry.configure(border_color=C["rule"])
        self.dpi_box.configure(border_color=C["rule"])
        threading.Thread(target=self.convert_all, args=(list(self.files), output_root, dpi), daemon=True).start()

    def convert_all(self, files, output_root, dpi):
        errors = []
        for number, pdf_path in enumerate(files, start=1):
            self.events.put(("file_start", pdf_path))
            try:
                convert_pdf(pdf_path, output_root, dpi,
                            lambda page, total, n=number, p=pdf_path: self.events.put(("progress", n, len(files), p, page, total)))
                self.events.put(("file_done", number, len(files), pdf_path, None))
            except Exception as error:
                errors.append(f"{pdf_path.name}: {error}")
                self.events.put(("file_done", number, len(files), pdf_path, str(error)))
        self.events.put(("done", len(files) - len(errors), errors, output_root))

    def set_row_status(self, path, text, color="muted"):
        self.file_states[path] = text
        label = self.row_status.get(path)
        if label:
            label.configure(text=text, text_color=C[color])

    def set_progress(self, value):
        self.progress.set(value)
        self.percent_label.configure(text=f"{value:.0%}")

    def process_events(self):
        try:
            # Bound each batch so long documents cannot starve the UI event loop.
            for _ in range(100):
                event = self.events.get_nowait()
                if event[0] == "file_start":
                    self.set_row_status(event[1], "กำลังเปิด…", "accent")
                elif event[0] == "progress":
                    _, number, count, path, page, pages = event
                    self.set_progress((number - 1 + page / pages) / count)
                    self.set_row_status(path, f"หน้า {page}/{pages}", "accent")
                    self.status.set(f"ไฟล์ {number}/{count} · {self.shorten(path.name, 40)} · หน้า {page}/{pages}")
                elif event[0] == "file_done":
                    _, number, count, path, error = event
                    self.set_progress(number / count)
                    self.set_row_status(path, "ผิดพลาด" if error else "เสร็จแล้ว", "error" if error else "success")
                elif event[0] == "done":
                    _, succeeded, self.errors, self.destination = event
                    self.busy = False
                    for control in self.controls:
                        control.configure(state="normal")
                    self.start_button.configure(state="normal", text="แปลงอีกครั้ง", fg_color=C["accent"], border_color=C["accent"])
                    self.open_button.configure(state="normal")
                    self.activity_title.configure(text=f"แปลงสำเร็จ {succeeded} ไฟล์" + (f" · มีปัญหา {len(self.errors)} ไฟล์" if self.errors else " · พร้อมใช้งาน"),
                                                  text_color=C["error"] if self.errors else C["success"])
                    self.status.set("บันทึกแล้ว · เปิดโฟลเดอร์ผลลัพธ์เพื่อดูภาพ" if not self.errors else "บางไฟล์แปลงไม่ได้ · กดดูข้อผิดพลาดเพื่อตรวจสอบ")
                    if self.errors:
                        self.error_button.grid(row=0, column=1, padx=(0, S["sm"]))
        except queue.Empty:
            pass
        self.root.after(80, self.process_events)

    def show_errors(self):
        if self.errors:
            messagebox.showwarning("ไฟล์ที่แปลงไม่ได้", "\n\n".join(self.errors), parent=self.root)

    def open_output(self):
        if self.destination and not self.busy:
            try:
                os.startfile(str(self.destination.resolve()))
            except OSError as error:
                self.validation_error(f"เปิดโฟลเดอร์ไม่ได้ · {error}")

    def close(self):
        if self.busy:
            self.status.set("กำลังแปลงอยู่ · รอให้เสร็จก่อนปิดโปรแกรม")
        else:
            self.root.destroy()


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    window = ctk.CTk()
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from app_self_test import run
        run(window, App, sys.argv[2])
    else:
        App(window)
        window.mainloop()
