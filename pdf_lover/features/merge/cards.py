"""Native, virtualized PDF cards on one Canvas.

Hallmark component: Cobalt document workspace. One native drawing surface keeps
pointer motion and scrolling independent of queue length.
"""
import ctypes
import math
import queue
import sys
import time
import tkinter as tk
from collections import OrderedDict
from pathlib import Path
from tkinter import font as tkfont

import customtkinter as ctk
from PIL import Image, ImageTk

from pdf_lover.features.merge.previews import PreviewWorker
from pdf_lover.ui.pdf_previews import PreviewCache
from pdf_lover.ui.theme import COLORS as C, FONTS, SPACE as S


class MergeCards(ctk.CTkFrame):
    GAP = 12
    HEIGHT = 240
    MIN_WIDTH = 220
    MAX_PREVIEWS = 48
    HINT = "ลากการ์ดเพื่อเรียง · ซ้ายไปขวา แล้วแถวถัดไป"
    LIFT_SECONDS = 0.12
    MARKER_SECONDS = 0.14

    def __init__(self, parent, page):
        super().__init__(parent, fg_color="transparent", corner_radius=0)
        self.page = page
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=C["document-desk"], highlightthickness=0, bd=0,
                                takefocus=1, cursor="arrow", xscrollincrement=1, yscrollincrement=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self._scroll,
                                           fg_color=C["surface"], button_color=C["rule"],
                                           button_hover_color=C["muted"], width=14)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.photos = OrderedDict()
        self.cache = PreviewCache(self.MAX_PREVIEWS, 16 * 1048576, lambda key: self.photos.pop(key, None))
        self.pending = set()
        self.preview_keys = {}
        self.worker = PreviewWorker(page.app.preview_coordinator)
        self.preview_active = False
        self.worker.set_active(False)
        self.visible = {}
        self.columns = 1
        self.card_width = self.MIN_WIDTH
        self.step_x = self.MIN_WIDTH + self.GAP
        self.step_y = self.HEIGHT + self.GAP
        self.scaling = 1
        self.selected = None
        self.hovered = None
        self.drag = None
        self.ghost = None
        self.marker = None
        self.motion_enabled = self._system_motion_enabled()
        self.frame_timer = None
        self.draw_timer = None
        self.scroll_timer = None
        self.preview_timer = None
        self.mouse_down = False
        self.paints = 0
        self.scrollregion = None
        self.font_bold = tkfont.Font(family=FONTS["body"], size=14, weight="bold")
        self.font_small = tkfont.Font(family=FONTS["body"], size=12)
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.motion)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Motion>", self._motion_idle)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _: self._wheel_steps(-1))
        self.canvas.bind("<Button-5>", lambda _: self._wheel_steps(1))
        self.canvas.bind("<Escape>", lambda _: self.cancel_drag())
        self.canvas.bind("<FocusIn>", lambda _: self._style(self.selected))
        self.canvas.bind("<FocusOut>", self._focus_out)
        for key, step in (("Left", -1), ("Right", 1), ("Up", -self.columns), ("Down", self.columns)):
            self.canvas.bind(f"<{key}>", lambda event, name=key: self._keyboard(name))
        self.canvas.bind("<Delete>", self._delete_selected)

    @staticmethod
    def _system_motion_enabled():
        """Follow Windows' client-area animation accessibility preference."""
        if sys.platform != "win32":
            return True
        enabled = ctypes.c_int(1)
        try:
            return bool(ctypes.windll.user32.SystemParametersInfoW(
                0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)
        except (AttributeError, OSError):
            return True

    def _resize(self, event):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        gap = round(self.GAP * scale)
        columns = max(1, (event.width - gap) // round((self.MIN_WIDTH + self.GAP) * scale))
        width = max(round(152 * scale), (event.width - gap * (columns + 1)) // columns)
        if (columns, width, scale) != (self.columns, self.card_width, self.scaling):
            self.cancel_drag()
            self.columns, self.card_width, self.scaling = columns, width, scale
            self.step_x = width + gap
            self.step_y = round((self.HEIGHT + self.GAP) * scale)
            self.font_bold = tkfont.Font(family=FONTS["body"], size=round(14 * scale), weight="bold")
            self.font_small = tkfont.Font(family=FONTS["body"], size=round(12 * scale))
            self._update_scrollregion()
        self._schedule_draw()

    def _update_scrollregion(self):
        rows = math.ceil(len(self.page.files) / max(1, self.columns))
        extent = max(self.canvas.winfo_height(), rows * self.step_y + round(self.GAP * self.scaling))
        region = (0, 0, self.canvas.winfo_width(), extent)
        if region != self.scrollregion:
            self.scrollregion = region
            self.canvas.configure(scrollregion=region)

    def render(self):
        self.cancel_drag()
        files = set(self.page.files)
        self.preview_keys = {path: key for path, key in self.preview_keys.items() if path in files}
        if self.selected not in files:
            self.selected = self.page.files[0] if self.page.files else None
        if self.hovered not in files:
            self.hovered = None
        self._update_scrollregion()
        self._schedule_draw()

    def _schedule_draw(self):
        if self.preview_active and self.draw_timer is None:
            self.draw_timer = self.page.app.root.after(12, self._draw_visible)

    def _on_scroll(self, start, end):
        self.scrollbar.set(start, end)
        self._schedule_draw()

    def _scroll(self, *args):
        self.canvas.yview(*args)
        self._schedule_draw()

    def _wheel(self, event):
        if event.delta:
            self._wheel_steps(-int(event.delta / 120))
        return "break"

    def _wheel_steps(self, steps):
        self.canvas.yview_scroll(steps * round(56 * self.scaling), "units")
        self._schedule_draw()
        return "break"

    def _bounds(self, index):
        row, column = divmod(index, self.columns)
        gap = round(self.GAP * self.scaling)
        x = gap + column * self.step_x
        y = gap + row * self.step_y
        return x, y, x + self.card_width, y + round(self.HEIGHT * self.scaling)

    def card_bounds(self, path):
        index = self.page.files.index(path)
        x1, y1, x2, y2 = self._bounds(index)
        offset = self.canvas.canvasy(0)
        return (self.canvas.winfo_rootx() + x1, self.canvas.winfo_rooty() + y1 - offset,
                self.canvas.winfo_rootx() + x2, self.canvas.winfo_rooty() + y2 - offset)

    def card_center(self, path, after=False):
        x1, y1, x2, y2 = self.card_bounds(path)
        return x1 + (x2 - x1) * (0.8 if after else 0.2), y1 + round(70 * self.scaling)

    def _draw_visible(self):
        self.draw_timer = None
        if not self.winfo_exists() or not self.preview_active:
            return
        self._update_scrollregion()
        top = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        first_row = max(0, int(top // self.step_y) - 1)
        last_row = min(math.ceil(len(self.page.files) / self.columns), int(bottom // self.step_y) + 2)
        self.canvas.delete("card")
        self.visible.clear()
        indexes = range(first_row * self.columns, min(last_row * self.columns, len(self.page.files)))
        keys = [self._preview_key(self.page.files[index], submit=False) for index in indexes]
        if self.worker.set_required(keys):
            self.pending.clear()
        for index in indexes:
            self._draw_card(index)
        self._raise_ghost()

    def _draw_card(self, index):
        path = self.page.files[index]
        x1, y1, x2, y2 = self._bounds(index)
        scale = self.scaling
        fill, outline = self._colors(index)
        rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline,
                                             width=max(1, round(2 * scale)), tags="card")
        self.canvas.create_text(x1 + round(12 * scale), y1 + round(22 * scale), text=str(index + 1),
                                anchor="w", fill=C["accent"], font=self.font_bold, tags="card")
        close_size = round(44 * scale)
        cx, cy = x2 - close_size - round(4 * scale), y1 + round(4 * scale)
        self.canvas.create_rectangle(cx, cy, cx + close_size, cy + close_size,
                                     fill=C["surface"], outline=C["rule"], tags="card")
        self.canvas.create_text(cx + close_size / 2, cy + close_size / 2, text="×",
                                fill=C["muted"] if self.page.app.busy else C["ink"],
                                font=self.font_bold, tags="card")
        key = self._preview_key(path)
        image = self._photo(key) if key in self.cache else None
        if image is not None:
            self.canvas.create_image((x1 + x2) / 2, y1 + round(112 * scale), image=image, tags="card")
        else:
            self.canvas.create_text((x1 + x2) / 2, y1 + round(112 * scale),
                                    text="กำลังโหลดภาพ…" if key in self.pending else "ไม่มีภาพตัวอย่าง",
                                    fill=C["muted"], font=self.font_small, tags="card")
        width = self.card_width - round(28 * scale)
        name = self._fit_name(path.name, width)
        self.canvas.create_text(x1 + round(12 * scale), y1 + round(192 * scale), text=name,
                                anchor="w", fill=C["ink"], font=self.font_bold, tags="card")
        self.canvas.create_text(x1 + round(12 * scale), y1 + round(218 * scale),
                                text=f"{self.page.page_counts[path]} หน้า", anchor="w", fill=C["muted"],
                                font=self.font_small, tags="card")
        self.visible[index] = rect

    def _fit_name(self, name, width):
        if self.font_bold.measure(name) <= width:
            return name
        stem, suffix = Path(name).stem, Path(name).suffix
        while stem and self.font_bold.measure(stem + "…" + suffix) > width:
            stem = stem[:-1]
        return stem + "…" + suffix if stem else name[:4] + "…"

    def _preview_key(self, path, submit=True):
        if path not in self.preview_keys:
            try:
                stat = path.stat()
                key = (path, stat.st_mtime_ns, stat.st_size)
            except OSError:
                key = (path, None, None)
            self.preview_keys[path] = key
        key = self.preview_keys[path]
        # An old thumbnail may have been evicted while the user scrolled away.
        if submit and key not in self.cache and key not in self.pending:
            if self.worker.submit(key):
                self.pending.add(key)
            elif self.worker.failed:
                self.cache[key] = None
        return key

    def _photo(self, key):
        if key not in self.photos:
            preview = self.cache[key]
            if preview is None:
                return None
            scaled = preview.copy()
            scaled.thumbnail((self.card_width - round(32 * self.scaling), round(132 * self.scaling)),
                             Image.Resampling.LANCZOS)
            self.photos[key] = ImageTk.PhotoImage(scaled, master=self.canvas)
            while len(self.photos) > self.MAX_PREVIEWS:
                self.photos.popitem(last=False)
        return self.photos[key]

    def _colors(self, index):
        path = self.page.files[index]
        focused = self.canvas.focus_get() is self.canvas and self.selected == path
        highlighted = self.drag and self.drag["slot"] == index
        active = self.drag and self.drag["path"] == path
        if self.page.app.busy:
            return C["soft"], C["rule"]
        return (C["tint"] if highlighted or active or self.hovered == path else C["paper"],
                C["focus"] if highlighted or focused else C["rule"])

    def _style(self, path):
        if path in self.page.files:
            index = self.page.files.index(path)
            if index in self.visible:
                fill, outline = self._colors(index)
                self.canvas.itemconfigure(self.visible[index], fill=fill, outline=outline)
                self.paints += 1

    def _hit_index(self, x, y):
        count = len(self.page.files)
        if not count:
            return None
        cx, cy = self.canvas.canvasx(x), self.canvas.canvasy(y)
        gap = round(self.GAP * self.scaling)
        row = max(0, int((cy - gap) // self.step_y))
        col = max(0, int((cx - gap) // self.step_x))
        index = row * self.columns + col
        if index >= count:
            return None
        x1, y1, x2, y2 = self._bounds(index)
        return index if x1 <= cx <= x2 and y1 <= cy <= y2 else None

    def _motion_idle(self, event):
        if self.drag or self.page.app.busy:
            return
        index = self._hit_index(event.x, event.y)
        path = self.page.files[index] if index is not None else None
        if path == self.hovered:
            return
        previous = self.hovered
        self.hovered = path
        self._style(previous)
        self._style(path)
        self.canvas.configure(cursor="hand2" if path else "arrow")
        text = (f"ลำดับ {index + 1} · {self.page.app.fit_filename(path.name, max(160, self.winfo_width() - 320))}"
                if path else self.HINT)
        self.page.order_hint.configure(text=text)

    def _leave(self, event):
        if self.drag:
            return
        previous = self.hovered
        self.hovered = None
        self._style(previous)
        self.page.order_hint.configure(text=self.HINT)

    def press(self, event):
        if self.page.app.busy:
            return
        index = self._hit_index(event.x, event.y)
        if index is None:
            return
        path = self.page.files[index]
        x1, y1, x2, y2 = self._bounds(index)
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        close_size = round(40 * self.scaling)
        if x2 - close_size - round(4 * self.scaling) <= cx <= x2 - round(4 * self.scaling) and cy <= y1 + round(44 * self.scaling):
            self.page.remove_file(path)
            return
        self.cancel_drag()
        self.canvas.focus_set()
        self.selected = path
        self.mouse_down = True
        self.drag = {"path": path, "source": index, "origin": (event.x_root, event.y_root),
                     "pointer": (event.x_root, event.y_root), "active": False, "slot": None,
                     "shown_slot": None, "lift_started": None, "marker_started": None}
        self.canvas.grab_set()
        self._style(path)

    def motion(self, event):
        if not self.drag or self.page.app.busy:
            return
        self.drag["pointer"] = (event.x_root, event.y_root)
        if not self.drag["active"] and math.dist(self.drag["origin"], self.drag["pointer"]) < 6:
            return
        if not self.drag["active"]:
            self.drag["active"] = True
            self.drag["lift_started"] = time.perf_counter()
            self.canvas.configure(cursor="fleur")
        if self.frame_timer is None:
            self.frame_timer = self.page.app.root.after(16, self._drag_frame)

    def _drag_frame(self):
        self.frame_timer = None
        if not self.drag or not self.drag["active"]:
            return
        self._target()
        if self.scroll_timer is None:
            self.scroll_timer = self.page.app.root.after(55, self._auto_scroll)
        if self.motion_enabled and (time.perf_counter() - self.drag["lift_started"] < self.LIFT_SECONDS or
                                    self.drag["marker_started"] is not None and
                                    time.perf_counter() - self.drag["marker_started"] < self.MARKER_SECONDS):
            self.frame_timer = self.page.app.root.after(16, self._drag_frame)

    def _target(self):
        x, y = self.drag["pointer"]
        left, top = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self.ghost is None:
            shadow = self.canvas.create_rectangle(0, 0, 0, 0, fill=C["rule"], outline="", tags="ghost")
            box = self.canvas.create_rectangle(0, 0, 0, 0, fill=C["accent"], outline=C["accent-hover"],
                                               width=max(1, round(self.scaling)), tags="ghost")
            symbol = self.canvas.create_text(0, 0, text="▤", fill=C["accent-ink"],
                                             font=self.font_bold, tags="ghost")
            label = self.canvas.create_text(0, 0, text=self._fit_name(self.drag["path"].name, round(180 * self.scaling)),
                                            fill=C["accent-ink"], anchor="w", font=self.font_small, tags="ghost")
            self.ghost = (shadow, box, symbol, label)
        progress = 1.0
        if self.motion_enabled:
            progress = min(1.0, (time.perf_counter() - self.drag["lift_started"]) / self.LIFT_SECONDS)
            progress = 1 - (1 - progress) ** 3
        ghost_width = round((194 + 10 * progress) * self.scaling)
        ghost_height = round((36 + 6 * progress) * self.scaling)
        gx = min(max(self.canvas.canvasx(x - left + 16), self.canvas.canvasx(0)),
                 self.canvas.canvasx(max(0, width - ghost_width - round(4 * self.scaling))))
        gy = min(max(self.canvas.canvasy(y - top + 16), self.canvas.canvasy(0)),
                 self.canvas.canvasy(max(0, height - ghost_height - round(4 * self.scaling))))
        shadow, box, symbol, label = self.ghost
        self.canvas.coords(shadow, gx + round(4 * self.scaling), gy + round(5 * self.scaling),
                           gx + ghost_width + round(4 * self.scaling), gy + ghost_height + round(5 * self.scaling))
        self.canvas.coords(box, gx, gy, gx + ghost_width, gy + ghost_height)
        self.canvas.coords(symbol, gx + round(16 * self.scaling), gy + ghost_height / 2)
        self.canvas.coords(label, gx + round(32 * self.scaling), gy + ghost_height / 2)
        self.canvas.tag_raise("ghost")
        slot = None
        if left <= x <= left + width and top <= y <= top + height:
            cx, cy = self.canvas.canvasx(x - left), self.canvas.canvasy(y - top)
            row = min(max(0, math.floor((cy - round(self.GAP * self.scaling) - self.HEIGHT * self.scaling / 2) / self.step_y + 0.5)),
                      (len(self.page.files) - 1) // self.columns)
            count = min(self.columns, len(self.page.files) - row * self.columns)
            col = min(max(0, math.floor((cx - round(self.GAP * self.scaling) - self.card_width / 2) / self.step_x + 0.5)), count - 1)
            nearest = row * self.columns + col
            bx1, _, bx2, _ = self._bounds(nearest)
            slot = nearest + (cx > (bx1 + bx2) / 2)
            slot -= slot > self.drag["source"]
        self.drag["slot"] = slot
        if self.drag["shown_slot"] != slot:
            old = self.drag["shown_slot"]
            self.drag["shown_slot"] = slot
            self.drag["marker_started"] = time.perf_counter() if slot is not None else None
            self._style(self.drag["path"])
            if old is not None:
                self._style(self.page.files[old])
            if slot is not None:
                self._style(self.page.files[slot])
            self.page.order_hint.configure(text=f"วางที่ลำดับ {slot + 1} · Esc ยกเลิก" if slot is not None
                                           else "ลากกลับเข้ารายการเพื่อวาง · Esc ยกเลิก")
        self._paint_marker(slot)

    def _paint_marker(self, slot):
        """Animate one insertion cue without repainting the card grid."""
        if slot is None:
            if self.marker is not None:
                self.canvas.delete("drop-marker")
                self.marker = None
            return
        x1, y1, x2, y2 = self._bounds(slot)
        gap = round(self.GAP * self.scaling)
        x = x2 + gap / 2 if slot > self.drag["source"] else x1 - gap / 2
        middle = (y1 + y2) / 2
        progress = 1.0
        if self.motion_enabled and self.drag["marker_started"] is not None:
            progress = min(1.0, (time.perf_counter() - self.drag["marker_started"]) / self.MARKER_SECONDS)
            progress = 1 - (1 - progress) ** 3
        half = (y2 - y1 - round(20 * self.scaling)) * progress / 2
        thickness = max(2, round(4 * self.scaling))
        if self.marker is None:
            self.marker = self.canvas.create_rectangle(0, 0, 0, 0, fill=C["accent"],
                                                       outline="", tags="drop-marker")
        self.canvas.coords(self.marker, x - thickness / 2, middle - half,
                           x + thickness / 2, middle + half)
        self.canvas.tag_raise("drop-marker")
        self.canvas.tag_raise("ghost")

    def _raise_ghost(self):
        if self.marker is not None:
            self.canvas.tag_raise("drop-marker")
        if self.ghost:
            self.canvas.tag_raise("ghost")

    def _auto_scroll(self):
        self.scroll_timer = None
        if not self.drag or not self.drag["active"] or self.page.app.busy:
            return
        x, y = self.drag["pointer"]
        left, top = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        if left <= x <= left + self.canvas.winfo_width():
            direction = -1 if top <= y < top + 38 else (1 if top + self.canvas.winfo_height() - 38 < y <= top + self.canvas.winfo_height() else 0)
            if direction:
                self.canvas.yview_scroll(direction * round(25 * self.scaling), "units")
                self._schedule_draw()
                self._target()
        self.scroll_timer = self.page.app.root.after(55, self._auto_scroll)

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
            self.selected = path
            self.canvas.focus_set()
            self._reveal(path)
            self._schedule_draw()

    def cancel_drag(self):
        for name in ("frame_timer", "scroll_timer"):
            timer = getattr(self, name)
            if timer:
                self.page.app.root.after_cancel(timer)
                setattr(self, name, None)
        if self.ghost:
            self.canvas.delete("ghost")
            self.ghost = None
        if self.marker is not None:
            self.canvas.delete("drop-marker")
            self.marker = None
        if self.drag:
            self.canvas.grab_release()
            self.drag = None
            self.mouse_down = False
            self.canvas.configure(cursor="arrow")
            self._style(self.selected)
        self.page.order_hint.configure(text=self.HINT)

    def _focus_out(self, event):
        if self.drag:
            self.cancel_drag()
        self._style(self.selected)

    def _keyboard(self, name):
        if self.page.app.busy or not self.page.files:
            return "break"
        if self.selected not in self.page.files:
            self.selected = self.page.files[0]
        step = {"Left": -1, "Right": 1, "Up": -self.columns, "Down": self.columns}[name]
        path = self.selected
        old = self.page.files.index(path)
        index = max(0, min(len(self.page.files) - 1, old + step))
        self.page.reorder_file(path, index)
        self.selected = path
        self._reveal(path)
        self._schedule_draw()
        return "break"

    def _delete_selected(self, event):
        if not self.page.app.busy and self.selected in self.page.files:
            self.page.remove_file(self.selected)
        return "break"

    def _reveal(self, path):
        x1, y1, x2, y2 = self._bounds(self.page.files.index(path))
        top = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        extent = max(1, math.ceil(len(self.page.files) / self.columns) * self.step_y)
        if y1 < top:
            self.canvas.yview_moveto(y1 / extent)
        elif y2 > top + height:
            self.canvas.yview_moveto(max(0, (y2 - height) / extent))
        self._schedule_draw()

    def _poll_previews(self):
        self.preview_timer = None
        if not self.preview_active:
            return
        if self.drag is None:
            if self.pending and (self.worker.failed or self.worker.process is not None and not self.worker.process.is_alive()):
                for key in self.pending:
                    self.cache[key] = None
                self.pending.clear()
                self.worker.failed = True
                self.worker.close()
                self._schedule_draw()
            deadline = time.perf_counter() + 0.004
            try:
                for _ in range(2):
                    key, payload = self.worker.get_nowait()
                    self.pending.discard(key)
                    self.cache[key] = Image.frombytes("RGB", payload[:2], payload[2]) if payload else None
                    self._schedule_draw()
                    if time.perf_counter() >= deadline:
                        break
            except queue.Empty:
                pass
            if any(self.preview_keys.get(self.page.files[index]) not in self.cache for index in self.visible):
                self._schedule_draw()
        self.preview_timer = self.page.app.root.after(80, self._poll_previews)

    def set_preview_active(self, active):
        if self.preview_active == active:
            return
        self.preview_active = active
        self.worker.set_active(active)
        self.pending.clear()
        if active:
            self.render()
            self._poll_previews()
        else:
            self.cancel_drag()
            for name in ("draw_timer", "preview_timer"):
                timer = getattr(self, name)
                if timer:
                    self.page.app.root.after_cancel(timer)
                    setattr(self, name, None)
            self.canvas.delete("all")
            self.visible.clear()
            self.cache.clear()
            self.photos.clear()

    def destroy(self):
        for timer in (self.frame_timer, self.draw_timer, self.scroll_timer, self.preview_timer):
            if timer:
                self.page.app.root.after_cancel(timer)
        self.worker.close()
        super().destroy()
