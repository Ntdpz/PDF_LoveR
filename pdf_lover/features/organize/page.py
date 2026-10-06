"""Order workbench with the existing worker, cancellation and publication lifecycle."""
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.ui.page_order import PageOrder
from pdf_lover.features.organize.service import build_plan, build_edit_plan, organize_pdf
from pathlib import Path
import queue
import threading
from tkinter import filedialog
from pdf_lover.core.document import DocumentError
from pdf_lover.core.cancellation import Cancelled, checkpoint


class OrderRows:
    """Format only the requested 25 table rows, even for long documents."""
    def __init__(self, page):
        self.page = page

    def __len__(self):
        return len(self.page.selector.order)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(len(self))))
        selector = self.page.selector
        source, original = selector.references[selector.order[index]]
        if len(selector.sources) == 1:
            return f'{index+1} (เดิม {original})', self.page.plan.outputs[0].path.name
        return f'{index+1} ← {original}', selector.sources[source].path.name


class OrganizePage(SelectionPage):
    TITLE = 'จัดเรียงหน้า PDF'
    SUFFIX = '_จัดเรียง'
    SAVE_LABEL = 'บันทึก PDF ตามลำดับใหม่'
    ORDER = True
    EVENT_LIMIT = 32
    SELECTOR_CLASS = PageOrder
    export = staticmethod(organize_pdf)

    def __init__(self, *args):
        self._reading = False
        super().__init__(*args)
        self.add_button.configure(text='เพิ่ม PDF…')
        self.masthead_title.configure(text='จัดหน้า', font=self.font_bold)
        self.results.heading('file', text='ต้นทาง / ไฟล์ผลลัพธ์')
        self.order_focus = []
        for control in self.controls:
            if str(control).startswith(str(self.order_options) + '.'):
                target = getattr(control, '_entry', getattr(control, '_canvas', control))
                target.configure(takefocus=1)
                target.bind('<FocusIn>', lambda event: self._reveal_setting(event.widget), add='+')
                self.order_focus.append(target)

    def _reveal_setting(self, widget):
        canvas = self.order_options._parent_canvas
        top, bottom = canvas.winfo_rooty(), canvas.winfo_rooty()+canvas.winfo_height()
        y, end = widget.winfo_rooty(), widget.winfo_rooty()+widget.winfo_height()
        delta = y-top-8 if y < top else end-bottom+8 if end > bottom else 0
        box = canvas.bbox('all')
        if delta and box and box[3] > 0:
            canvas.yview_moveto(max(0, (canvas.canvasy(0)+delta)/box[3]))

    def refresh_plan(self):
        super().refresh_plan()
        if hasattr(self, 'edit_buttons'):
            for button, stack in zip(self.edit_buttons[1:3], (self.selector.history.undo_stack, self.selector.history.redo_stack)):
                button.configure(state='normal' if stack and not self.busy else 'disabled')

    def add_files(self):
        if not self.busy:
            paths = filedialog.askopenfilenames(parent=self.root, title='เพิ่มหน้าจาก PDF · ก่อนหน้าที่เลือก หรือท้ายเอกสาร', filetypes=[('PDF', '*.pdf')])
            if paths:
                self.add_paths(paths)

    def replace_document(self):
        if not self.busy:
            path = filedialog.askopenfilename(parent=self.root, title='เริ่มโต๊ะงานใหม่ · ประวัติปัจจุบันจะถูกล้าง', filetypes=[('PDF', '*.pdf')])
            if path:
                self.add_paths([path], replace=True)

    def add_paths(self, paths, replace=False):
        if self.busy or not paths:
            return
        paths = tuple(Path(path).expanduser().resolve() for path in paths)
        try:
            slots = () if replace or not self.info else self.selector.selection()
        except ValueError as error:
            self.status.set(str(error))
            return
        before = min(slots) - 1 if slots else None
        self._reading = True
        self._lock('กำลังตรวจ PDF ที่เพิ่ม · ยกเลิกได้โดยเก็บโต๊ะงานเดิม')
        threading.Thread(target=self._read_documents, args=(paths, replace, before), daemon=True).start()

    def _read_documents(self, paths, replace, before):
        try:
            infos = []
            for path in paths:
                checkpoint(self.cancel_event)
                infos.append(self.inspect(path))
            checkpoint(self.cancel_event)
            self.events.put(('imported', tuple(infos), replace, before))
        except Cancelled as error:
            self.events.put(('cancelled', str(error)))
        except Exception as error:
            self.events.put(('error', str(error)))

    def process_events(self):
        if not self._reading:
            return super().process_events()
        self.selector.process_events()
        try:
            event = self.events.get_nowait()
        except queue.Empty:
            return
        self._reading = False
        self.busy = False
        for control in self.controls:
            control.configure(state='normal')
        self.selector.set_enabled(True)
        error = None
        if event[0] == 'imported' and self.cancel_event.is_set():
            event = ('cancelled', 'ยกเลิกการอ่านแล้ว · เก็บโต๊ะงานเดิม')
        if event[0] == 'imported':
            infos, replace, before = event[1:]
            try:
                # Validate the complete batch before changing any existing edit state.
                if len(infos) + (0 if replace or not self.info else len(self.selector.sources)) > 64 or sum(i.page_count for i in infos) + (0 if replace or not self.info else sum(i.page_count for i in self.selector.sources)) > 100000:
                    raise DocumentError('รองรับไม่เกิน 64 ไฟล์ / 100,000 หน้าต้นทาง')
                if len({i.path for i in infos}) != len(infos):
                    raise DocumentError('ไฟล์ในชุดที่เพิ่มซ้ำกัน')
                if replace or not self.info:
                    self.info = infos[0]
                    self.selector.set_document(self.info)
                    self.prefix.set(self.info.path.stem[:90] + self.SUFFIX)
                    self.selector.append_documents(infos[1:])
                    self.selector.history.clear()
                else:
                    self.selector.append_documents(infos, before)
                self.source_label.configure(text=f'{self.shorten(self.info.path.name, 28)} · ต้นทาง {len(self.selector.sources)} ไฟล์')
            except DocumentError as failure:
                error = str(failure)
        else:
            error = event[1]
        self.destination = None
        self.progress.set(0)
        self.refresh_plan()
        if error:
            self.status.set(error)

    def preview_rows(self):
        if not self.plan:
            return ()
        return OrderRows(self)

    def build_plan(self, info, directory, prefix, expression, mode):
        if len(self.selector.sources) == 1 and len(self.selector.order) == info.page_count:
            return build_plan(info, directory, prefix, self.selector.order)
        return build_edit_plan(self.selector.sources, directory, prefix,
                               tuple(self.selector.references[p] for p in self.selector.order))
