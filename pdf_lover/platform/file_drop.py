"""Native Explorer file drops, separate from the Canvas card reorder gesture."""
import os
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

from pdf_lover.ui.theme import COLORS as C, RADIUS, SPACE as S


class FileDrop:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.version = TkinterDnD._require(self.root)
        self.root.tk.call("tkdnd::drop_target", "register", self.root._w, (DND_FILES,))
        # Bind Tcl's native drop substitutions on the existing CTk root. No
        # replacement root or global monkey-patching of Tk widgets is needed.
        for sequence, callback, arguments in (
            ("<<DropEnter>>", self.enter, ""),
            ("<<DropPosition>>", self.action, ""),
            ("<<DropLeave>>", self.leave, ""),
            ("<<Drop>>", self.receive, "%D"),
        ):
            command = self.root.register(callback)
            self.root.tk.call("bind", self.root._w, sequence, f"{command} {arguments}")
        self.banner = ctk.CTkFrame(self.root, fg_color=C["tint"], border_color=C["accent"],
                                  border_width=2, corner_radius=RADIUS["panel"])
        self.label = app.label(self.banner, "", font=app.font_bold, color="accent")
        self.label.pack(padx=S["xl"], pady=S["lg"])
        self.hide_timer = None
        self.pending_timer = None
        self.pending = []
        self.skipped = 0
        self.closed = False
        self.root.bind("<Destroy>", self._destroyed, add="+")

    def show(self, message, temporary=False):
        if self.hide_timer is not None:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None
        self.label.configure(text=message)
        self.banner.place(relx=0.5, y=16, anchor="n")
        self.banner.lift()
        if temporary:
            self.hide_timer = self.root.after(3000, self.leave)

    def action(self):
        return REFUSE_DROP if self.app.busy else COPY

    def enter(self):
        message = ("กำลังทำงานอยู่ · เพิ่มไฟล์ได้เมื่อเสร็จ" if self.app.busy else
                   "วาง PDF เพื่อเปิดในเครื่องมือที่เลือก" if self.app.route != "home" else
                   "วาง PDF เพื่อเพิ่มเข้าเครื่องมือรวมไฟล์")
        self.show(message)
        return self.action()

    def leave(self):
        if self.hide_timer is not None:
            self.root.after_cancel(self.hide_timer)
            self.hide_timer = None
        self.banner.place_forget()
        return self.action()

    def receive(self, data):
        self.leave()
        if self.closed or self.app.busy:
            return REFUSE_DROP
        try:
            names = self.root.tk.splitlist(data)
        except tk.TclError:
            self.show("อ่านรายการไฟล์ไม่ได้ · ลองลากไฟล์ PDF อีกครั้ง", temporary=True)
            return REFUSE_DROP
        accepted = []
        skipped = 0
        for name in names:
            try:
                path = Path(name).resolve()
                valid = path.suffix.lower() == ".pdf" and path.is_file()
            except (OSError, ValueError):
                valid = False
            if valid:
                accepted.append(path)
            else:
                skipped += 1
        if not accepted:
            self.show("รับเฉพาะไฟล์ PDF · ไม่รองรับโฟลเดอร์", temporary=True)
            return REFUSE_DROP
        known = {os.path.normcase(str(path)) for path in self.pending}
        for path in accepted:
            key = os.path.normcase(str(path))
            if key not in known:
                self.pending.append(path)
                known.add(key)
        self.skipped += skipped
        if self.pending_timer is None:
            # Finish the OLE drop first; PDF inspection and UI rendering happen
            # on the next Tk event turn rather than blocking Explorer's drag.
            self.pending_timer = self.root.after(0, self._apply)
        return COPY

    def _apply(self):
        self.pending_timer = None
        paths, skipped = self.pending, self.skipped
        self.pending, self.skipped = [], 0
        if self.closed or self.app.busy:
            return
        self.app.accept_paths(paths)
        if skipped:
            self.show(f"เพิ่ม PDF แล้ว · ข้ามไฟล์ชนิดอื่นหรือโฟลเดอร์ {skipped} รายการ", temporary=True)

    def close(self):
        self.closed = True
        for timer in (self.hide_timer, self.pending_timer):
            if timer is not None:
                self.root.after_cancel(timer)
        self.hide_timer = self.pending_timer = None
        self.pending = []

    def _destroyed(self, event):
        if event.widget is self.root:
            self.close()
