"""PDF to Image feature page. Rendering lives in service.py."""
from __future__ import annotations
import os
import queue
from decimal import Decimal, InvalidOperation
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from pdf_lover.core.cancellation import Cancelled, checkpoint
import customtkinter as ctk
from pdf_lover.features.base import ToolPage
from pdf_lover.features.png.service import convert_pdf, ImageOptions, FORMATS
from pdf_lover.platform.paths import documents_folder
from pdf_lover.core.document import inspect_document
from pdf_lover.core.page_selection import selected_pages
from pdf_lover.ui.icons import document_icon
from pdf_lover.ui.theme import COLORS as C, FONTS, RADIUS, SPACE as S


class PngPage(ToolPage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.files: list[Path] = []
        self.selections = {}
        self.selection_window = None
        self.selection_buttons = {}
        self.events: queue.Queue[tuple] = queue.Queue(maxsize=32)
        self.output = tk.StringVar(value=str(documents_folder()))
        self.dpi = tk.StringVar(value="150")
        self.file_type = tk.StringVar(value="PNG")
        self.size_mode = tk.StringVar(value="DPI")
        self.width_px = tk.StringVar()
        self.height_px = tk.StringVar()
        self.limit_size = tk.StringVar()
        self.limit_unit = tk.StringVar(value="MB")
        self.jpeg_quality = tk.StringVar(value="95")
        self.warnings: list[str] = []
        self.warning_count = 0
        self.status = tk.StringVar(value="เลือกไฟล์ PDF แล้วเริ่มแปลงได้เลย")
        self.errors: list[str] = []
        self.destination: Path | None = None
        self.file_states: dict[Path, str] = {}
        self.row_status: dict[Path, ctk.CTkLabel] = {}
        self.filename_labels: dict[Path, ctk.CTkLabel] = {}
        self.controls: list = []
        self.icon = document_icon()
        self.small_icon = document_icon(32, "muted")
        self._build()
        self._render_files()
        self.update_image_settings()

    def _build(self):
        root = self
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        from pdf_lover.ui.navigation import masthead
        masthead(self, 'PDF to Image')
        intro = ctk.CTkFrame(root, fg_color="transparent")
        intro.grid(row=1, column=0, sticky="ew", padx=S["xl"], pady=S["sm"])
        self.label(intro, "เลือกเอกสาร · ตั้งค่า · ตรวจชื่อภาพ · บันทึก", font=ctk.CTkFont(family=FONTS["body"], size=20, weight="bold")).pack(anchor="w")
        self.label(intro, "PNG / JPG / WebP / TIFF · หนึ่งโฟลเดอร์ต่อเอกสาร", color="muted").pack(anchor="w", pady=(S["xs"], 0))

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=S["xl"])
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0, minsize=324)
        body.grid_rowconfigure(0, weight=1)
        queue_panel = ctk.CTkFrame(body, fg_color=C["surface"], border_width=1,
                                   border_color=C["rule"], corner_radius=RADIUS["panel"])
        queue_panel.grid(row=0, column=0, sticky="nsew", padx=(0, S["xl"]))
        queue_panel.grid_columnconfigure(0, weight=1)
        queue_panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(queue_panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=S["xl"], pady=(S["sm"], S["sm"]))
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
        footer.grid(row=2, column=0, sticky="ew", padx=S["xl"], pady=S["sm"])
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
        self.dpi_label = self.label(settings, "ความละเอียดภาพ (36–600 DPI)")
        self.dpi_label.grid(row=10, column=0, sticky="w", pady=(S["sm"], S["xs"]))
        self.dpi_box = ctk.CTkComboBox(settings, variable=self.dpi, values=["72", "150", "200", "300"],
                                      height=44, corner_radius=RADIUS["control"], border_width=2,
                                      fg_color=C["surface"], border_color=C["rule"], button_color=C["rule"],
                                      button_hover_color=C["soft"], text_color=C["ink"], font=self.font_body,
                                      dropdown_font=self.font_body, dropdown_fg_color=C["surface"],
                                      dropdown_text_color=C["ink"], dropdown_hover_color=C["soft"], command=self.update_quality)
        self.dpi_box.grid(row=11, column=0, sticky="ew")
        self._entry_focus(self.dpi_box)
        self.controls.append(self.dpi_box)
        self.quality_hint = self.label(settings, "150 DPI · สมดุลระหว่างคุณภาพกับขนาดไฟล์", color="muted", font=self.font_small)
        self.quality_hint.grid(row=12, column=0, sticky="w", pady=(S["xs"], S["xs"]))
        self.dpi.trace_add("write", lambda *_: self.update_quality())

        def option_label(text, row):
            widget = self.label(settings, text, font=self.font_small)
            widget.grid(row=row, column=0, sticky="w", pady=(S["sm"], S["xs"]))
            return widget

        def option_menu(variable, values, row, command=None):
            widget = ctk.CTkOptionMenu(settings, variable=variable, values=values, command=command,
                                       height=44, fg_color=C["graphite"], button_color=C["graphite"],
                                       font=self.font_body, dropdown_font=self.font_body)
            widget.grid(row=row, column=0, sticky="ew")
            self.controls.append(widget)
            return widget

        def option_entry(variable, row):
            widget = ctk.CTkEntry(settings, textvariable=variable, height=44, font=self.font_body,
                                  fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"])
            widget.grid(row=row, column=0, sticky="ew")
            self.controls.append(widget)
            return widget

        option_label("ประเภทไฟล์ปลายทาง", 4)
        self.format_menu = option_menu(self.file_type, list(FORMATS), 5, self.update_image_settings)
        self.format_hint = self.label(settings, "", color="muted", font=self.font_small, wraplength=285, justify="left")
        self.format_hint.grid(row=6, column=0, sticky="w", pady=(S["xs"], 0))
        self.jpeg_label = option_label("คุณภาพ JPG (1–100 · มีการสูญเสียคุณภาพ)", 15)
        self.jpeg_entry = option_entry(self.jpeg_quality, 16)
        option_label("กำหนดขนาดภาพด้วย", 8)
        self.size_menu = option_menu(self.size_mode, ["DPI", "พิกเซล"], 9, self.update_image_settings)
        self.width_label = option_label("ความกว้าง (px · เว้นว่างได้)", 10)
        self.width_entry = option_entry(self.width_px, 11)
        self.height_label = option_label("ความสูง (px · เว้นว่างได้)", 12)
        self.height_entry = option_entry(self.height_px, 13)
        self.pixel_hint = self.label(settings, "ล็อกสัดส่วนเสมอ · ใส่สองช่อง = กรอบสูงสุด\n1–20000 px / ไม่เกิน 40 ล้านพิกเซล", color="muted", font=self.font_small,
                   wraplength=285, justify="left")
        self.pixel_hint.grid(row=14, column=0, sticky="w", pady=(S["xs"], 0))
        option_label("เพดานขนาดไฟล์ต่อภาพ (เว้นว่าง = ไม่จำกัด)", 17)
        self.limit_entry = option_entry(self.limit_size, 18)
        self.limit_menu = option_menu(self.limit_unit, ["KB", "MB"], 19)
        self.label(settings, "เกินเพดาน: บันทึกคุณภาพเดิมแล้วแจ้งเตือน\nไม่ลดพิกเซลหรือคุณภาพเอง\nดูขนาดจริงทุกภาพใน image_report.csv", color="muted", font=self.font_small,
                   wraplength=285, justify="left").grid(row=20, column=0, sticky="w", pady=(S["xs"], 0))

        naming = ctk.CTkFrame(settings, fg_color=C["graphite"], corner_radius=RADIUS["panel"])
        naming.grid(row=22, column=0, sticky="ew", pady=(S["md"], S["sm"]))
        self.label(naming, "รูปแบบไฟล์ผลลัพธ์", color="accent-ink", font=self.font_bold).pack(anchor="w", padx=S["lg"], pady=(S["lg"], S["sm"]))
        self.name_example = self.label(naming, "ชื่อเอกสาร_page_001.png", color="graphite-muted", font=self.font_small)
        self.name_example.pack(anchor="w", padx=S["lg"])
        self.label(naming, "หนึ่งโฟลเดอร์ต่อหนึ่ง PDF", color="graphite-muted", font=self.font_small).pack(anchor="w", padx=S["lg"], pady=(S["xs"], S["md"]))

        activity = ctk.CTkFrame(root, fg_color=C["surface"], border_width=1, border_color=C["rule"], corner_radius=RADIUS["panel"])
        activity.grid(row=3, column=0, sticky="ew", padx=S["xl"], pady=(S["sm"], S["sm"]))
        activity.grid_columnconfigure(0, weight=1)
        self.activity_title = self.label(activity, "พร้อมเริ่มเมื่อคุณเลือกไฟล์", font=self.font_bold)
        self.activity_title.grid(row=0, column=0, sticky="w", padx=S["xl"], pady=(S["sm"], 0))
        self.percent_label = self.label(activity, "0%", font=self.font_bold, color="muted")
        self.percent_label.grid(row=0, column=1, padx=S["xl"], pady=(S["sm"], 0))
        self.progress = ctk.CTkProgressBar(activity, height=6, corner_radius=3, fg_color=C["soft"], progress_color=C["accent"])
        self.progress.set(0)
        self.progress.grid(row=1, column=0, columnspan=2, sticky="ew", padx=S["xl"], pady=S["sm"])
        self.status_label = self.label(activity, textvariable=self.status, text="", font=self.font_small, color="muted")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=S["xl"], pady=(0, S["sm"]))
        self.start_button = self.button(activity, "เริ่มแปลงเป็นภาพ", self.start, primary=True, width=220)
        self.start_button.grid(row=0, column=2, rowspan=3, padx=(S["sm"], S["xl"]), pady=S["lg"])

        bottom = ctk.CTkFrame(root, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=S["xl"], pady=(0, S["md"]))
        bottom.grid_columnconfigure(0, weight=1)
        self.label(bottom, "Ctrl + O  เพิ่ม PDF     ·     Ctrl + Enter  เริ่มแปลง", font=self.font_small, color="muted").grid(row=0, column=0, sticky="w")
        self.error_button = self.button(bottom, "ดูคำเตือน", self.show_errors, width=120)
        self.open_button = self.button(bottom, "เปิดโฟลเดอร์ผลลัพธ์", self.open_output, width=200)
        self.open_button.grid(row=0, column=2)
        self.open_button.configure(state="disabled")
        self.root.bind("<Configure>", self._resize, add="+")

    def _resize(self, event):
        if event.widget is self.root:
            # Keep filenames/status readable at every supported desktop size.
            scale = ctk.ScalingTracker.get_widget_scaling(self.root)
            self.status_label.configure(wraplength=max(260, event.width / scale - 420))
            for path, label in self.filename_labels.items():
                label.configure(text=self.fit_filename(path.name, max(90, event.width / scale - 760)))

    def update_quality(self, *_):
        hints = {"72": "72 DPI · ไฟล์เล็ก เหมาะสำหรับดูบนหน้าจอ",
                 "150": "150 DPI · สมดุลระหว่างคุณภาพกับขนาดไฟล์",
                 "200": "200 DPI · เพิ่มรายละเอียดของภาพ",
                 "300": "300 DPI · รายละเอียดสูง ใช้พื้นที่มากขึ้น"}
        self.quality_hint.configure(text=hints.get(self.dpi.get(), "DPI สูงขึ้น ภาพละเอียดและไฟล์ใหญ่ขึ้น"), wraplength=290, justify="left")

    def update_image_settings(self, *_):
        if self.busy:
            return
        is_jpg = self.file_type.get() == "JPG"
        self.format_hint.configure(text="JPG บีบอัดแบบสูญเสียคุณภาพ แม้ตั้ง 100" if is_jpg else "Lossless · รักษาพิกเซลของภาพที่เรนเดอร์")
        for widget in (self.jpeg_label, self.jpeg_entry):
            widget.grid() if is_jpg else widget.grid_remove()
        self.jpeg_entry.configure(state="normal" if is_jpg else "disabled")
        pixels = self.size_mode.get() == "พิกเซล"
        for widget in (self.dpi_label, self.dpi_box, self.quality_hint):
            widget.grid_remove() if pixels else widget.grid()
        for widget in (self.width_label, self.width_entry, self.height_label, self.height_entry, self.pixel_hint):
            widget.grid() if pixels else widget.grid_remove()
        self.dpi_box.configure(state="disabled" if pixels else "normal")
        self.width_entry.configure(state="normal" if pixels else "disabled")
        self.height_entry.configure(state="normal" if pixels else "disabled")
        stem = self.files[0].stem if self.files else "ชื่อเอกสาร"
        self.name_example.configure(text=self.shorten(stem + "_page_001." + FORMATS[self.file_type.get()], 34))

    def image_options(self):
        pixels = self.size_mode.get() == "พิกเซล"
        width = int(self.width_px.get()) if pixels and self.width_px.get().strip() else None
        height = int(self.height_px.get()) if pixels and self.height_px.get().strip() else None
        if pixels and width is None and height is None:
            raise ValueError("ใส่ความกว้างหรือความสูงอย่างน้อยหนึ่งช่อง")
        limit = None
        if self.limit_size.get().strip():
            value = Decimal(self.limit_size.get().strip())
            if not value.is_finite() or value <= 0 or value > 1000000:
                raise ValueError("เพดานขนาดไฟล์ต้องมากกว่า 0 และไม่เกิน 1000000 KB/MB")
            limit = int(value * (1024 if self.limit_unit.get() == "KB" else 1024 * 1024))
        options = ImageOptions(self.file_type.get(), width, height, limit,
                               int(self.jpeg_quality.get()) if self.file_type.get() == "JPG" else 95)
        options.validate()
        return options

    def _render_files(self):
        for widget in self.file_area.winfo_children():
            widget.destroy()
        self.row_status.clear()
        self.selection_buttons.clear()
        self.filename_labels.clear()
        self.count_label.configure(text=f"รายการ PDF  ·  {len(self.files)} ไฟล์" if self.files else "รายการ PDF")
        self.clear_button.configure(state="normal" if self.files and not self.busy else "disabled")
        if not self.files:
            empty = ctk.CTkFrame(self.file_area, fg_color="transparent")
            empty.grid(row=0, column=0)
            self.label(empty, "", image=self.icon, width=64, height=64, anchor="center").pack(pady=(0, S["sm"]))
            self.label(empty, "เริ่มจากไฟล์ PDF ของคุณ", font=self.font_bold, anchor="center").pack()
            self.label(empty, "ลาก PDF มาวาง หรือเลือกไฟล์เพื่อแปลงภาพ", color="muted", anchor="center").pack(pady=(S["xs"], S["lg"]))
            empty_add = self.button(empty, "เลือกไฟล์ PDF…", self.add_files, width=176)
            empty_add.pack()
            self.total_label.configure(text="เลือก PDF ได้หลายไฟล์พร้อมกัน")
            self.name_example.configure(text="ชื่อเอกสาร_page_001." + FORMATS[self.file_type.get()])
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
            self.label(row, "", image=self.small_icon, width=40).grid(row=0, column=0, rowspan=2, padx=(S["sm"], S["sm"]), pady=S["sm"])
            scale = ctk.ScalingTracker.get_widget_scaling(self.root)
            name_label = self.label(row, self.fit_filename(path.name, max(90, self.root.winfo_width() / scale - 760)), font=self.font_bold)
            name_label.grid(row=0, column=1, sticky="w", pady=(S["md"], 0))
            self.filename_labels[path] = name_label
            if path in self.selections:
                info, expression = self.selections[path]
                detail = "หน้า " + self.shorten(expression, 18)
            else:
                detail += " · ทุกหน้า"
            self.label(row, detail, color="muted", font=self.font_small).grid(row=1, column=1, sticky="w", pady=(0, S["md"]))
            status = self.label(row, self.file_states.get(path, "รอแปลง"), color="muted", font=self.font_small)
            status.grid(row=0, column=3, rowspan=2, padx=S["sm"])
            self.row_status[path] = status
            remove = self.button(row, "×", lambda p=path: self.remove_file(p), width=44)
            remove.grid(row=0, column=4, rowspan=2, padx=(0, S["sm"]))
            select = self.button(row, "เลือกหน้า", lambda p=path: self.choose_pages(p), width=88)
            select.configure(font=self.font_small)
            select.grid(row=0, column=2, rowspan=2, padx=S["xs"])
            self.selection_buttons[path] = select
            if self.busy:
                remove.configure(state="disabled")
                select.configure(state="disabled")
        self.total_label.configure(text=f"{len(self.files)} ไฟล์  ·  รวม {total_size / 1024 / 1024:.2f} MB")
        self.name_example.configure(text=self.shorten(self.files[0].stem + "_page_001." + FORMATS[self.file_type.get()], 34))

    def add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(parent=self.root, title="เลือกไฟล์ PDF", filetypes=[("PDF files", "*.pdf")])
        self.add_paths(paths)

    def add_paths(self, paths):
        if self.busy:
            return
        self.close_selection()
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
            self.close_selection()
            self.selections.pop(path, None)
            self.files.remove(path)
            self.file_states.pop(path, None)
            self._render_files()
            self._queue_changed()

    def clear_files(self):
        if not self.busy:
            self.close_selection()
            self.selections.clear()
            self.files.clear()
            self.file_states.clear()
            self._render_files()
            self._queue_changed()

    def _queue_changed(self):
        self.destination = None
        self.open_button.configure(state="disabled")
        self.progress.set(0)
        self.percent_label.configure(text="0%")
        self.errors = []
        self.warnings = []
        self.warning_count = 0
        self.error_button.grid_remove()
        self.start_button.configure(text="เริ่มแปลงเป็นภาพ")
        self.activity_title.configure(text="พร้อมแปลงเป็นภาพ" if self.files else "พร้อมเริ่มเมื่อคุณเลือกไฟล์", text_color=C["ink"])
        self.status.set(f"เลือกแล้ว {len(self.files)} ไฟล์ · ตั้งค่าปลายทางแล้วเริ่มแปลง" if self.files else "เลือกไฟล์ PDF แล้วเริ่มแปลงได้เลย")

    def choose_pages(self, path):
        if self.busy or path not in self.files:
            return
        self.close_selection()
        self.busy = True
        for control in self.controls:
            control.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self._render_files()
        self.status.set("กำลังอ่านจำนวนหน้า PDF…")
        threading.Thread(target=self._inspect_selection, args=(path,), daemon=True).start()

    def _inspect_selection(self, path):
        try:
            checkpoint(self.cancel_event)
            info = inspect_document(path)
            checkpoint(self.cancel_event)
            self.events.put(("selection_loaded", info))
        except Cancelled as error:
            self.events.put(("selection_cancelled", str(error)))
        except Exception as error:
            self.events.put(("selection_error", str(error)))

    def _open_selection(self, info):
        from pdf_lover.features.png.selection import ImagePageSelection
        previous = self.selections.get(info.path)
        expression = previous[1] if previous and previous[0].signature == info.signature else None
        self.selection_window = ImagePageSelection(self, info, expression)

    def close_selection(self):
        window, self.selection_window = self.selection_window, None
        if window is not None:
            window.destroy()

    def set_active(self, active):
        if not active:
            self.close_selection()
        super().set_active(active)

    def destroy(self):
        self.close_selection()
        super().destroy()

    def choose_output(self):
        if self.busy:
            return
        initial = Path(self.output.get()).expanduser() if self.output.get().strip() else documents_folder()
        path = filedialog.askdirectory(parent=self.root, title="เลือกโฟลเดอร์ปลายทาง",
                                      initialdir=str(initial if initial.is_dir() else documents_folder()))
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
        if self.app.route != "pdf-png":
            self.app.show_tool("pdf-png")
        if self.selection_window is not None:
            self.validation_error("ยืนยันหน้าที่เลือก หรือปิดหน้าต่างเลือกหน้าก่อนเริ่มแปลง")
            return
        if not self.files:
            self.validation_error("ยังไม่มี PDF · กดเพิ่ม PDF เพื่อเลือกอย่างน้อย 1 ไฟล์")
            return
        try:
            dpi = int(self.dpi.get()) if self.size_mode.get() == "DPI" else 150
            if not 36 <= dpi <= 600:
                raise ValueError
        except ValueError:
            self.validation_error("DPI ไม่ถูกต้อง · ใส่จำนวนเต็มระหว่าง 36 ถึง 600", self.dpi_box)
            return
        try:
            options = self.image_options()
        except (ValueError, InvalidOperation) as error:
            self.validation_error(f"ตั้งค่าภาพไม่ถูกต้อง · {error}")
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
        selections = dict(self.selections)
        self.close_selection()
        self.busy = True
        self.errors = []
        self.warnings = []
        self.warning_count = 0
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
        threading.Thread(target=self.convert_all, args=(list(self.files), output_root, dpi, options, selections), daemon=True).start()

    def convert_all(self, files, output_root, dpi, options, selections=None):
        errors = []
        succeeded = 0
        for number, pdf_path in enumerate(files, start=1):
            try:
                checkpoint(self.cancel_event)
                self.events.put(("file_start", pdf_path))
                selected = (selections or {}).get(pdf_path)
                info, expression = selected if selected else (None, None)
                pages = selected_pages(expression, info.page_count) if info else None
                convert_pdf(pdf_path, output_root, dpi,
                            lambda page, total, n=number, p=pdf_path: self.events.put(("progress", n, len(files), p, page, total)),
                            options=options, warning=lambda path, size, limit: self.events.put(("warning", path, size, limit)),
                            pages=pages, info=info, cancel=self.cancel_event)
                succeeded += 1
                self.events.put(("file_done", number, len(files), pdf_path, None))
            except Cancelled as error:
                self.events.put(("cancelled", succeeded, errors, output_root, pdf_path, str(error), bool(error.output_folder)))
                return
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
        if self.selection_window is not None:
            self.selection_window.selector.process_events()
        try:
            # Bound each batch so long documents cannot starve the UI event loop.
            for _ in range(100):
                event = self.events.get_nowait()
                if event[0] in ("selection_loaded", "selection_error", "selection_cancelled"):
                    self.busy = False
                    for control in self.controls:
                        control.configure(state="normal")
                    self.start_button.configure(state="normal")
                    self.update_image_settings()
                    self._render_files()
                    if event[0] == "selection_loaded":
                        self._open_selection(event[1])
                        self.status.set("เลือกหน้าต่อเอกสาร · กดยืนยัน หรือปิดเพื่อยกเลิก")
                    elif event[0] == "selection_cancelled":
                        self.status.set(event[1])
                    else:
                        self.validation_error(event[1])
                elif event[0] == "file_start":
                    self.set_row_status(event[1], "กำลังเปิด…", "accent")
                elif event[0] == "progress":
                    _, number, count, path, page, pages = event
                    self.set_progress((number - 1 + page / pages) / count)
                    self.set_row_status(path, f"หน้า {page}/{pages}", "accent")
                    self.report_progress(f"ไฟล์ {number}/{count} · {self.shorten(path.name, 40)} · หน้า {page}/{pages}")
                elif event[0] == "warning":
                    _, path, size, limit = event
                    self.warning_count += 1
                    if len(self.warnings) < 50:
                        self.warnings.append(f"{path.name}: {size / 1024:.2f} KB > {limit / 1024:.2f} KB")
                elif event[0] == "file_done":
                    _, number, count, path, error = event
                    self.set_progress(number / count)
                    self.set_row_status(path, "ผิดพลาด" if error else "เสร็จแล้ว", "error" if error else "success")
                elif event[0] == "cancelled":
                    _, succeeded, self.errors, output_root, active, message, partial = event
                    self.busy = False
                    for control in self.controls:
                        control.configure(state="normal")
                    self.start_button.configure(state="normal", text="แปลงอีกครั้ง", fg_color=C["accent"], border_color=C["accent"])
                    self.destination = output_root if succeeded or partial else None
                    self.open_button.configure(state="normal" if self.destination else "disabled")
                    for path in self.files:
                        if self.file_states.get(path) == "รอแปลง":
                            self.file_states[path] = "ไม่ได้เริ่ม"
                    self.file_states[active] = "หยุดแล้ว"
                    self.update_image_settings()
                    self._render_files()
                    self.activity_title.configure(text=f"ยกเลิกงานแล้ว · เสร็จ {succeeded} เอกสาร", text_color=C["muted"])
                    self.status.set(message)
                    if self.errors or self.warning_count:
                        self.error_button.configure(text="ดูคำเตือน")
                        self.error_button.grid(row=0, column=1, padx=(0, S["sm"]))
                elif event[0] == "done":
                    _, succeeded, self.errors, self.destination = event
                    self.busy = False
                    for control in self.controls:
                        control.configure(state="normal")
                    self.start_button.configure(state="normal", text="แปลงอีกครั้ง", fg_color=C["accent"], border_color=C["accent"])
                    self.open_button.configure(state="normal")
                    self.update_image_settings()
                    self._render_files()
                    self.activity_title.configure(text=f"แปลงสำเร็จ {succeeded} ไฟล์" + (f" · มีปัญหา {len(self.errors)} ไฟล์" if self.errors else " · พร้อมใช้งาน"),
                                                  text_color=C["error"] if self.errors else C["success"])
                    self.status.set("บันทึกแล้ว · เปิดโฟลเดอร์ผลลัพธ์เพื่อดูภาพ" if not self.errors else "บางไฟล์แปลงไม่ได้ · กดดูข้อผิดพลาดเพื่อตรวจสอบ")
                    if self.warning_count:
                        self.status.set((f"มีปัญหา {len(self.errors)} ไฟล์ · " if self.errors else "บันทึกแล้ว · ") + f"{self.warning_count} ภาพเกินเพดาน · ไม่ลดคุณภาพเอง · ดู image_report.csv")
                    if self.errors or self.warning_count:
                        self.error_button.configure(text="ดูคำเตือน")
                        self.error_button.grid(row=0, column=1, padx=(0, S["sm"]))
        except queue.Empty:
            pass

    def show_errors(self):
        if self.errors or self.warnings:
            details = self.errors + self.warnings
            if self.warning_count:
                details.append(f"รวม {self.warning_count} ภาพเกินเพดาน · แสดงไม่เกิน 50 รายการ\nดูขนาดจริงทั้งหมดใน image_report.csv แต่ละโฟลเดอร์\nบันทึกตามค่าที่เลือก ไม่มีการลดคุณภาพหรือพิกเซลอัตโนมัติ")
            messagebox.showwarning("ผลการแปลงภาพ", "\n\n".join(details), parent=self.root)

    def open_output(self):
        if self.destination and not self.busy:
            try:
                os.startfile(str(self.destination.resolve()))
            except OSError as error:
                self.validation_error(f"เปิดโฟลเดอร์ไม่ได้ · {error}")
