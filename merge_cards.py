"""Hallmark · component: document cards · Cobalt · native Windows.

Pre-emit critique: P4 H5 E4 S5 R5 V4. Keyboard focus, hover, pressed,
disabled, preview loading/error and reorder success use the existing tokens.
"""
import math
import queue
import threading
from collections import OrderedDict

import customtkinter as ctk
import pymupdf
from PIL import Image

from ui_theme import COLORS as C, SPACE as S, RADIUS


class MergeCards(ctk.CTkScrollableFrame):
    """Row-major cards; committing a drop is the only mouse order mutation."""
    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent", corner_radius=0,
                         scrollbar_button_color=C["rule"], scrollbar_button_hover_color=C["muted"])
        self.page = page
        self.cards = {}
        self.previews = {}
        self.cache = OrderedDict()
        self.pending = set()
        self.requests = queue.Queue()
        self.results = queue.Queue()
        self.columns = 0
        self.card_width = 0
        self.drag = None
        self.scroll_timer = None
        self.layout_timer = None
        self.preview_timer = None
        self.ghost = None
        self.bind("<Configure>", self._resize, add="+")
        threading.Thread(target=self._preview_worker, daemon=True).start()
        self.preview_timer = self.page.app.root.after(80, self._poll_previews)

    def _resize(self, event):
        if self.layout_timer:
            self.page.app.root.after_cancel(self.layout_timer)
        self.layout_timer = self.page.app.root.after(80, self._layout)

    def _layout(self):
        self.layout_timer = None
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        width = max(160, int(self.winfo_width() / scale))
        columns = max(1, width // 176)
        card_width = max(152, width // columns - S["md"])
        if (columns, card_width) == (self.columns, self.card_width):
            return
        self.cancel_drag()
        for column in range(max(columns, self.columns)):
            self.grid_columnconfigure(column, weight=0, minsize=0, uniform="")
        self.columns, self.card_width = columns, card_width
        for column in range(columns):
            self.grid_columnconfigure(column, weight=1, uniform="documents")
        self._place_cards()

    def _place_cards(self):
        for index, path in enumerate(self.page.files):
            card = self.cards[path]
            card.configure(width=self.card_width, height=180)
            card.grid(row=index // max(1, self.columns), column=index % max(1, self.columns),
                      sticky="ew", padx=S["xs"], pady=(S["xs"], S["sm"]))
            card.number.configure(text=str(index + 1))
            card.name.configure(text=self.page.app.fit_filename(path.name, self.card_width - 28))

    def render(self):
        self.cancel_drag()
        for path in list(self.cards):
            if path not in self.page.files:
                self.cards.pop(path).destroy()
                self.previews.pop(path, None)
        for path in self.page.files:
            if path not in self.cards:
                self._make_card(path)
            card = self.cards[path]
            card.close.configure(state="disabled" if self.page.app.busy else "normal")
            card.configure(fg_color=C["soft"] if self.page.app.busy else C["paper"],
                           border_color=C["rule"], cursor="arrow" if self.page.app.busy else "hand2")
            card._canvas.configure(takefocus=0 if self.page.app.busy else 1)
        self._layout()
        self._place_cards()

    def _make_card(self, path):
        card = ctk.CTkFrame(self, width=176, height=180, corner_radius=RADIUS["control"],
                            fg_color=C["paper"], border_color=C["rule"], border_width=2, cursor="hand2")
        card.grid_propagate(False)
        card.grid_columnconfigure(0, weight=1)
        card.number = self.page.label(card, "", font=self.page.app.font_bold, color="accent", width=24)
        card.number.grid(row=0, column=0, sticky="w", padx=S["md"], pady=(S["xs"], 0))
        card.close = self.page.app.button(card, "×", lambda: self.page.remove_file(path), width=44)
        card.close.grid(row=0, column=1, padx=(0, S["xs"]), pady=(S["xs"], 0))
        preview = self.page.label(card, "กำลังโหลดภาพ…", font=self.page.app.font_small,
                                  color="muted", height=76, anchor="center")
        preview.grid(row=1, column=0, columnspan=2, sticky="ew", padx=S["sm"])
        card.name = self.page.label(card, "", font=self.page.app.font_bold, height=26)
        card.name.grid(row=2, column=0, columnspan=2, sticky="w", padx=S["md"], pady=(S["xs"], 0))
        pages = self.page.label(card, f"{self.page.page_counts[path]} หน้า", font=self.page.app.font_small, color="muted", height=20)
        pages.grid(row=3, column=0, columnspan=2, sticky="w", padx=S["md"], pady=(0, S["sm"]))
        self.cards[path] = card
        self.previews[path] = preview
        for widget in (card, card.number, preview, card.name, pages):
            widget.bind("<ButtonPress-1>", lambda event, p=path: self.press(p, event), add="+")
            widget.bind("<B1-Motion>", self.motion, add="+")
            widget.bind("<ButtonRelease-1>", self.release, add="+")
            widget.bind("<Enter>", lambda event, p=path: self._hover(p, True), add="+")
            widget.bind("<Leave>", lambda event, p=path: self._hover(p, False), add="+")
        card._canvas.bind("<FocusIn>", lambda event: card.configure(border_color=C["focus"]))
        card._canvas.bind("<FocusOut>", lambda event: card.configure(border_color=C["rule"]))
        for key, direction in (("Left", -1), ("Right", 1), ("Up", -1), ("Down", 1)):
            card._canvas.bind(f"<{key}>", lambda event, p=path, d=direction: self._keyboard(p, d))
        card._canvas.bind("<Escape>", lambda event: self.cancel_drag())
        card.bind("<Escape>", lambda event: self.cancel_drag(), add="+")
        try:
            stat = path.stat()
            key = (path, stat.st_mtime_ns, stat.st_size)
        except OSError:
            key = (path, None, None)
        card.preview_key = key
        if key in self.cache:
            self._apply_preview(path, self.cache[key])
        elif key not in self.pending:
            self.pending.add(key)
            self.requests.put(key)

    def _keyboard(self, path, direction):
        self.page.move_file(path, direction)
        if path in self.cards and not self.page.app.busy:
            self.cards[path]._canvas.focus_set()
            self._reveal(path)
        return "break"

    def _reveal(self, path):
        canvas = self._parent_canvas
        card = self.cards[path]
        top = card.winfo_y()
        height = max(1, self.winfo_height())
        visible_top = canvas.canvasy(0)
        if top < visible_top:
            canvas.yview_moveto(top / height)
        elif top + card.winfo_height() > visible_top + canvas.winfo_height():
            canvas.yview_moveto((top + card.winfo_height() - canvas.winfo_height()) / height)

    def _hover(self, path, inside):
        if not self.drag and not self.page.app.busy and path in self.cards:
            card = self.cards[path]
            focused = self.focus_get() is card._canvas
            card.configure(fg_color=C["tint"] if inside else C["paper"],
                           border_color=C["focus"] if focused else C["rule"])
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            name = self.page.app.fit_filename(path.name, max(160, self.page.winfo_width() / scale - 320))
            self.page.order_hint.configure(text=f"ลำดับ {self.page.files.index(path) + 1} · {name}" if inside
                                           else "ลากการ์ดเพื่อเรียง · ซ้ายไปขวา แล้วแถวถัดไป")

    def press(self, path, event):
        if self.page.app.busy or path not in self.cards:
            return
        card = self.cards[path]
        card._canvas.focus_set()
        self.drag = {"path": path, "origin": (event.x_root, event.y_root),
                     "pointer": (event.x_root, event.y_root), "active": False, "slot": None}
        card.configure(fg_color=C["tint"], border_color=C["focus"])
        card.grab_set()

    def motion(self, event):
        if not self.drag or self.page.app.busy:
            return
        self.drag["pointer"] = (event.x_root, event.y_root)
        if math.dist(self.drag["origin"], self.drag["pointer"]) < 6 and not self.drag["active"]:
            return
        self.drag["active"] = True
        if self.ghost is None:
            self.ghost = ctk.CTkLabel(self.page, text=self.page.app.fit_filename(self.drag["path"].name, 180),
                                     width=204, height=44, fg_color=C["accent"], text_color=C["accent-ink"],
                                     corner_radius=RADIUS["control"], font=self.page.app.font_small)
            self.cards[self.drag["path"]].configure(cursor="fleur")
        self._target()
        if self.scroll_timer is None:
            self.scroll_timer = self.page.app.root.after(60, self._auto_scroll)

    def _target(self):
        x, y = self.drag["pointer"]
        if self.ghost:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
            gx = min(max(0, (x - self.page.winfo_rootx()) / scale + 16), self.page.winfo_width() / scale - 204)
            gy = min(max(0, (y - self.page.winfo_rooty()) / scale + 16), self.page.winfo_height() / scale - 44)
            self.ghost.place(x=gx, y=gy)
            self.ghost.lift()
        canvas = self._parent_canvas
        left, top = canvas.winfo_rootx(), canvas.winfo_rooty()
        if not (left <= x <= left + canvas.winfo_width() and top <= y <= top + canvas.winfo_height()):
            self.drag["slot"] = None
            self.page.order_hint.configure(text="ลากกลับเข้ารายการเพื่อวาง · Esc ยกเลิก")
        else:
            nearest = min(self.page.files, key=lambda p: self._distance(self.cards[p], x, y))
            card = self.cards[nearest]
            slot = self.page.files.index(nearest)
            if x > card.winfo_rootx() + card.winfo_width() / 2:
                slot += 1
            source = self.page.files.index(self.drag["path"])
            self.drag["slot"] = slot - (slot > source)
            self.page.order_hint.configure(text=f"วางที่ลำดับ {self.drag['slot'] + 1} · Esc ยกเลิก")
        for index, path in enumerate(self.page.files):
            card = self.cards[path]
            target = self.drag["slot"] == index
            card.configure(border_color=C["focus"] if target else C["rule"],
                           fg_color=C["tint"] if target or path == self.drag["path"] else C["paper"])

    @staticmethod
    def _distance(card, x, y):
        # Distance to card rectangle; vertical separation dominates across rows.
        dx = max(card.winfo_rootx() - x, 0, x - card.winfo_rootx() - card.winfo_width())
        dy = max(card.winfo_rooty() - y, 0, y - card.winfo_rooty() - card.winfo_height())
        return dx * dx + dy * dy * 4

    def _auto_scroll(self):
        self.scroll_timer = None
        if not self.drag or not self.drag["active"] or self.page.app.busy:
            return
        canvas = self._parent_canvas
        x, y = self.drag["pointer"]
        top = canvas.winfo_rooty()
        if canvas.winfo_rootx() <= x <= canvas.winfo_rootx() + canvas.winfo_width():
            direction = -1 if y < top + 36 else (1 if y > top + canvas.winfo_height() - 36 else 0)
            if direction:
                canvas.yview_scroll(direction * 20, "units")
                self._target()
        self.scroll_timer = self.page.app.root.after(60, self._auto_scroll)

    def release(self, event):
        if not self.drag:
            return
        if self.drag["active"]:
            self.drag["pointer"] = (event.x_root, event.y_root)
            self._target()
        path, slot, active = self.drag["path"], self.drag["slot"], self.drag["active"]
        self.cancel_drag()
        if active and slot is not None and not self.page.app.busy:
            self.page.reorder_file(path, slot)
            self.page.status.set(f"จัดลำดับแล้ว · {path.name} อยู่ลำดับ {slot + 1}")
            self.cards[path]._canvas.focus_set()

    def cancel_drag(self):
        if self.scroll_timer:
            self.page.app.root.after_cancel(self.scroll_timer)
            self.scroll_timer = None
        if self.ghost:
            self.ghost.destroy()
            self.ghost = None
        if self.drag:
            card = self.cards.get(self.drag["path"])
            if card:
                card.grab_release()
            self.drag = None
            for card in self.cards.values():
                card.configure(border_color=C["rule"], fg_color=C["soft"] if self.page.app.busy else C["paper"],
                               cursor="arrow" if self.page.app.busy else "hand2")
        self.page.order_hint.configure(text="ลากการ์ดเพื่อเรียง · ซ้ายไปขวา แล้วแถวถัดไป")

    def _preview_worker(self):
        while True:
            key = self.requests.get()
            if key is None:
                break
            try:
                with pymupdf.open(key[0]) as document:
                    page = document[0]
                    factor = min(224 / page.rect.width, 144 / page.rect.height)
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False, colorspace=pymupdf.csRGB)
                    preview = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                self.results.put((key, preview))
            except Exception:
                self.results.put((key, None))

    def _apply_preview(self, path, preview):
        label = self.previews[path]
        if preview is None:
            label.configure(text="ไม่มีภาพตัวอย่าง", image=None)
        else:
            image = ctk.CTkImage(light_image=preview, dark_image=preview,
                                 size=(max(1, preview.width // 2), max(1, preview.height // 2)))
            label.configure(text="", image=image)

    def _poll_previews(self):
        try:
            for _ in range(12):
                key, preview = self.results.get_nowait()
                self.pending.discard(key)
                self.cache[key] = preview
                while len(self.cache) > 128:
                    self.cache.popitem(last=False)
                path = key[0]
                if path in self.cards and self.cards[path].preview_key == key:
                    self._apply_preview(path, preview)
        except queue.Empty:
            pass
        self.preview_timer = self.page.app.root.after(80, self._poll_previews)

    def destroy(self):
        self.requests.put(None)
        for timer in (self.layout_timer, self.scroll_timer, self.preview_timer):
            if timer:
                self.page.app.root.after_cancel(timer)
        super().destroy()
