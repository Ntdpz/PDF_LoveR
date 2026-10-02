"""Delayed native tooltip for mouse and keyboard users; all callbacks run on Tk."""
import customtkinter as ctk
from pdf_lover.ui.theme import COLORS as C


class Tooltip:
    def __init__(self, widget, text, font):
        self.widget = widget
        self.text = text
        self.font = font
        self.timer = self.window = None
        widget.bind("<Enter>", self.schedule, add=True)
        widget.bind("<Leave>", self.hide, add=True)
        widget.bind("<ButtonPress-1>", self.hide, add=True)
        widget._canvas.bind("<FocusIn>", self.schedule, add="+")
        widget._canvas.bind("<FocusOut>", self.hide, add="+")
        widget._canvas.bind("<Escape>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add=True)

    def schedule(self, _=None):
        self.hide()
        if self.widget.cget("state") == "normal":
            self.timer = self.widget.after(450, self.show)

    def show(self):
        self.timer = None
        if not self.widget.winfo_exists() or not self.widget.winfo_viewable() or self.widget.cget("state") != "normal":
            return
        self.window = window = ctk.CTkToplevel(self.widget)
        window.withdraw()
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(fg_color=C["ink"])
        label = ctk.CTkLabel(window, text=self.text, font=self.font,
                            fg_color=C["ink"], text_color=C["surface"], padx=12, pady=6)
        label.pack()
        window.update_idletasks()
        x = min(self.widget.winfo_rootx(), self.widget.winfo_screenwidth() - window.winfo_reqwidth() - 8)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        if y + window.winfo_reqheight() > self.widget.winfo_screenheight():
            y = self.widget.winfo_rooty() - window.winfo_reqheight() - 6
        window.geometry(f"+{max(0,x)}+{max(0,y)}")
        window.deiconify()

    def hide(self, _=None):
        if self.timer is not None:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
