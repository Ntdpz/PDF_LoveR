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
