"""Hallmark · component: page selector · modern-minimal · existing Cobalt tokens.

Native states: default / hover / keyboard focus / pressed / disabled / loading /
error / selected. No spatial animation. Pre-emit critique: P4 H5 E4 S5 R5 V4.
Four bounded thumbnails at a time, using the shared spawned preview process.
"""
import queue
import tkinter as tk
import customtkinter as ctk
from PIL import Image
from pdf_lover.core.page_selection import selected_pages, format_pages, PageSelectionError
from pdf_lover.ui.pdf_previews import PreviewWorker, PreviewCache
from pdf_lover.ui.theme import COLORS as C, SPACE as S, RADIUS


class PageSelector(ctk.CTkFrame):
    """Reusable selection, polled by the shell. No feature imports or timer chain."""
    VISIBLE = 4

    def __init__(self, parent, app, changed, *, title="หน้าที่เลือก",
                 hint="เช่น 1-3,5,8-10 · แต่ละช่วงเป็นหนึ่งไฟล์", select_initial=True):
        super().__init__(parent, fg_color=C["surface"], corner_radius=RADIUS["panel"])
        self.app, self.changed = app, changed
        self.select_initial = select_initial
        self.info, self.offset = None, 0
        self.enabled = self.editable = True
        self.expression = tk.StringVar(value="")
        self.worker = PreviewWorker(app.preview_coordinator)
        self.preview_active = False
        self.worker.set_active(False)
        self.pending, self.images = set(), {}
        self.cache = PreviewCache(32, 6 * 1048576, lambda key: self.images.pop(key, None))
        self.selection_key, self.selection_value = None, ()
        self.empty_image = ctk.CTkImage(Image.new("RGB", (1, 1), C["surface"]), size=(1, 1))
        self.grid_columnconfigure(0, weight=1)
        app.label(self, title, font=app.font_bold).grid(row=0, column=0, sticky="w", padx=S["lg"], pady=S["xs"])
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=1, padx=S["lg"])
        self.all_button = app.button(actions, "ทุกหน้า", self.select_all, width=88)
        self.all_button.pack(side="left", padx=S["xs"])
        self.none_button = app.button(actions, "ล้าง", lambda: self.expression.set(""), width=60)
        self.none_button.pack(side="left")
        self.entry = ctk.CTkEntry(self, textvariable=self.expression, height=44, font=app.font_body,
                                fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"], border_width=2)
        self.entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=S["lg"])
        app._entry_focus(self.entry)
        app.label(self, hint, font=app.font_small, color="muted").grid(
            row=2, column=0, columnspan=2, sticky="w", padx=S["lg"], pady=S["sm"])
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.grid(row=3, column=0, columnspan=2, sticky="ew", padx=S["md"])
        self.cards = []
        for index in range(self.VISIBLE):
            strip.grid_columnconfigure(index, weight=1, uniform="pages")
            button = app.button(strip, "—", lambda i=index: self.toggle(self.offset + i + 1), width=80)
            button.configure(height=100, compound="top", font=app.font_small)
            button.grid(row=0, column=index, sticky="ew", padx=S["xs"])
            self.cards.append(button)
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=4, column=0, columnspan=2, sticky="ew", padx=S["lg"], pady=S["xs"])
        nav.grid_columnconfigure(1, weight=1)
        self.previous = app.button(nav, "ก่อนหน้า", lambda: self.move(-1), width=88)
        self.previous.grid(row=0, column=0)
        self.counter = app.label(nav, "ยังไม่มีเอกสาร", font=app.font_small, color="muted", anchor="center")
        self.counter.grid(row=0, column=1, sticky="ew")
        self.next = app.button(nav, "ถัดไป", lambda: self.move(1), width=88)
        self.next.grid(row=0, column=2)
        self.expression.trace_add("write", self._changed)
        self.render()

    def destroy(self):
        self.worker.close()
        super().destroy()

    def set_document(self, info):
        self.info, self.offset = info, 0
        self.cache.clear()
        self.images.clear()
        self.expression.set(f"1-{info.page_count}" if info and self.select_initial else "")
        self.set_enabled(self.enabled, self.editable)

    def select_all(self):
        if self.info and self.enabled and self.editable:
            self.expression.set(f"1-{self.info.page_count}")

    def selection(self):
        key = (self.expression.get(), self.info.page_count if self.info else 0)
        if key != self.selection_key:
            value = selected_pages(*key) if self.info else ()
            self.selection_key, self.selection_value = key, value
        return self.selection_value

    def set_preview_active(self, active):
        if self.preview_active == active:
            return
        self.preview_active = active
        self.worker.set_active(active)
        self.pending.clear()
        if active:
            self.render()
        else:
            for card in self.cards:
                card.configure(image=self.empty_image)
            self.cache.clear()
            self.images.clear()

    def _changed(self, *_):
        self.render()
        self.changed()

    def toggle(self, page):
        if not self.enabled or not self.editable or not self.info or page > self.info.page_count:
            return
        try:
            pages = set(self.selection())
        except PageSelectionError:
            pages = set()
        if page in pages:
            pages.remove(page)
        else:
            pages.add(page)
        self.expression.set(format_pages(pages))

    def set_enabled(self, enabled, editable=True):
        self.enabled, self.editable = enabled, editable
        for control in (self.entry, self.all_button, self.none_button):
            control.configure(state="normal" if enabled and editable and self.info else "disabled")
        self.render()

    def move(self, direction):
        if self.enabled and self.info:
            self.offset = max(0, min(((self.info.page_count - 1) // self.VISIBLE) * self.VISIBLE,
                                     self.offset + direction * self.VISIBLE))
            self.render()

    def render(self):
        if not self.preview_active:
            return
        keys = [(self.info.path, self.info.signature[3], self.info.signature[2], page - 1)
                for page in range(self.offset + 1, min(self.offset + self.VISIBLE, self.info.page_count) + 1)] if self.info else []
        if self.worker.set_required(keys):
            self.pending.clear()
        try:
            selected = set(self.selection()) if self.editable else set(range(1, self.info.page_count + 1)) if self.info else set()
            self.entry.configure(border_color=C["rule"])
        except PageSelectionError:
            selected = set()
            self.entry.configure(border_color=C["error"])
        count = self.info.page_count if self.info else 0
        for index, card in enumerate(self.cards):
            page = self.offset + index + 1
            if page > count:
                card.configure(text="—", image=None, state="disabled", fg_color=C["soft"], border_color=C["rule"])
                continue
            key = (self.info.path, self.info.signature[3], self.info.signature[2], page - 1)
            if key not in self.cache and key not in self.pending and len(self.pending) < self.VISIBLE:
                if self.worker.submit(key):
                    self.pending.add(key)
                elif self.worker.failed:
                    self.cache[key] = None
            payload = self.cache.get(key)
            if payload and key not in self.images:
                width, height, samples = payload
                self.images[key] = ctk.CTkImage(Image.frombytes("RGB", (width, height), samples), size=(width / 3, height / 3))
            label = f"{'✓ ' if page in selected else ''}หน้า {page}"
            if key not in self.cache:
                label += "\nกำลังโหลด…"
            elif payload is None:
                label += "\nไม่มีภาพตัวอย่าง"
            card.configure(text=label, image=self.images.get(key, self.empty_image),
                           state="normal" if self.enabled and self.editable else "disabled",
                           fg_color=C["tint"] if page in selected else C["surface"],
                           border_color=C["accent"] if page in selected else C["rule"])
        self.counter.configure(text=f"หน้า {self.offset + 1}–{min(self.offset + self.VISIBLE, count)} / {count}" if count else "ยังไม่มีเอกสาร")
        self.previous.configure(state="normal" if self.enabled and self.offset else "disabled")
        self.next.configure(state="normal" if self.enabled and self.offset + self.VISIBLE < count else "disabled")

    def process_events(self):
        if not self.preview_active:
            return
        updated = False
        if self.pending and self.worker.failed:
            for key in self.pending:
                self.cache[key] = None
            self.pending.clear()
            updated = True
        try:
            for _ in range(self.VISIBLE):
                key, payload = self.worker.get_nowait()
                self.pending.discard(key)
                if self.info and key[:3] == (self.info.path, self.info.signature[3], self.info.signature[2]):
                    self.cache[key] = payload
                    if len(self.cache) > 32:
                        oldest = next(iter(self.cache))
                        self.cache.pop(oldest)
                        self.images.pop(oldest, None)
                updated = True
        except queue.Empty:
            pass
        if updated or any(key not in self.cache and key not in self.pending for key in self.worker.required):
            self.render()
