"""Hallmark · component: page selector · modern-minimal · existing Cobalt tokens.

Native states: default / hover / keyboard focus / pressed / disabled / loading /
error / selected. No spatial animation. Pre-emit critique: P4 H5 E4 S5 R5 V4.
Vertical viewport grid; bounded visible cards use the shared spawned preview process.
"""
import math
import queue
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from pdf_lover.core.page_selection import selected_pages, format_pages, PageSelectionError
from pdf_lover.ui.pdf_previews import PreviewWorker, PreviewCache
from pdf_lover.ui.page_gestures import card_box, intersects, marquee_pages
from pdf_lover.ui.theme import COLORS as C, SPACE as S, RADIUS


class PageSelector(ctk.CTkFrame):
    """Reusable selection, polled by the shell. No feature imports or timer chain."""
    VISIBLE = 24
    MIN_WIDTH = 180
    ROW_HEIGHT = 240

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
        self.columns, self.step_y, self.scaling = 1, self.ROW_HEIGHT, 1
        self.visible = {}
        self.focused, self.hovered, self.pressed = 1, None, None
        self.anchor = 1
        self.gesture = self.edge_timer = None
        self.draw_timer = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        app.label(self, title, font=app.font_bold).grid(row=0, column=0, sticky="w", padx=S["md"], pady=S["xs"])
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=1, padx=S["md"])
        self.all_button = app.button(actions, "ทุกหน้า", self.select_all, width=88)
        self.all_button.pack(side="left", padx=S["xs"])
        self.none_button = app.button(actions, "ล้าง", lambda: self.expression.set(""), width=60)
        self.none_button.pack(side="left")
        self.entry = ctk.CTkEntry(self, textvariable=self.expression, height=44, font=app.font_body,
                                fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"], border_width=2)
        self.entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=S["lg"])
        app._entry_focus(self.entry)
        self.hint_label = app.label(self, hint, font=app.font_small, color="muted")
        self.hint_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=S["lg"], pady=S["xs"])
        viewport = ctk.CTkFrame(self, fg_color="transparent")
        viewport.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=S["lg"])
        viewport.grid_columnconfigure(0, weight=1)
        viewport.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(viewport, background=C["surface"], height=100,
                                highlightthickness=0, borderwidth=0, takefocus=True)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(viewport, orientation="vertical", command=self._scroll)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.counter = app.label(self, "ยังไม่มีเอกสาร", font=app.font_small, color="muted", anchor="w")
        self.counter.grid(row=4, column=0, columnspan=2, sticky="ew", padx=S["lg"], pady=S["sm"])
        self.gesture_hint = app.label(self, "Shift+คลิก: เลือกช่วง · Ctrl+คลิก: เพิ่ม/ลด\nลากครอบ: เลือกหลายหน้า · Esc: ยกเลิกการลาก",
                                      font=app.font_small, color="muted", anchor="w", justify="left")
        self.gesture_hint.grid(row=5, column=0, columnspan=2, sticky="ew", padx=S["lg"], pady=(0, S["sm"]))
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<FocusIn>", lambda _: self.render())
        self.canvas.bind("<FocusOut>", self._focus_out)
        for key in ("Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next", "space", "Return", "Escape", "a"):
            self.canvas.bind(f"<{key}>", self._keyboard)
        self.expression.trace_add("write", self._changed)
        self.render()

    def destroy(self):
        self.preview_active = False
        self._cancel_gesture()
        self._cancel_draw()
        self.worker.close()
        super().destroy()

    def set_document(self, info):
        self._cancel_gesture()
        self.info, self.offset = info, 0
        self.anchor = 1
        self.focused, self.hovered, self.pressed = 1, None, None
        self.canvas.delete("all")
        self.cache.clear()
        self.images.clear()
        self.canvas.yview_moveto(0)
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
            self._cancel_gesture()
            self._cancel_draw()
            self.canvas.delete("all")
            self.visible.clear()
            self.hovered = self.pressed = None
            self.cache.clear()
            self.images.clear()

    def _changed(self, *_):
        self._cancel_gesture()
        self.render()
        self.changed()

    def toggle(self, page):
        if not self.enabled or not self.editable or not self.info or not 1 <= page <= self.info.page_count:
            return
        try:
            pages = set(self.selection())
        except PageSelectionError:
            pages = set()
        if page in pages:
            pages.remove(page)
        else:
            pages.add(page)
        self.anchor = page
        self.expression.set(format_pages(pages))

    def set_enabled(self, enabled, editable=True):
        if not enabled or not editable:
            self._cancel_gesture()
        self.enabled, self.editable = enabled, editable
        for control in (self.entry, self.all_button, self.none_button):
            control.configure(state="normal" if enabled and editable and self.info else "disabled")
        self.render()

    def move(self, direction):
        if self.enabled and self.info:
            self.canvas.yview_scroll(direction, "pages")
            self.render()

    def _cancel_draw(self):
        if self.draw_timer is not None:
            self.app.root.after_cancel(self.draw_timer)
            self.draw_timer = None

    def _schedule(self):
        if self.preview_active and self.draw_timer is None:
            self.draw_timer = self.app.root.after(16, self._draw_grid)

    def _draw_grid(self):
        self.draw_timer = None
        self.render()

    def _resize(self, _=None):
        self._cancel_gesture()
        scale = self._get_widget_scaling()
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        columns = max(1, min(4, int(width / (self.MIN_WIDTH * scale))))
        # At most six intersecting rows even on tall displays; never build all pages.
        step_y = max(min(self.ROW_HEIGHT * scale, max(160 * scale, height)), math.ceil(height / 5))
        old_page = self.offset
        changed = columns != self.columns or step_y != self.step_y
        if scale != self.scaling or changed or width != getattr(self, "image_width", None):
            self.canvas.delete("all")
            self.images.clear()
        self.columns, self.step_y, self.scaling = columns, step_y, scale
        self.image_width = width
        count = self.info.page_count if self.info else 0
        total = max(height, math.ceil(count / columns) * step_y)
        self.canvas.configure(scrollregion=(0, 0, width, total), yscrollincrement=max(1, int(32 * scale)))
        if changed:
            self.canvas.yview_moveto((old_page // columns * step_y) / max(1, total))
        self._schedule()

    def _scroll(self, *args):
        if self.enabled:
            self.canvas.yview(*args)
            self._schedule()

    def _wheel(self, event):
        if self.enabled and self.info:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            self._schedule()
        return "break"

    def _hit(self, event):
        for page, (x1, y1, x2, y2) in self.visible.items():
            if x1 <= event.x <= x2 and y1 <= self.canvas.canvasy(event.y) <= y2:
                return page
        return None

    def _press(self, event):
        if self.enabled and self.info:
            self._cancel_gesture()
            self.canvas.focus_set()
            self.pressed = self._hit(event)
            if self.pressed is not None:
                self.focused = self.pressed
            if self.editable:
                try:
                    base = set(self.selection())
                except PageSelectionError:
                    base = set()
                self.gesture = {"origin": (event.x, self.canvas.canvasy(event.y)),
                                "pointer": (event.x, event.y), "start": (event.x, event.y),
                                "base": base, "state": event.state, "active": False}
                self.canvas.grab_set()
            self.render()

    def _release(self, event):
        gesture, page = self.gesture, self.pressed
        if gesture and gesture["active"]:
            gesture["pointer"] = (event.x, event.y)
            picked = set(marquee_pages(self._rectangle(), self.info.page_count, self.columns,
                                      self.canvas.winfo_width() / self.columns, self.step_y, S["sm"] * self.scaling))
            pages = (gesture["base"] ^ picked if gesture["state"] & 4 else
                     gesture["base"] | picked if gesture["state"] & 1 else picked)
            self._cancel_gesture()
            self.expression.set(format_pages(pages))
        elif gesture:
            state = gesture["state"]
            self._cancel_gesture()
            if page is not None and page == self._hit(event):
                if state & 1:
                    self._select_range(page, bool(state & 4))
                else:
                    self.toggle(page)
            elif page is None and self._hit(event) is None:
                if not state & 5:
                    self.expression.set("")
        else:
            self.pressed = None
        self.render()

    def _select_range(self, page, additive=False):
        if not self.enabled or not self.editable or not self.info:
            return
        pages = set(range(min(self.anchor, page), max(self.anchor, page) + 1))
        if additive:
            try:
                pages.update(self.selection())
            except PageSelectionError:
                pass
        self.expression.set(format_pages(pages))

    def _rectangle(self):
        x, y = self.gesture["pointer"]
        x = min(self.canvas.winfo_width(), max(0, x))
        y = self.canvas.canvasy(min(self.canvas.winfo_height(), max(0, y)))
        ox, oy = self.gesture["origin"]
        return min(ox, x), min(oy, y), max(ox, x), max(oy, y)

    def _motion(self, event):
        if not self.gesture:
            return
        self.gesture["pointer"] = (event.x, event.y)
        if not self.gesture["active"]:
            if math.dist(self.gesture["start"], self.gesture["pointer"]) < 6 * self.scaling:
                return
            self.gesture["active"] = True
            self.pressed = self.hovered = None
            self.canvas.configure(cursor="crosshair")
        self._schedule()
        self._schedule_edge()

    def _edge_direction(self):
        if not self.gesture or not self.gesture["active"]:
            return 0
        y = self.gesture["pointer"][1]
        edge = min(24 * self.scaling, self.canvas.winfo_height() / 4)
        return -1 if y < edge else 1 if y > self.canvas.winfo_height() - edge else 0

    def _schedule_edge(self):
        if self._edge_direction() and self.edge_timer is None:
            self.edge_timer = self.app.root.after(60, self._edge_tick)

    def _edge_tick(self):
        self.edge_timer = None
        direction = self._edge_direction()
        if not direction:
            return
        before = self.canvas.yview()
        self.canvas.yview_scroll(direction, "units")
        if self.canvas.yview() != before:
            self._schedule()
            self._schedule_edge()

    def _cancel_gesture(self):
        if self.edge_timer is not None:
            self.app.root.after_cancel(self.edge_timer)
            self.edge_timer = None
        self.gesture = self.pressed = None
        if self.canvas.grab_current() == self.canvas:
            self.canvas.grab_release()
        self.canvas.configure(cursor="")

    def _hover(self, event):
        if self.gesture:
            return
        hovered = self._hit(event) if self.enabled and self.editable else None
        if hovered != self.hovered:
            self.hovered = hovered
            self.canvas.configure(cursor="hand2" if hovered else "")
            self._schedule()

    def _leave(self, _):
        self.hovered = None
        if not self.gesture:
            self.canvas.configure(cursor="")
        self._schedule()

    def _focus_out(self, _):
        self._cancel_gesture()
        self.render()

    def _keyboard(self, event):
        if event.keysym == "Escape":
            self._cancel_gesture()
            self.render()
            return "break"
        if event.state & 4 and event.keysym.lower() == "a":
            self.select_all()
            return "break"
        # Let the shell handle Ctrl+Enter rather than treating it as page selection.
        if event.state & 4 and event.keysym == "Return":
            self._cancel_gesture()
            return None
        if not self.enabled or not self.info:
            return "break"
        key, count = event.keysym, self.info.page_count
        if key in ("space", "Return"):
            if event.state & 1:
                self._select_range(self.focused, bool(event.state & 4))
            else:
                self.toggle(self.focused)
            return "break"
        steps = {"Left": -1, "Right": 1, "Up": -self.columns, "Down": self.columns,
                 "Prior": -max(self.columns, int(self.canvas.winfo_height() / self.step_y) * self.columns),
                 "Next": max(self.columns, int(self.canvas.winfo_height() / self.step_y) * self.columns)}
        self.focused = 1 if key == "Home" else count if key == "End" else max(1, min(count, self.focused + steps.get(key, 0)))
        if event.state & 1:
            self._select_range(self.focused, bool(event.state & 4))
        elif not event.state & 4:
            self.anchor = self.focused
        top = ((self.focused - 1) // self.columns) * self.step_y
        current, height = self.canvas.canvasy(0), self.canvas.winfo_height()
        total = max(height, math.ceil(count / self.columns) * self.step_y)
        if top < current:
            self.canvas.yview_moveto(top / total)
        elif top + self.step_y > current + height:
            self.canvas.yview_moveto(max(0, top + self.step_y - height) / total)
        self.render()
        return "break"

    def _key(self, page):
        return (self.info.path, self.info.signature[3], self.info.signature[2], page - 1, 0, 180, 200)

    def render(self):
        if not self.preview_active:
            return
        count = self.info.page_count if self.info else 0
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        total = max(height, math.ceil(count / self.columns) * self.step_y)
        self.canvas.configure(scrollregion=(0, 0, width, total))
        top = max(0, self.canvas.canvasy(0))
        self.offset = int(top // self.step_y) * self.columns
        end = min(count, math.ceil((top + height) / self.step_y) * self.columns)
        pages = list(range(self.offset + 1, end + 1))[:self.VISIBLE]
        keys = [self._key(page) for page in pages]
        if self.worker.set_required(keys):
            self.pending.clear()
        try:
            selected = set(self.selection()) if self.editable else set(range(1, self.info.page_count + 1)) if self.info else set()
            self.entry.configure(border_color=C["rule"])
        except PageSelectionError:
            selected = set()
            self.entry.configure(border_color=C["error"])
        self.canvas.delete("all")
        self.visible.clear()
        scale, gap = self.scaling, S["sm"] * self.scaling
        cell_width = width / self.columns
        font = self._apply_font_scaling(self.app.font_small)
        for page, key in zip(pages, keys):
            chosen = page in selected
            if self.gesture and self.gesture["active"]:
                hit = intersects(card_box(page, self.columns, cell_width, self.step_y, gap), self._rectangle())
                base = page in self.gesture["base"]
                chosen = base != hit if self.gesture["state"] & 4 else base or hit if self.gesture["state"] & 1 else hit
            if key not in self.cache and key not in self.pending and len(self.pending) < self.VISIBLE:
                if self.worker.submit(key):
                    self.pending.add(key)
                elif self.worker.failed:
                    self.cache[key] = None
            payload = self.cache.get(key)
            if payload and key not in self.images:
                pixel_width, pixel_height, samples = payload
                image = Image.frombytes("RGB", (pixel_width, pixel_height), samples)
                factor = min((cell_width - 24 * scale) / pixel_width, (self.step_y - 48 * scale) / pixel_height)
                self.images[key] = ImageTk.PhotoImage(image.resize((max(1, int(pixel_width * factor)), max(1, int(pixel_height * factor)))), master=self.canvas)
            label = f"{'✓ ' if chosen else ''}หน้า {page}"
            if key not in self.cache:
                label += "\nกำลังโหลด…"
            elif payload is None:
                label += "\nไม่มีภาพตัวอย่าง"
            row, column = divmod(page - 1, self.columns)
            x1, y1 = column * cell_width + gap / 2, row * self.step_y + gap / 2
            x2, y2 = (column + 1) * cell_width - gap / 2, (row + 1) * self.step_y - gap / 2
            self.visible[page] = (x1, y1, x2, y2)
            fill = C["soft"] if not self.enabled else C["tint"] if chosen else C["surface"]
            if self.enabled and self.editable and page in (self.hovered, self.pressed):
                fill = C["tint"] if page != self.pressed else C["soft"]
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill,
                                         outline=C["accent"] if chosen else C["rule"], width=2 * scale)
            if page == self.focused and self.canvas.focus_get() == self.canvas:
                self.canvas.create_rectangle(x1 + 3 * scale, y1 + 3 * scale, x2 - 3 * scale, y2 - 3 * scale,
                                             outline=C["focus"], width=2 * scale)
            if key in self.images:
                self.canvas.create_image((x1 + x2) / 2, y1 + (self.step_y - 40 * scale) / 2, image=self.images[key])
            self.canvas.create_text((x1 + x2) / 2, y2 - 22 * scale, text=label, font=font,
                                    fill=C["ink"] if self.enabled else C["muted"], justify="center")
        if not count:
            self.canvas.create_text(gap, gap, text="เลือก PDF เพื่อดูหน้าเอกสาร", anchor="nw", font=font, fill=C["muted"])
        if self.gesture and self.gesture["active"]:
            self.canvas.create_rectangle(*self._rectangle(), outline=C["accent"], width=2 * scale,
                                         dash=(4, 3), tags="marquee")
        caption = f"หน้า {pages[0]}–{pages[-1]} / {count}" if pages else "ยังไม่มีเอกสาร"
        if count and total > height:
            caption += " · เลื่อนลงเพื่อดูหน้าถัดไป"
        if self.gesture and self.gesture["active"]:
            caption = "ปล่อยเมาส์เพื่อยืนยันหน้าที่เลือก · Esc ยกเลิก"
        self.counter.configure(text=caption)

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
