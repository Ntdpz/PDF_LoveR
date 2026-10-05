"""Small shared activity badge, advanced only by the shell's existing poll."""
import ctypes
import math
import sys
import time
import tkinter as tk
import customtkinter as ctk
from pdf_lover.ui.theme import COLORS as C


def system_motion_enabled():
    if sys.platform != "win32":
        return True
    enabled = ctypes.c_int(1)
    try:
        return bool(ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)
    except (AttributeError, OSError):
        return True


class ActivityIndicator(ctk.CTkFrame):
    """No private timers, images or workers; hidden and idle badges do not tick."""
    def __init__(self, parent, font):
        super().__init__(parent, fg_color=C["graphite"], corner_radius=0, width=164, height=44)
        self.grid_propagate(False)
        self.grid_columnconfigure(1, weight=1)
        self.running = False
        self.visible = False
        self.started = None
        self.motion_enabled = system_motion_enabled()
        self.elapsed_seconds = 0
        self.frame_count = 0
        self.canvas = tk.Canvas(self, width=30, height=30, bg=C["graphite"], highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, padx=(0, 5), pady=7)
        self.track = self.canvas.create_oval(4, 4, 26, 26, outline=C["muted"], width=2)
        self.arc = self.canvas.create_arc(4, 4, 26, 26, start=90, extent=110, style="arc", outline=C["accent-ink"], width=3, state="hidden")
        self.dot = self.canvas.create_oval(11, 11, 19, 19, fill=C["graphite-muted"], outline="")
        self.text = ctk.CTkLabel(self, text="พร้อมทำงาน", font=font, text_color=C["graphite-muted"], anchor="w", justify="left")
        self.text.grid(row=0, column=1, sticky="ew")

    def set_active(self, active):
        self.visible = active
        if active and self.running:
            self.tick()

    def set_running(self, running):
        if self.running == bool(running):
            return
        self.running = bool(running)
        self.started = time.perf_counter() if self.running else None
        self.elapsed_seconds = 0
        self.canvas.itemconfigure(self.arc, state="normal" if self.running else "hidden")
        self.canvas.itemconfigure(self.dot, state="hidden" if self.running else "normal")
        self.text.configure(text="กำลังทำงาน\n00:00" if self.running else "พร้อมทำงาน",
                            text_color=C["accent-ink"] if self.running else C["graphite-muted"])
        self.tick()

    def tick(self, now=None):
        if not self.running or not self.visible or not self.winfo_exists():
            return
        elapsed = max(0, (time.perf_counter() if now is None else now) - self.started)
        seconds = int(elapsed)
        if seconds != self.elapsed_seconds:
            self.elapsed_seconds = seconds
            minutes, seconds = divmod(seconds, 60)
            self.text.configure(text=f"กำลังทำงาน\n{minutes:02}:{seconds:02}")
        if self.motion_enabled and self.winfo_ismapped():
            # Twelve lightweight Canvas updates/second; no animation in idle/home.
            self.canvas.itemconfigure(self.arc, start=90 - (elapsed * 240) % 360,
                                      extent=110 + 30 * math.sin(elapsed * math.pi))
            self.frame_count += 1
