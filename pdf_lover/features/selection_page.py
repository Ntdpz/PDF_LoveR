"""Hallmark · native selection workbench · existing Cobalt design system.

Pre-emit critique: P4 H5 E4 S5 R5 V4. Selection and result preview precede save.
Workers receive immutable plans and report queues; all Tk access stays here.
"""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from pdf_lover.core.cancellation import Cancelled, checkpoint
import customtkinter as ctk

from pdf_lover.features.base import ToolPage
from pdf_lover.core.document import DocumentError as SplitError, inspect_document
from pdf_lover.core.pdf_output import export_pages
from pdf_lover.platform.paths import documents_folder
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.theme import COLORS as C, SPACE as S, FONTS


class SelectionPage(ToolPage):
    """Shared workbench for extract/delete; feature subclasses supply the headless planner."""
    TITLE = "เลือกหน้า"
    SUFFIX = "_เลือกหน้า"
    DELETE = False
    SAVE_LABEL = "บันทึกหน้าที่เลือก"
    inspect = staticmethod(inspect_document)
    export = staticmethod(export_pages)
    PREVIEW_LIMIT = 25

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.info = self.plan = self.destination = None
        self.events = queue.Queue()
        self.mode = tk.StringVar(value="single")
        self.output = tk.StringVar(value=str(documents_folder()))
        self.prefix = tk.StringVar(value="เอกสารแยก")
        self.status = tk.StringVar(value="เลือก PDF หนึ่งไฟล์ หรือวางไฟล์จาก Explorer")
        self.controls = []
        self.preview_offset = 0
        self._build()
        for value in (self.mode, self.output, self.prefix):
            value.trace_add("write", self._settings_changed)
        self.refresh_plan()

    def _entry(self, parent, variable, width=180):
        entry = ctk.CTkEntry(parent, textvariable=variable, height=44, width=width,
                             font=self.font_small, fg_color=C["surface"], text_color=C["ink"],
                             border_width=2, border_color=C["rule"])
        self.app._entry_focus(entry)
        self.controls.append(entry)
        return entry

    def _build(self):
        from pdf_lover.ui.workbench import selection_workbench
        selection_workbench(self, split=False)

    def _settings_changed(self, *_):
        if hasattr(self, "results") and not self.busy:
            self.preview_offset = 0
            self.destination = None
            self.open_button.configure(state="disabled")
            self.progress.set(0)
            self.refresh_plan()

    def refresh_plan(self):
        self.plan = None
        mode = self.mode.get()
        for button, value in zip(self.mode_buttons, ("single", "pages")):
            button.configure(fg_color=C["tint"] if mode == value else C["surface"],
                             border_color=C["accent"] if mode == value else C["rule"])
        self.selector.set_enabled(not self.busy)
        if self.info:
            try:
                if not self.output.get().strip():
                    raise SplitError("เลือกโฟลเดอร์ปลายทางก่อนบันทึก")
                if self.DELETE and not self.selector.expression.get().strip():
                    raise SplitError("เลือกหน้าที่จะลบ · ต้องเหลืออย่างน้อยหนึ่งหน้า")
                self.plan = self.build_plan(self.info, self.output.get(), self.prefix.get(),
                                            self.selector.expression.get(), mode)
                total = sum(len(item.pages) for item in self.plan.outputs)
                summary = f"ผลลัพธ์ · {len(self.plan.outputs)} ไฟล์ · {total} หน้า"
                if self.DELETE:
                    summary = f"ลบ {self.info.page_count-total} หน้า · เหลือ {total} หน้า"
                self.summary.configure(text=summary)
                self.status.set("ตรวจหน้าและชื่อไฟล์ก่อนบันทึก · เก็บต้นฉบับไว้")
                self.status_label.configure(text_color=C["muted"])
            except SplitError as error:
                self.status.set(str(error))
                self.status_label.configure(text_color=C["error"])
        if self.plan is None:
            self.summary.configure(text="ไฟล์ที่จะได้ · รอข้อมูลที่ถูกต้อง")
        self.start_button.configure(state="normal" if self.plan and not self.busy else "disabled")
        self.render_outputs()

    def preview_rows(self):
        if not self.plan:
            return ()
        return tuple((f"{index} (เดิม {page})", output.path.name)
                     for output in self.plan.outputs for index, page in enumerate(output.pages, 1))

    def render_outputs(self):
        self.results.delete(*self.results.get_children())
        rows = self.preview_rows()
        for row in rows[self.preview_offset:self.preview_offset + self.PREVIEW_LIMIT]:
            self.results.insert("", "end", values=row)
        self.output_counter.configure(text=f"{self.preview_offset + 1}–{min(self.preview_offset + self.PREVIEW_LIMIT, len(rows))} / {len(rows)}" if rows else "—")
        self.prev_outputs.configure(state="normal" if self.preview_offset and not self.busy else "disabled")
        self.next_outputs.configure(state="normal" if self.preview_offset + self.PREVIEW_LIMIT < len(rows) and not self.busy else "disabled")

    def move_outputs(self, direction):
        if self.plan and not self.busy:
            self.preview_offset = max(0, min(((len(self.preview_rows()) - 1) // self.PREVIEW_LIMIT) * self.PREVIEW_LIMIT,
                                           self.preview_offset + direction * self.PREVIEW_LIMIT))
            self.render_outputs()

    def add_files(self):
        if not self.busy:
            path = filedialog.askopenfilename(parent=self.root, title="เลือก PDF", filetypes=[("PDF", "*.pdf")])
            if path:
                self.add_paths([path])

    def add_paths(self, paths):
        if self.busy:
            return
        paths = list(paths)
        if len(paths) != 1:
            self.status.set("เลือก PDF ครั้งละหนึ่งไฟล์")
            return
        self.info = self.plan = self.destination = None
        self.selector.set_document(None)
        self.source_label.configure(text=f"กำลังอ่าน · {self.shorten(Path(paths[0]).name, 48)}")
        self._lock("กำลังอ่านจำนวนหน้า PDF…")
        threading.Thread(target=self._inspect_worker, args=(Path(paths[0]),), daemon=True).start()

    def _inspect_worker(self, path):
        try:
            checkpoint(self.cancel_event)
            info = self.inspect(path)
            checkpoint(self.cancel_event)
            self.events.put(("loaded", info))
        except Cancelled as error:
            self.events.put(("cancelled", str(error)))
        except Exception as error:
            self.events.put(("error", str(error)))

    def choose_output(self):
        if not self.busy:
            folder = filedialog.askdirectory(parent=self.root, initialdir=self.output.get(), title="เลือกโฟลเดอร์สำหรับชุด PDF")
            if folder:
                self.output.set(folder)

    def _lock(self, message):
        self.busy = True
        self.status.set(message)
        self.status_label.configure(text_color=C["muted"])
        for control in self.controls:
            control.configure(state="disabled")
        self.selector.set_enabled(False)
        self.start_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.render_outputs()

    def start(self):
        if self.busy:
            return
        self.refresh_plan()
        if self.plan:
            plan = self.plan
            self.destination = None
            self.progress.set(0)
            self._lock("กำลังสร้าง PDF ใหม่และตรวจจำนวนหน้า…")
            threading.Thread(target=self._export_worker, args=(plan,), daemon=True).start()

    def _export_worker(self, plan):
        try:
            outputs = self.export(plan, lambda done, total, name: self.events.put(("progress", done, total, name)), cancel=self.cancel_event)
            self.events.put(("done", outputs))
        except Cancelled as error:
            self.events.put(("cancelled", str(error)))
        except Exception as error:
            self.events.put(("error", str(error)))

    def process_events(self):
        self.selector.process_events()
        try:
            for _ in range(100):
                event = self.events.get_nowait()
                if event[0] == "progress":
                    self.progress.set(event[1] / event[2] * 0.9)
                    self.report_progress(f"เตรียมไฟล์ {event[1]}/{event[2]} · {event[3]}")
                    continue
                self.busy = False
                for control in self.controls:
                    control.configure(state="normal")
                if event[0] == "loaded":
                    self.info = event[1]
                    self.prefix.set(self.info.path.stem[:90] + self.SUFFIX)
                    self.source_label.configure(text=f"{self.shorten(self.info.path.name, 48)} · {self.info.page_count} หน้า")
                    self.selector.set_document(self.info)
                    self.preview_offset = 0
                    self.refresh_plan()
                else:
                    self.selector.set_enabled(True)
                    self.start_button.configure(state="normal" if self.plan else "disabled")
                    self.render_outputs()
                    if event[0] == "done":
                        self.destination = event[1][0].parent
                        self.progress.set(1)
                        self.status.set(f"บันทึกสำเร็จ · {len(event[1])} ไฟล์ · เก็บต้นฉบับไว้แล้ว")
                        self.status_label.configure(text_color=C["success"])
                        self.open_button.configure(state="normal")
                        self.start_button.configure(state="disabled")
                    else:
                        self.progress.set(0)
                        self.status.set(event[1])
                        self.status_label.configure(text_color=C["muted"] if event[0] == "cancelled" else C["error"])
        except queue.Empty:
            pass

    def open_result(self):
        if self.destination and not self.busy:
            try:
                os.startfile(str(self.destination))
            except OSError:
                self.status.set("เปิดโฟลเดอร์ไม่ได้ · ตรวจว่าปลายทางยังอยู่")
