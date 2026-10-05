"""Common page contract: shell owns navigation and the job lock."""
from abc import ABC, abstractmethod
import customtkinter as ctk
from pdf_lover.ui.controls import UIControls
from pdf_lover.ui.theme import COLORS


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
