"""Per-document selection dialog using the existing bounded preview coordinator."""
import customtkinter as ctk
from pdf_lover.core.page_selection import PageSelectionError, format_pages
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.theme import COLORS as C, SPACE as S


class ImagePageSelection(ctk.CTkToplevel):
    def __init__(self, page, info, expression):
        super().__init__(page.root)
        self.page, self.info = page, info
        self.title("เลือกหน้าที่จะแปลง · " + info.path.name)
        self.geometry("780x700")
        self.minsize(650, 620)
        self.transient(page.root)
        self.configure(fg_color=C["paper"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        page.label(self, page.shorten(info.path.name, 48), font=page.font_bold).grid(row=0,column=0,sticky="w",padx=S["lg"],pady=S["sm"])
        self.selector = PageSelector(self, page.app, self.changed, title="หน้าที่จะแปลงภาพ",
                                     hint="เช่น 1-3,5,8 · ชื่อภาพคงเลขหน้าต้นฉบับ")
        self.selector.grid(row=1,column=0,sticky="nsew",padx=S["sm"])
        self.selector.set_document(info)
        if expression is not None:self.selector.expression.set(expression)
        self.selector.set_preview_active(True)
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2,column=0,sticky="ew",padx=S["lg"],pady=S["sm"])
        bottom.grid_columnconfigure(0,weight=1)
        self.summary = page.label(bottom,"",font=page.font_small,wraplength=420)
        self.summary.grid(row=0,column=0,sticky="w")
        self.apply_button = page.button(bottom,"ยืนยันหน้าที่เลือก",self.apply,primary=True,width=180)
        self.apply_button.grid(row=0,column=1,padx=S["sm"])
        self.protocol("WM_DELETE_WINDOW",page.close_selection)
        self.bind("<Escape>",lambda event: page.close_selection() if event.widget is not self.selector.canvas else None)
        self.grab_set()
        self.changed()

    def destroy(self):
        if hasattr(self,"selector"):
            self.selector.set_preview_active(False)
        super().destroy()

    def changed(self):
        if not hasattr(self,"apply_button"):return
        try:
            selected=self.selector.selection()
            self.summary.configure(text=f"แปลง {len(selected)}/{self.info.page_count} หน้า · หนึ่งภาพต่อหน้า",text_color=C["ink"])
            self.apply_button.configure(state="normal")
        except PageSelectionError as error:
            self.summary.configure(text=str(error),text_color=C["error"])
            self.apply_button.configure(state="disabled")

    def apply(self):
        if self.page.busy:return
        try:selected=self.selector.selection()
        except PageSelectionError:return
        self.page.selections[self.info.path]=(self.info,format_pages(selected))
        self.page.close_selection()
        self.page._render_files()
        self.page._queue_changed()
