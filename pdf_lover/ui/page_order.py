"""Ordered viewport reusing the shared bounded selector and preview coordinator."""
import math
import queue
from dataclasses import replace
from types import SimpleNamespace
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.core.page_selection import format_pages, PageSelectionError
from pdf_lover.core.page_order import move_selected, OrderHistory
from pdf_lover.core.document import DocumentError
from pdf_lover.ui.theme import COLORS as C


class PageOrder(PageSelector):
    def __init__(self, *args, **kwargs):
        self.order = ()
        self.sources = ()
        self.references = {}
        self.history = OrderHistory()
        self.drag = None
        kwargs.update(title='ลำดับหน้าใหม่', hint='เลือกตามลำดับใหม่ เช่น 1-3,5', select_initial=False)
        super().__init__(*args, **kwargs)
        self.gesture_hint.configure(text='Shift / Ctrl+คลิก: เลือกหลายหน้า · ลากหน้าเพื่อย้าย\nAlt+ลูกศร: ย้ายที่เลือก · Esc: ยกเลิกการลาก')
        self.canvas.bind('<Delete>', lambda _: self.delete_selected())

    def _control_keyboard(self, event):
        keycode = getattr(event, 'keycode', None)
        if event.keysym.lower() in ('z', 'y') or keycode in (90, 89):
            self.undo(redo=event.keysym.lower() == 'y' or keycode == 89 or bool(event.state & 1))
            return 'break'
        return super()._control_keyboard(event)

    def set_document(self, info):
        self.sources = (info,) if info else ()
        self.references = {p: (0, p) for p in range(1, info.page_count + 1)} if info else {}
        self.history.clear()
        self.order = tuple(range(1, info.page_count + 1)) if info else ()
        super().set_document(info)

    def _state(self):
        return self.order, self.expression.get()

    def _apply(self, order, expression=''):
        self._cancel_gesture()
        self.order = tuple(order)
        self.info = replace(self.sources[0], page_count=len(self.order))
        self.focused = max(1, min(self.focused, len(self.order)))
        self.anchor = self.focused
        self.selection_key = None
        self.expression.set(expression)
        self._resize()

    def undo(self, redo=False):
        if not self.enabled or not self.info:
            return
        state = self.history.step(self._state(), redo)
        if state:
            self._apply(*state)

    def append_documents(self, infos, before=None):
        if not infos:
            return
        if len(self.sources) + len(infos) > 64 or sum(i.page_count for i in self.sources + tuple(infos)) > 100000:
            raise DocumentError('รองรับต้นทางไม่เกิน 64 ไฟล์ / 100,000 หน้าในโต๊ะงานนี้')
        if any(info.path in {i.path for i in self.sources} for info in infos) or len({i.path for i in infos}) != len(infos):
            raise DocumentError('ไฟล์นี้อยู่ในโต๊ะงานแล้ว · ใช้ Undo หรือคืนต้นฉบับเพื่อเรียกหน้ากลับ')
        self.history.record(self._state())
        added = []
        for info in infos:
            source = len(self.sources)
            self.sources += (info,)
            for page in range(1, info.page_count + 1):
                identity = len(self.references) + 1
                self.references[identity] = (source, page)
                added.append(identity)
        slot = len(self.order) if before is None else max(0, min(len(self.order), before))
        self._apply(self.order[:slot] + tuple(added) + self.order[slot:], format_pages(range(slot + 1, slot + len(added) + 1)))

    def delete_selected(self):
        if not self.enabled or not self.info:
            return 'break'
        try:
            slots = set(self.selection())
        except PageSelectionError:
            return 'break'
        if not slots or len(slots) == len(self.order):
            self.counter.configure(text='เลือกหน้าที่จะลบ · ต้องเหลืออย่างน้อยหนึ่งหน้า')
            return 'break'
        self.history.record(self._state())
        self._apply(tuple(p for slot, p in enumerate(self.order, 1) if slot not in slots))
        return 'break'

    def selection(self):
        return super().selection() if self.expression.get().strip() else ()

    def _key(self, page):
        source, original = self.references[self.order[page - 1]]
        info = self.sources[source]
        return (info.path, info.signature[3], info.signature[2], original - 1, 0, 180, 200)

    def page_label(self, page):
        source, original = self.references[self.order[page - 1]]
        name = self.sources[source].path.stem
        return f'ใหม่ {page} · เดิม {original}' + (f'\n{name[:18]}' if source else '')

    def reset_order(self):
        if self.enabled and self.info:
            self._cancel_gesture()
            original = tuple(range(1, self.sources[0].page_count + 1))
            if self.order != original:
                self.history.record(self._state())
                self._apply(original)
            else:
                self.expression.set('')

    def _move(self, before):
        try:
            slots = self.selection()
        except PageSelectionError:
            return
        selected = {self.order[p - 1] for p in slots}
        if not selected:
            return
        order = move_selected(self.order, selected, before)
        if order == self.order:
            return
        self.history.record(self._state())
        self.order = order
        slots = [i for i, p in enumerate(self.order, 1) if p in selected]
        self.focused = slots[0]
        self.anchor = slots[0]
        self.expression.set(format_pages(slots))

    def nudge(self, direction):
        if not self.enabled or not self.info:
            return
        try:
            slots = self.selection()
        except PageSelectionError:
            return
        if slots:
            self._move(max(0, min(slots) - 2) if direction < 0 else min(len(self.order), max(slots) + 1))

    def _press(self, event):
        if not self.enabled or not self.info:
            return
        page = self._hit(event)
        if page is None or event.state & 5:
            return super()._press(event)
        self._cancel_gesture()
        self.canvas.focus_set()
        try:
            selected = self.selection()
        except PageSelectionError:
            selected = ()
        if page not in selected:
            self.expression.set(str(page))
        self.focused = self.anchor = page
        self.drag = {'start': (event.x, event.y), 'page': page, 'active': False}
        self.gesture = {'pointer': (event.x, event.y), 'active': False}
        self.canvas.grab_set()
        self.render()

    def _motion(self, event):
        if not self.drag:
            return super()._motion(event)
        self.gesture['pointer'] = (event.x, event.y)
        if math.dist(self.drag['start'], (event.x, event.y)) >= 6 * self.scaling:
            self.drag['active'] = True
            self.gesture['active'] = True
            self.canvas.configure(cursor='fleur')
            self._schedule()
            self._schedule_edge()

    def _drop_slot(self, event):
        width = self.canvas.winfo_width() / self.columns
        row = max(0, int(self.canvas.canvasy(event.y) // self.step_y))
        column = max(0, min(self.columns - 1, int(event.x // width)))
        after = event.x % width > width / 2
        return min(len(self.order), row * self.columns + column + int(after))

    def _release(self, event):
        if not self.drag:
            return super()._release(event)
        active, slot = self.drag['active'], self._drop_slot(event)
        self._cancel_gesture()
        if active:
            self._move(slot)
        self.render()

    def _cancel_gesture(self):
        self.drag = None
        super()._cancel_gesture()

    def _keyboard(self, event):
        if event.state & 8 and event.keysym in ('Left', 'Up', 'Right', 'Down'):
            self._cancel_gesture()
            self.nudge(-1 if event.keysym in ('Left', 'Up') else 1)
            return 'break'
        return super()._keyboard(event)

    def render(self):
        # Parent selection/marquee rendering remains unchanged for blank-area gestures.
        gesture = self.gesture
        self.previews_paused = bool(self.drag)
        if self.drag:
            self.gesture = None
        super().render()
        self.gesture = gesture
        if self.drag and self.drag['active']:
            x, y = gesture['pointer']
            slot = self._drop_slot(SimpleNamespace(x=x, y=y))
            page = min(len(self.order), slot + 1)
            if page in self.visible:
                x1, y1, x2, y2 = self.visible[page]
                marker = x2 if slot == len(self.order) else x1
                self.canvas.create_line(marker, y1, marker, y2, fill=C['accent'], width=4 * self.scaling)
            self.counter.configure(text=f'ย้ายหน้าที่เลือกก่อนลำดับ {slot + 1}' if slot < len(self.order) else 'ย้ายหน้าที่เลือกไปท้ายเอกสาร')
            self.canvas.create_text(x, self.canvas.canvasy(y) - 12, text='ปล่อยเพื่อย้าย · Esc ยกเลิก', anchor='s', fill=C['ink'])

    def process_events(self):
        if self.drag or not self.preview_active:
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
                if key in self.worker.required:
                    self.cache[key] = payload
                updated = True
        except queue.Empty:
            pass
        if updated or any(key not in self.cache and key not in self.pending for key in self.worker.required):
            self.render()
