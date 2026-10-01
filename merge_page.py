"""PDF LoveR merge workbench; consumes the established native design tokens."""
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from home_page import tool_icon
from pdf_merge import inspect_pdf, merge_pdfs, MergeError
from ui_theme import COLORS as C, FONTS, RADIUS, SPACE as S


class MergePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=C["paper"], corner_radius=0)
        self.app = app
        self.files = []
        self.page_counts = {}
        self.events = queue.Queue()
        self.output = tk.StringVar()
        self.status = tk.StringVar(value="เพิ่ม PDF อย่างน้อย 2 ไฟล์ แล้วจัดลำดับก่อนรวม")
        self.busy = False
        self.destination = None
        self.controls = []
        self.name_labels = []
        self._build()
        self.render_files()
        self.app.root.bind("<Configure>", self._resize, add="+")

    def label(self, parent, text="", **kwargs):
        return self.app.label(parent, text, **kwargs)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        self.label(header, "", image=tool_icon("pages", "accent", 36)).grid(row=0, column=0, padx=(S["2xl"], S["md"]), pady=S["lg"])
        self.label(header, "รวม PDF", font=ctk.CTkFont(family=FONTS["body"], size=22, weight="bold")).grid(row=0, column=1, sticky="w")
        self.home_button = self.app.button(header, "เครื่องมือทั้งหมด", self.app.show_home, width=200)
        self.home_button.grid(row=0, column=2, padx=S["2xl"], pady=S["md"])
        self.controls.append(self.home_button)
        intro = ctk.CTkFrame(self, fg_color="transparent")
        intro.grid(row=1, column=0, sticky="ew", padx=S["2xl"], pady=(S["lg"], S["lg"]))
        self.label(intro, "รวม PDF ตามลำดับของคุณ", font=ctk.CTkFont(family=FONTS["body"], size=28, weight="bold")).pack(anchor="w")
        self.label(intro, "เพิ่มเอกสาร เรียงลำดับ แล้วบันทึกทุกหน้าเป็น PDF ไฟล์เดียว", color="muted").pack(anchor="w", pady=(S["xs"], 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=S["2xl"])
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, minsize=304)
        body.grid_rowconfigure(0, weight=1)
        panel = ctk.CTkFrame(body, fg_color=C["surface"], border_color=C["rule"], border_width=1, corner_radius=RADIUS["panel"])
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, S["xl"]))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(panel, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=S["xl"], pady=S["lg"])
        toolbar.grid_columnconfigure(0, weight=1)
        self.count_label = self.label(toolbar, "ลำดับเอกสาร", font=self.app.font_bold)
        self.count_label.grid(row=0, column=0, sticky="w")
        self.add_button = self.app.button(toolbar, "+  เพิ่ม PDF", self.add_files, width=120)
        self.add_button.grid(row=0, column=1)
        self.controls.append(self.add_button)
        self.file_area = ctk.CTkFrame(panel, fg_color="transparent")
        self.file_area.grid(row=1, column=0, sticky="nsew", padx=S["lg"])
        self.file_area.grid_columnconfigure(0, weight=1)
        self.file_area.grid_rowconfigure(0, weight=1)
        bottom = ctk.CTkFrame(panel, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=S["xl"], pady=S["lg"])
        bottom.grid_columnconfigure(0, weight=1)
        self.label(bottom, "ใช้ปุ่มขึ้น / ลงเพื่อเปลี่ยนลำดับ", font=self.app.font_small, color="muted").grid(row=0, column=0, sticky="w")
        self.clear_button = self.app.button(bottom, "ล้างรายการ", self.clear_files, width=104)
        self.clear_button.grid(row=0, column=1)
        self.controls.append(self.clear_button)
        settings = ctk.CTkScrollableFrame(body, width=284, fg_color="transparent", corner_radius=0,
                                        scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        settings.grid(row=0, column=1, sticky="nsew")
        settings.grid_columnconfigure(0, weight=1)
        self.label(settings, "ไฟล์ผลลัพธ์", font=self.app.font_bold).grid(row=0, column=0, sticky="w", pady=(S["sm"], S["lg"]))
        self.label(settings, "ตำแหน่งและชื่อไฟล์ PDF").grid(row=1, column=0, sticky="w", pady=(0, S["sm"]))
        self.output_entry = ctk.CTkEntry(settings, textvariable=self.output, height=44, font=self.app.font_small,
                                        fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"], border_width=2,
                                        corner_radius=RADIUS["control"])
        self.output_entry.grid(row=2, column=0, sticky="ew", pady=(0, S["sm"]))
        self.app._entry_focus(self.output_entry)
        self.controls.append(self.output_entry)
        self.browse_button = self.app.button(settings, "เลือกที่บันทึก…", self.choose_output, width=200)
        self.browse_button.grid(row=3, column=0, sticky="ew", pady=(0, S["lg"]))
        self.controls.append(self.browse_button)
        self.label(settings, "เลือกชื่อใหม่เพื่อเก็บไฟล์เดิมไว้", font=self.app.font_small, color="muted").grid(row=4, column=0, sticky="w")
        self.summary = self.label(settings, "0 ไฟล์ · 0 หน้า", font=ctk.CTkFont(family=FONTS["body"], size=23, weight="bold"))
        self.summary.grid(row=5, column=0, sticky="w", pady=(S["2xl"], S["sm"]))
        self.label(settings, "ทุกหน้าตามลำดับในรายการ\nข้อความและภาพยังอยู่ใน PDF", color="muted", justify="left").grid(row=6, column=0, sticky="w")
        self.label(settings, "ทำงานออฟไลน์บนเครื่องคุณ", font=self.app.font_small, color="muted").grid(row=7, column=0, sticky="w", pady=(S["xl"], 0))
        activity = ctk.CTkFrame(self, fg_color=C["surface"], border_color=C["rule"], border_width=1, corner_radius=RADIUS["panel"])
        activity.grid(row=3, column=0, sticky="ew", padx=S["2xl"], pady=(S["lg"], S["md"]))
        activity.grid_columnconfigure(0, weight=1)
        self.activity_title = self.label(activity, "พร้อมเมื่อคุณเลือกเอกสาร", font=self.app.font_bold)
        self.activity_title.grid(row=0, column=0, sticky="w", padx=S["xl"], pady=(S["lg"], 0))
        self.progress = ctk.CTkProgressBar(activity, height=6, fg_color=C["soft"], progress_color=C["accent"])
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=S["xl"], pady=S["md"])
        self.status_label = self.label(activity, "", textvariable=self.status, font=self.app.font_small, color="muted", wraplength=570, justify="left")
        self.status_label.grid(row=2, column=0, sticky="w", padx=S["xl"], pady=(0, S["lg"]))
        self.start_button = self.app.button(activity, "รวมและบันทึก PDF", self.start, primary=True, width=220)
        self.start_button.grid(row=0, column=1, rowspan=3, padx=(S["sm"], S["xl"]), pady=S["lg"])
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=4, column=0, sticky="ew", padx=S["2xl"], pady=(0, S["md"]))
        foot.grid_columnconfigure(0, weight=1)
        self.label(foot, "Ctrl + O เพิ่ม PDF  ·  Ctrl + Enter รวมไฟล์", font=self.app.font_small, color="muted").grid(row=0, column=0, sticky="w")
        self.open_button = self.app.button(foot, "เปิด PDF ที่รวมแล้ว", self.open_result, width=200)
        self.open_button.grid(row=0, column=1)
        self.open_button.configure(state="disabled")

    def _resize(self, event):
        if event.widget is self.app.root:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            self.status_label.configure(wraplength=max(260, event.width / scale - 380))
            for path, label in self.name_labels:
                label.configure(text=self.app.fit_filename(path.name, max(140, event.width / scale - 580)))

    def render_files(self):
        for child in self.file_area.winfo_children():
            child.destroy()
        self.name_labels.clear()
        self.count_label.configure(text=f"ลำดับเอกสาร · {len(self.files)} ไฟล์" if self.files else "ลำดับเอกสาร")
        self.summary.configure(text=f"{len(self.files)} ไฟล์ · {sum(self.page_counts.get(path, 0) for path in self.files)} หน้า")
        self.clear_button.configure(state="normal" if self.files and not self.busy else "disabled")
        if not self.files:
            empty = ctk.CTkFrame(self.file_area, fg_color="transparent")
            empty.grid(row=0, column=0)
            self.label(empty, "", image=tool_icon("pages", "accent", 48)).pack(pady=(0, S["lg"]))
            self.label(empty, "เอกสารไหนมาก่อน?", font=self.app.font_bold).pack()
            self.label(empty, "เพิ่ม PDF อย่างน้อย 2 ไฟล์เพื่อเริ่มรวม", color="muted").pack(pady=(S["xs"], S["lg"]))
            self.app.button(empty, "เลือกไฟล์ PDF…", self.add_files, width=176).pack()
            return
        scroll = ctk.CTkScrollableFrame(self.file_area, fg_color="transparent", corner_radius=0,
                                        scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        for index, path in enumerate(self.files):
            row = ctk.CTkFrame(scroll, fg_color=C["paper"], corner_radius=RADIUS["control"])
            row.grid(row=index, column=0, sticky="ew", pady=(0, S["sm"]))
            row.grid_columnconfigure(1, weight=1)
            self.label(row, str(index + 1), font=self.app.font_bold, color="muted", width=32, anchor="center").grid(row=0, column=0, rowspan=2, padx=S["sm"], pady=S["lg"])
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            label = self.label(row, self.app.fit_filename(path.name, max(140, self.app.root.winfo_width() / scale - 580)), font=self.app.font_bold)
            label.grid(row=0, column=1, sticky="w", pady=(S["md"], 0))
            self.name_labels.append((path, label))
            self.label(row, f"{self.page_counts[path]} หน้า", font=self.app.font_small, color="muted").grid(row=1, column=1, sticky="w", pady=(0, S["md"]))
            for column, (text, action, enabled) in enumerate((
                ("ขึ้น", lambda p=path: self.move_file(p, -1), index > 0),
                ("ลง", lambda p=path: self.move_file(p, 1), index < len(self.files) - 1),
                ("×", lambda p=path: self.remove_file(p), True),
            ), start=2):
                button = self.app.button(row, text, action, width=44)
                button.grid(row=0, column=column, rowspan=2, padx=(S["xs"], S["xs"]))
                button.configure(state="normal" if enabled and not self.busy else "disabled")

    def changed(self):
        self.progress.set(0)
        self.activity_title.configure(text="พร้อมรวมเอกสาร" if len(self.files) >= 2 else "เพิ่ม PDF อย่างน้อย 2 ไฟล์", text_color=C["ink"])
        self.status.set("จัดลำดับแล้วเลือกที่บันทึก ก่อนกดรวมและบันทึก PDF")
        self.start_button.configure(text="รวมและบันทึก PDF")

    def add_files(self):
        if not self.app.busy:
            self.add_paths(filedialog.askopenfilenames(parent=self.app.root, title="เลือก PDF ที่ต้องการรวม", filetypes=[("PDF", "*.pdf")]))

    def add_paths(self, paths):
        if self.app.busy:
            return
        known = {os.path.normcase(str(path)) for path in self.files}
        errors = []
        for name in paths:
            path = Path(name).resolve()
            if os.path.normcase(str(path)) in known:
                continue
            try:
                pages = inspect_pdf(path)
                self.files.append(path)
                self.page_counts[path] = pages
                known.add(os.path.normcase(str(path)))
            except MergeError as error:
                errors.append(str(error))
        self.render_files()
        self.changed()
        if errors:
            self.error("เพิ่มบางไฟล์ไม่ได้ · " + " | ".join(errors[:2]) + (f" · อีก {len(errors) - 2} ไฟล์" if len(errors) > 2 else ""))

    def move_file(self, path, direction):
        if not self.app.busy and path in self.files:
            index = self.files.index(path)
            other = index + direction
            if 0 <= other < len(self.files):
                self.files[index], self.files[other] = self.files[other], self.files[index]
                self.render_files()
                self.changed()

    def remove_file(self, path):
        if not self.app.busy and path in self.files:
            self.files.remove(path)
            self.page_counts.pop(path, None)
            self.render_files()
            self.changed()

    def clear_files(self):
        if not self.app.busy:
            self.files.clear()
            self.page_counts.clear()
            self.render_files()
            self.changed()

    def choose_output(self):
        if self.app.busy:
            return
        initial = Path(self.output.get()) if self.output.get() else (self.files[0].parent if self.files else Path.home()) / "รวมเอกสาร.pdf"
        path = filedialog.asksaveasfilename(parent=self.app.root, title="เลือกที่บันทึก PDF ที่รวมแล้ว", defaultextension=".pdf",
                                           filetypes=[("PDF", "*.pdf")], initialdir=str(initial.parent), initialfile=initial.name,
                                           confirmoverwrite=False)
        if path:
            self.output.set(path)
            self.output_entry.configure(border_color=C["rule"])

    def error(self, message, field=False):
        self.activity_title.configure(text="ตรวจสอบข้อมูลก่อนรวม", text_color=C["error"])
        self.status.set(message)
        if field:
            self.output_entry.focus_set()
            self.output_entry.configure(border_color=C["error"])

    def start(self):
        if self.app.busy:
            return
        if len(self.files) < 2:
            self.error("เพิ่ม PDF อย่างน้อย 2 ไฟล์ก่อนรวม")
            return
        if not self.output.get().strip():
            self.error("ยังไม่ได้เลือกที่บันทึก · กดเลือกที่บันทึกเพื่อกำหนดชื่อ PDF", True)
            return
        try:
            target = Path(self.output.get().strip()).expanduser().resolve()
        except (OSError, ValueError):
            self.error("ตำแหน่งไฟล์ไม่ถูกต้อง · กดเลือกที่บันทึกเพื่อเลือกใหม่", True)
            return
        if target in self.files:
            self.error("ปลายทางเป็นไฟล์ต้นฉบับ · เลือกชื่อไฟล์ใหม่", True)
            return
        if target.exists():
            self.error("ชื่อไฟล์นี้มีอยู่แล้ว · เลือกชื่อใหม่เพื่อเก็บไฟล์เดิมไว้", True)
            return
        if target.suffix.lower() != ".pdf" or not target.parent.is_dir():
            self.error("เลือกโฟลเดอร์ที่มีอยู่ และชื่อไฟล์ที่ลงท้ายด้วย .pdf", True)
            return
        self.busy = self.app.busy = True
        self.open_button.configure(state="disabled")
        for control in self.controls:
            control.configure(state="disabled")
        self.start_button.configure(state="disabled", text="กำลังรวม PDF…", fg_color=C["soft"], border_color=C["rule"])
        self.activity_title.configure(text="กำลังรวมเอกสาร", text_color=C["ink"])
        self.status.set("กำลังอ่าน PDF ตามลำดับในรายการ")
        self.progress.set(0)
        self.render_files()
        threading.Thread(target=self._worker, args=(list(self.files), target), daemon=True).start()

    def _worker(self, paths, target):
        try:
            pages = merge_pdfs(paths, target, lambda done, total, pages, all_pages, name: self.events.put(("progress", done, total, pages, all_pages, name)))
            self.events.put(("done", target, pages))
        except MergeError as error:
            self.events.put(("error", str(error)))
        except OSError:
            self.events.put(("error", "บันทึก PDF ไม่ได้ · ตรวจสิทธิ์โฟลเดอร์หรือเลือกที่บันทึกใหม่"))
        except Exception:
            self.events.put(("error", "รวม PDF ไม่สำเร็จ · ตรวจเอกสารต้นฉบับแล้วลองอีกครั้ง"))

    def process_events(self):
        try:
            for _ in range(100):
                event = self.events.get_nowait()
                if event[0] == "progress":
                    _, done, total, pages, all_pages, name = event
                    self.progress.set(done / total * 0.9)
                    self.status.set(f"อ่านแล้ว {done}/{total} ไฟล์ · {pages}/{all_pages} หน้า · กำลังเตรียมบันทึก")
                else:
                    self.busy = self.app.busy = False
                    for control in self.controls:
                        control.configure(state="normal")
                    self.start_button.configure(state="normal", text="รวมและบันทึก PDF", fg_color=C["accent"], border_color=C["accent"])
                    self.render_files()
                    if event[0] == "done":
                        self.destination = event[1]
                        self.progress.set(1)
                        self.activity_title.configure(text=f"รวมสำเร็จ · {event[2]} หน้า", text_color=C["success"])
                        self.status.set(f"บันทึกแล้ว · {self.app.shorten(event[1].name, 48)}")
                        self.open_button.configure(state="normal")
                    else:
                        self.progress.set(0)
                        self.error(event[1])
        except queue.Empty:
            pass

    def open_result(self):
        if self.destination and not self.app.busy:
            try:
                os.startfile(str(self.destination))
            except OSError:
                self.error("เปิดไฟล์ไม่ได้ · ตรวจว่า PDF ที่รวมแล้วยังอยู่ในตำแหน่งเดิม")
