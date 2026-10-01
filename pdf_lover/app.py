"""Application shell: navigation, shared job lock and event dispatch."""
from pathlib import Path
import customtkinter as ctk
from pdf_lover.catalog import TOOLS
from pdf_lover.features.registry import PAGE_FACTORIES, validate_registry
from pdf_lover.platform.file_drop import FileDrop
from pdf_lover.ui.controls import UIControls
from pdf_lover.ui.home import HomePage
from pdf_lover.ui.theme import COLORS as C
from pdf_lover.version import VERSION


class App(UIControls):
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.route = "home"
        self.closed = False
        self.event_timer = None
        root.title(f"PDF LoveR {VERSION} · เครื่องมือ PDF")
        icon = Path(__file__).resolve().parent / "assets" / "pdf_to_png.ico"
        if icon.exists():
            root.iconbitmap(str(icon))
        root.geometry("1080x780")
        root.minsize(920, 700)
        root.configure(fg_color=C["paper"])
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        self.init_fonts()
        validate_registry()
        self.views = {}
        self.home = HomePage(root, self)
        self.home.grid(row=0, column=0, sticky="nsew")
        self.show_home()
        self.file_drop = FileDrop(self)
        root.bind("<Control-o>", self._open_pdf_shortcut)
        root.bind("<Control-Return>", self._start_shortcut)
        root.bind("<Control-f>", self._search_shortcut)
        root.bind("<Alt-Left>", lambda _: self.show_home())
        root.bind("<Destroy>", self._destroyed, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.event_timer = root.after(80, self.process_events)

    @property
    def active_page(self):
        return self.views.get(self.route)

    def get_page(self, tool_id):
        """Create a ready page on first use and retain its queue/settings."""
        if tool_id not in self.views:
            self.views[tool_id] = PAGE_FACTORIES[tool_id](self.root, self)
        return self.views[tool_id]

    @property
    def png(self):
        return self.get_page("pdf-png")

    @property
    def merge(self):
        return self.get_page("merge")

    def show_home(self):
        if self.busy:
            self.active_status("กำลังทำงานอยู่ · รอให้เสร็จก่อนกลับไปเลือกเครื่องมือ")
            return False
        for view in self.views.values():
            view.grid_remove()
        self.home.grid()
        self.route = "home"
        self.root.title(f"PDF LoveR {VERSION} · เครื่องมือ PDF")
        return True

    def show_tool(self, tool_id):
        tool = next((item for item in TOOLS if item.id == tool_id), None)
        if tool is None:
            return False
        if not tool.ready:
            self.home.show_detail(tool)
            return False
        if self.busy and self.route != tool_id:
            return False
        self.get_page(tool_id)
        if self.home.detail_window:
            self.home.close_detail()
        self.home.grid_remove()
        for key, view in self.views.items():
            if key == tool_id:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_remove()
        self.route = tool_id
        self.root.title(tool.title + f" · PDF LoveR {VERSION}")
        self.active_page.add_button._canvas.focus_set()
        return True

    def accept_paths(self, paths):
        if self.busy:
            return
        if self.route == "home":
            self.show_tool("merge")
        self.active_page.add_paths(paths)

    def _open_pdf_shortcut(self, _=None):
        if not self.busy:
            if self.route == "home":
                self.show_tool("pdf-png")
            self.active_page.add_files()
        return "break"

    def _start_shortcut(self, _=None):
        if self.active_page:
            self.active_page.start()
        return "break"

    def active_status(self, message):
        (self.active_page or self.png).status.set(message)

    def _search_shortcut(self, _=None):
        if self.show_home():
            self.home.search_entry.focus_set()
        return "break"

    def process_events(self):
        self.event_timer = None
        if self.closed:
            return
        for page in self.views.values():
            page.process_events()
        self.event_timer = self.root.after(80, self.process_events)

    def _destroyed(self, event):
        if event.widget is self.root:
            self.closed = True
            if self.event_timer is not None:
                self.root.after_cancel(self.event_timer)
                self.event_timer = None

    def close(self):
        if self.busy:
            self.active_status("กำลังทำงานอยู่ · รอให้เสร็จก่อนปิดโปรแกรม")
        else:
            self.file_drop.close()
            self.root.destroy()
