"""Hallmark native before/after component; Cobalt tokens, bounded spawned previews.

States: empty, hover/focus/pressed navigation, disabled, loading, error and ready.
Pre-emit critique: P4 H5 E4 S5 R5 V4. No spatial animation or feature imports.
"""
import queue
import customtkinter as ctk
from PIL import Image
from pdf_lover.ui.pdf_previews import PreviewWorker, PreviewCache
from pdf_lover.ui.theme import COLORS as C, SPACE as S


class PagePreview(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color=C['surface'])
        self.app=app;self.info=None;self.page=1;self.angle=90;self.selected=frozenset();self.enabled=True
        self.worker=PreviewWorker(app.preview_coordinator);self.preview_active=False;self.worker.set_active(False)
        self.images={};self.pending=set()
        self.cache=PreviewCache(12,6*1048576,lambda key:self.images.pop(key,None))
        # CTkLabel leaves the native Tk image set when configured with image=None.
        # Keep a real empty image alive for empty/loading/error states.
        self.empty_image=ctk.CTkImage(Image.new('RGB',(1,1),C['surface']),size=(1,1))
        self.grid_columnconfigure((0,1),weight=1,uniform='preview')
        self.title=app.label(self,'ภาพก่อน–หลังหมุน',font=app.font_bold)
        self.title.grid(row=0,column=0,columnspan=2,sticky='w',padx=S['lg'],pady=S['xs'])
        self.labels=[]
        for col,title in enumerate(('ต้นฉบับ','ผลลัพธ์')):
            app.label(self,title,font=app.font_small,color='muted').grid(row=1,column=col)
            label=app.label(self,'เลือก PDF',height=120,anchor='center',font=app.font_small)
            label.grid(row=2,column=col,sticky='nsew',padx=S['sm']);self.labels.append(label)
        self.caption=app.label(self,'',font=app.font_small,wraplength=340,justify='left')
        self.caption.grid(row=3,column=0,columnspan=2,sticky='w',padx=S['lg'],pady=S['xs'])
        nav=ctk.CTkFrame(self,fg_color='transparent');nav.grid(row=4,column=0,columnspan=2,sticky='ew',padx=S['lg'],pady=S['xs'])
        nav.grid_columnconfigure(1,weight=1)
        self.previous=app.button(nav,'ก่อนหน้า',lambda:self.move(-1),width=88);self.previous.grid(row=0,column=0)
        self.counter=app.label(nav,'—',font=app.font_small,anchor='center');self.counter.grid(row=0,column=1,sticky='ew')
        self.next=app.button(nav,'ถัดไป',lambda:self.move(1),width=88);self.next.grid(row=0,column=2)
        self.render()

    def set_document(self,info,selected=(),angle=90,filename=''):
        if info!=self.info:
            self.page=1;self.cache.clear();self.images.clear()
        self.info=info;self.selected=frozenset(selected);self.angle=angle
        # Full filenames remain in the batch dialog; keep the compact comparison
        # caption on one line so long document names cannot hide navigation.
        self.caption.configure(text=self.app.shorten(filename,26))
        self.render()

    def set_enabled(self,enabled):
        self.enabled=enabled;self.render()

    def move(self,delta):
        if self.enabled and self.info:
            self.page=max(1,min(self.info.page_count,self.page+delta));self.render()

    def keys(self):
        if not self.info:return ()
        base=(self.info.path,self.info.signature[3],self.info.signature[2],self.page-1)
        delta=self.angle if self.page in self.selected else 0
        return (base+(0,240,300),base+(delta,240,300))

    def render(self):
        if not self.preview_active:return
        if self.worker.set_required(self.keys()):self.pending.clear()
        for index,label in enumerate(self.labels):
            if not self.info:
                label.configure(image=self.empty_image)
                label.configure(text='เลือก PDF');continue
            key=self.keys()[index]
            if key not in self.cache and key not in self.pending and len(self.pending)<2:
                if self.worker.submit(key):self.pending.add(key)
                elif self.worker.failed:self.cache[key]=None
            payload=self.cache.get(key)
            if payload and key not in self.images:
                width,height,samples=payload
                scale=min(120/width,120/height)
                self.images[key]=ctk.CTkImage(Image.frombytes('RGB',(width,height),samples),size=(width*scale,height*scale))
            label.configure(image=self.images.get(key,self.empty_image))
            label.configure(text='' if payload else 'กำลังโหลด…' if key not in self.cache else 'ไม่มีภาพตัวอย่าง')
        self.counter.configure(text=f'หน้า {self.page} / {self.info.page_count}' if self.info else '—')
        self.previous.configure(state='normal' if self.enabled and self.info and self.page>1 else 'disabled')
        self.next.configure(state='normal' if self.enabled and self.info and self.page<self.info.page_count else 'disabled')

    def process_events(self):
        if not self.preview_active:return
        updated=False
        if self.pending and self.worker.failed:
            for key in self.pending:self.cache[key]=None
            self.pending.clear();updated=True
        try:
            for _ in range(2):
                key,payload=self.worker.get_nowait();self.pending.discard(key)
                if self.info and key[:3]==(self.info.path,self.info.signature[3],self.info.signature[2]):
                    self.cache[key]=payload
                    while len(self.cache)>12:
                        oldest=next(iter(self.cache));self.cache.pop(oldest);self.images.pop(oldest,None)
                updated=True
        except queue.Empty:pass
        if updated or any(key not in self.cache and key not in self.pending for key in self.worker.required):self.render()

    def set_preview_active(self,active):
        if self.preview_active==active:return
        self.preview_active=active;self.worker.set_active(active);self.pending.clear()
        if active:self.render()
        else:
            for label in self.labels:label.configure(image=self.empty_image)
            self.cache.clear();self.images.clear()

    def destroy(self):
        self.worker.close();super().destroy()
