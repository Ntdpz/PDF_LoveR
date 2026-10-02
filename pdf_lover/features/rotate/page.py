"""Hallmark native rotation workbench, using existing Cobalt tokens.

Pre-emit critique P4 H5 E4 S5 R5 V4. Per-document selection and actual before/after
previews precede batch save. All Tk access stays on the main thread.
"""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
import customtkinter as ctk
from pdf_lover.features.base import ToolPage
from pdf_lover.features.rotate.service import inspect_document, build_plan, rotate_pdf
from pdf_lover.core.document import DocumentError
from pdf_lover.core.page_selection import selected_pages, format_pages, PageSelectionError
from pdf_lover.platform.paths import documents_folder
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.page_preview import PagePreview
from pdf_lover.ui.theme import COLORS as C, SPACE as S, FONTS


class RotatePage(ToolPage):
    def __init__(self,parent,app):
        super().__init__(parent,app)
        self.inputs=[];self.expressions={};self.active=0
        self.plan=self.destination=self.preview_window=None
        self.events=queue.Queue();self.controls=[];self.switching=False
        self.angle=tk.StringVar(value="90")
        self.suffix=tk.StringVar(value="_หมุน")
        self.output=tk.StringVar(value=str(documents_folder()))
        self.status=tk.StringVar(value="เพิ่ม PDF · เลือกเอกสารเพื่อเลือกหน้าแต่ละไฟล์")
        self._build()
        for value in (self.angle,self.suffix,self.output):value.trace_add("write",self._settings_changed)
        self.refresh_plan()

    def _entry(self, parent, variable, width=180):
        entry = ctk.CTkEntry(parent, textvariable=variable, height=44, width=width,
                             font=self.font_small, fg_color=C["surface"], text_color=C["ink"],
                             border_width=2, border_color=C["rule"])
        self.app._entry_focus(entry)
        self.controls.append(entry)
        return entry

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        header = ctk.CTkFrame(self, fg_color=C["surface"], corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.label(header, "หมุน PDF", font=ctk.CTkFont(family=FONTS["body"], size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=S["2xl"], pady=S["sm"])
        home = self.button(header, "เครื่องมือทั้งหมด", self.app.show_home, width=200)
        home.grid(row=0, column=1, padx=S["2xl"])
        self.controls.append(home)
        source = ctk.CTkFrame(self, fg_color="transparent")
        source.grid(row=1, column=0, sticky="ew", padx=S["2xl"], pady=S["xs"])
        source.grid_columnconfigure(0, weight=1)
        self.documents = ctk.CTkComboBox(source, values=["ยังไม่มี PDF"], command=self.select_document,
                                        height=44, font=self.font_small, state="readonly",
                                        fg_color=C["surface"], text_color=C["ink"], border_color=C["rule"])
        self.documents.grid(row=0, column=0, sticky="ew", padx=(0,S["sm"]))
        self.remove_button = self.button(source, "นำออก", self.remove_document, width=90)
        self.remove_button.grid(row=0,column=1,padx=(0,S["sm"]))
        self.add_button = self.button(source, "เพิ่ม PDF…", self.add_files, width=150)
        self.add_button.grid(row=0,column=2)
        self.controls.extend((self.documents,self.remove_button,self.add_button))
        modes = ctk.CTkFrame(self, fg_color="transparent")
        modes.grid(row=2, column=0, sticky="ew", padx=S["2xl"], pady=S["xs"])
        self.label(modes, "หมุนเพิ่ม", font=self.font_small).grid(row=0,column=0,padx=(0,S["sm"]))
        self.angle_buttons=[]
        for index,(angle,title) in enumerate(((90,"ขวา 90°"),(180,"กลับหัว 180°"),(270,"ซ้าย 90°")),1):
            button=self.button(modes,title,lambda value=angle:self.angle.set(str(value)),width=140)
            button.grid(row=0,column=index,padx=(0,S["sm"]))
            self.angle_buttons.append(button);self.controls.append(button)
        self.names_button=self.button(modes,"ดูชื่อไฟล์ทั้งหมด…",self.show_names,width=190)
        self.names_button.grid(row=0,column=4,padx=S["sm"])
        self.controls.append(self.names_button)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", padx=S["2xl"], pady=S["sm"])
        body.grid_columnconfigure(0, weight=1, uniform="panels")
        body.grid_columnconfigure(1, weight=1, uniform="panels")
        body.grid_rowconfigure(0, weight=1)
        self.selector = PageSelector(body,self.app,self._settings_changed,title="หน้าที่จะหมุน",
                                     hint="เลือกหน้าในไฟล์นี้ · มุมเดียวกันใช้กับทุกไฟล์")
        self.selector.grid(row=0,column=0,sticky="nsew",padx=(0,S["sm"]))
        self.preview=PagePreview(body,self.app)
        self.preview.grid(row=0,column=1,sticky="nsew",padx=(S["sm"],0))
        settings = ctk.CTkFrame(self, fg_color="transparent")
        settings.grid(row=4, column=0, sticky="ew", padx=S["2xl"], pady=S["sm"])
        settings.grid_columnconfigure(1, weight=1)
        self.label(settings, "ต่อท้ายชื่อไฟล์", font=self.font_small).grid(row=0, column=0, sticky="w", padx=(0, S["md"]))
        self.suffix_entry = self._entry(settings, self.suffix)
        self.suffix_entry.grid(row=0, column=1, sticky="ew")
        self.label(settings, "โฟลเดอร์ปลายทาง", font=self.font_small).grid(row=1, column=0, sticky="w", padx=(0, S["md"]), pady=S["sm"])
        self.output_entry = self._entry(settings, self.output)
        self.output_entry.grid(row=1, column=1, sticky="ew", pady=S["sm"])
        browse = self.button(settings, "เลือกโฟลเดอร์…", self.choose_output, width=160)
        browse.grid(row=1, column=2, padx=(S["sm"], 0))
        self.controls.append(browse)
        activity = ctk.CTkFrame(self, fg_color=C["surface"])
        activity.grid(row=5, column=0, sticky="ew", padx=S["2xl"], pady=S["md"])
        activity.grid_columnconfigure(0, weight=1)
        self.status_label = self.label(activity, "", textvariable=self.status, font=self.font_small, wraplength=560, justify="left")
        self.status_label.grid(row=0, column=0, sticky="w", padx=S["lg"], pady=S["sm"])
        self.progress = ctk.CTkProgressBar(activity, height=6, fg_color=C["soft"], progress_color=C["accent"])
        self.progress.grid(row=1, column=0, sticky="ew", padx=S["lg"], pady=(0, S["sm"]))
        self.progress.set(0)
        self.start_button = self.button(activity, "หมุนและบันทึก PDF ใหม่", self.start, primary=True, width=210)
        self.start_button.grid(row=0, column=1, rowspan=2, padx=S["lg"])
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=6, column=0, sticky="ew", padx=S["2xl"], pady=(0, S["sm"]))
        foot.grid_columnconfigure(0, weight=1)
        self.label(foot, "Ctrl + O เลือก PDF · Ctrl + Enter บันทึก", font=self.font_small, color="muted").grid(row=0, column=0, sticky="w")
        self.open_button = self.button(foot, "เปิดโฟลเดอร์ผลลัพธ์", self.open_result, width=200)
        self.open_button.grid(row=0, column=1)
        self.open_button.configure(state="disabled")

    def _close_names(self):
        if self.preview_window is not None:
            self.preview_window.destroy();self.preview_window=None

    def _settings_changed(self,*_):
        if self.switching or self.busy:return
        if self.inputs:self.expressions[self.inputs[self.active].path]=self.selector.expression.get()
        self.destination=None;self.open_button.configure(state="disabled");self.progress.set(0)
        self._close_names();self.refresh_plan()

    def refresh_plan(self):
        self.plan=None
        raw=self.angle.get();angle=int(raw) if raw in ("90","180","270") else 0
        for button,value in zip(self.angle_buttons,(90,180,270)):
            button.configure(fg_color=C["tint"] if angle==value else C["surface"],border_color=C["accent"] if angle==value else C["rule"])
        self.selector.set_enabled(not self.busy)
        self.preview.set_enabled(not self.busy)
        if self.inputs:
            try:
                if not self.output.get().strip():raise DocumentError("เลือกโฟลเดอร์ปลายทางก่อนบันทึก")
                self.plan=build_plan(tuple(self.inputs),self.output.get(),self.suffix.get(),angle,dict(self.expressions))
                count=sum(len(j.selected) for j in self.plan.jobs)
                self.status.set(f"พร้อมหมุน {count} หน้า ใน {len(self.plan.jobs)} ไฟล์ · เก็บต้นฉบับไว้")
                self.status_label.configure(text_color=C["muted"])
            except DocumentError as error:
                self.status.set(str(error));self.status_label.configure(text_color=C["error"])
        info=self.inputs[self.active] if self.inputs else None
        try:pages=selected_pages(self.expressions.get(info.path,""),info.page_count) if info else ()
        except PageSelectionError:pages=()
        name=self.plan.jobs[self.active].output.path.name if self.plan else "ตรวจข้อมูลก่อนบันทึก"
        self.preview.set_document(info,pages,angle,name)
        self.start_button.configure(state="normal" if self.plan and not self.busy else "disabled")
        self.names_button.configure(state="normal" if self.plan and not self.busy else "disabled")
        self.remove_button.configure(state="normal" if self.inputs and not self.busy else "disabled")

    def _show_document(self):
        self.switching=True
        if self.inputs:
            self.active=min(self.active,len(self.inputs)-1)
            values=[f"{i}. {info.path.name} · {info.page_count} หน้า" for i,info in enumerate(self.inputs,1)]
            self.documents.configure(values=values);self.documents.set(values[self.active])
            info=self.inputs[self.active];self.selector.set_document(info)
            self.selector.expression.set(self.expressions.get(info.path,f"1-{info.page_count}"))
        else:
            self.documents.configure(values=["ยังไม่มี PDF"]);self.documents.set("ยังไม่มี PDF")
            self.selector.set_document(None)
        self.switching=False;self.refresh_plan()

    def select_document(self,value):
        if self.busy:return
        self.active=int(value.split(".",1)[0])-1
        self._close_names();self._show_document()

    def remove_document(self):
        if self.inputs and not self.busy:
            info=self.inputs.pop(self.active);self.expressions.pop(info.path,None)
            self.destination=None;self.open_button.configure(state="disabled")
            self._close_names();self._show_document()
            if not self.inputs:self.status.set("เพิ่ม PDF · เลือกเอกสารเพื่อเลือกหน้าแต่ละไฟล์")

    def add_files(self):
        if not self.busy:
            paths=filedialog.askopenfilenames(parent=self.root,title="เลือก PDF ที่จะหมุน",filetypes=[("PDF","*.pdf")])
            if paths:self.add_paths(paths)

    def add_paths(self,paths):
        if self.busy:return
        paths=tuple(paths)
        if not paths:return
        existing=tuple(info.path for info in self.inputs)
        self._lock("กำลังอ่านจำนวนหน้า PDF…")
        threading.Thread(target=self._inspect_worker,args=(paths,existing),daemon=True).start()

    def _inspect_worker(self,paths,existing):
        try:
            seen=set(existing);infos=[]
            for path in paths:
                resolved=Path(path).expanduser().resolve()
                if resolved not in seen:infos.append(inspect_document(resolved));seen.add(resolved)
            self.events.put(("loaded",tuple(infos)))
        except Exception as error:self.events.put(("error",str(error)))

    def choose_output(self):
        if not self.busy:
            folder=filedialog.askdirectory(parent=self.root,initialdir=self.output.get(),title="เลือกโฟลเดอร์ผลลัพธ์")
            if folder:self.output.set(folder)

    def _lock(self,message):
        self._close_names();self.busy=True;self.status.set(message)
        self.status_label.configure(text_color=C["muted"])
        for control in self.controls:control.configure(state="disabled")
        self.selector.set_enabled(False);self.preview.set_enabled(False)
        self.start_button.configure(state="disabled");self.open_button.configure(state="disabled")

    def start(self):
        if self.busy:return
        self.refresh_plan()
        if self.plan:
            plan=self.plan;self.destination=None;self.progress.set(0)
            self._lock("กำลังหมุนและตรวจชุด PDF ก่อนบันทึก…")
            threading.Thread(target=self._export_worker,args=(plan,),daemon=True).start()

    def _export_worker(self,plan):
        try:
            outputs=rotate_pdf(plan,lambda done,total,name:self.events.put(("progress",done,total,name)))
            self.events.put(("done",outputs))
        except Exception as error:self.events.put(("error",str(error)))

    def process_events(self):
        self.selector.process_events();self.preview.process_events()
        try:
            for _ in range(100):
                event=self.events.get_nowait()
                if event[0]=="progress":
                    self.progress.set(event[1]/event[2]*0.9);self.status.set(f"เตรียมไฟล์ {event[1]}/{event[2]} · {event[3]}");continue
                self.busy=False
                for control in self.controls:control.configure(state="normal")
                self.documents.configure(state="readonly")
                if event[0]=="loaded":
                    self.inputs.extend(event[1])
                    for info in event[1]:self.expressions[info.path]=f"1-{info.page_count}"
                    self.destination=None;self.open_button.configure(state="disabled");self._show_document()
                else:
                    self.selector.set_enabled(True);self.preview.set_enabled(True)
                    self.remove_button.configure(state="normal" if self.inputs else "disabled")
                    self.names_button.configure(state="normal" if self.plan else "disabled")
                    self.start_button.configure(state="normal" if self.plan else "disabled")
                    if event[0]=="done":
                        self.destination=event[1][0].parent;self.progress.set(1)
                        self.status.set(f"บันทึกสำเร็จ · {len(event[1])} ไฟล์ · เก็บต้นฉบับไว้แล้ว")
                        self.status_label.configure(text_color=C["success"])
                        self.open_button.configure(state="normal");self.start_button.configure(state="disabled")
                    else:
                        self.progress.set(0);self.status.set(event[1]);self.status_label.configure(text_color=C["error"])
        except queue.Empty:pass

    def preview_rows(self):
        return tuple((j.info.path.name,format_pages(j.selected),j.output.path.name) for j in self.plan.jobs) if self.plan else ()

    def show_names(self):
        if self.busy or not self.plan:return
        self._close_names()
        window=ctk.CTkToplevel(self.root);self.preview_window=window
        window.title("ชื่อไฟล์ก่อนบันทึก");window.geometry("860x380");window.transient(self.root)
        window.grid_columnconfigure(0,weight=1);window.grid_rowconfigure(0,weight=1)
        style=ttk.Style(window);style.configure("Rotate.Treeview",font=(FONTS["body"],12),rowheight=28)
        table=ttk.Treeview(window,columns=("source","pages","file"),show="headings",style="Rotate.Treeview",height=7)
        for key,title,width in (("source","ต้นฉบับ",240),("pages","หน้าที่หมุน",110),("file","ชื่อไฟล์ใหม่",360)):
            table.heading(key,text=title);table.column(key,width=width,minwidth=80)
        table.grid(row=0,column=0,sticky="nsew",padx=S["lg"],pady=S["sm"])
        scroll=ttk.Scrollbar(window,orient="vertical",command=table.yview);scroll.grid(row=0,column=1,sticky="ns")
        horizontal=ttk.Scrollbar(window,orient="horizontal",command=table.xview);horizontal.grid(row=1,column=0,sticky="ew",padx=S["lg"])
        table.configure(yscrollcommand=scroll.set,xscrollcommand=horizontal.set)
        rows=self.preview_rows();offset=[0]
        nav=ctk.CTkFrame(window,fg_color="transparent");nav.grid(row=2,column=0,sticky="ew",padx=S["lg"],pady=S["sm"]);nav.grid_columnconfigure(1,weight=1)
        count=self.label(nav,"",font=self.font_small,anchor="center");count.grid(row=0,column=1,sticky="ew")
        def render(delta=0):
            offset[0]=max(0,min(((len(rows)-1)//25)*25,offset[0]+delta*25))
            table.delete(*table.get_children())
            for row in rows[offset[0]:offset[0]+25]:table.insert("","end",values=row)
            count.configure(text=f"{offset[0]+1}–{min(offset[0]+25,len(rows))} / {len(rows)}")
        self.button(nav,"ก่อนหน้า",lambda:render(-1),width=88).grid(row=0,column=0)
        self.button(nav,"ถัดไป",lambda:render(1),width=88).grid(row=0,column=2)
        self.names_table=table;render();window.protocol("WM_DELETE_WINDOW",self._close_names)

    def open_result(self):
        if self.destination and not self.busy:
            try:os.startfile(str(self.destination))
            except OSError:self.status.set("เปิดโฟลเดอร์ไม่ได้ · ตรวจปลายทาง")
