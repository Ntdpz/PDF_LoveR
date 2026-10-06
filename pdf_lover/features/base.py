"""Common page contract: shell owns navigation and the job lock."""
from abc import ABC, abstractmethod
import threading
import customtkinter as ctk
from pdf_lover.ui.controls import UIControls
from pdf_lover.ui.theme import COLORS
from pdf_lover.ui.theme import SPACE


class ToolPage(ctk.CTkFrame, UIControls, ABC):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=COLORS["paper"], corner_radius=0)
        self.app = app
        self.root = app.root
        self.font_body = app.font_body
        self.font_small = app.font_small
        self.font_bold = app.font_bold
        self.font_title = app.font_title
        self.page_visible = False
        self.cancel_event = threading.Event()

    def set_job_running(self, running, new_job=False):
        if new_job:
            self.cancel_event = threading.Event()
        if hasattr(self, "cancel_button"):
            if running:
                self.cancel_button.configure(state="normal", text="ยกเลิก")
                self.cancel_button.grid(row=0, column=3, padx=SPACE['sm'])
                self.tool_menu.configure(width=120)
            else:
                self.cancel_button.grid_forget()
                self.tool_menu.configure(width=176)

    def report_progress(self, message):
        if not self.cancel_event.is_set():
            self.status.set(message)

    def request_cancel(self):
        if self.busy and not self.cancel_event.is_set():
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled", text="กำลังหยุด…")
            self.status.set("กำลังยกเลิก · รอขั้นตอนที่กำลังเขียนไฟล์…")

    def set_active(self, active):
        """Retain document/settings state, release preview resources on hidden pages."""
        self.page_visible = active
        if hasattr(self, "activity_indicator"):
            self.activity_indicator.set_active(active)
        def visit(widget):
            if hasattr(widget, "set_preview_active"):
                widget.set_preview_active(active)
            for child in widget.winfo_children():
                visit(child)
        for child in self.winfo_children():
            visit(child)

    @property
    def busy(self):
        return self.app.busy

    @busy.setter
    def busy(self, value):
        self.app.busy = value

    @abstractmethod
    def add_files(self):
        raise NotImplementedError

    @abstractmethod
    def add_paths(self, paths):
        raise NotImplementedError

    @abstractmethod
    def start(self):
        raise NotImplementedError

    @abstractmethod
    def process_events(self):
        raise NotImplementedError
