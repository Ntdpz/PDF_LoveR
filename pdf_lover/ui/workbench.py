"""Hallmark Workbench: document viewport, review rail and fixed save bar.

Native Windows adaptation of the locked design.md. No PDF work or extra polling.
Pre-emit critique: P5 H5 E4 S5 R5 V4.
"""
from tkinter import ttk
import customtkinter as ctk
from pdf_lover.ui.theme import COLORS as C, SPACE as S, FONTS
from pdf_lover.ui.page_selector import PageSelector
from pdf_lover.ui.page_preview import PagePreview


def shell(page, title, instruction, *, scroll_review=False):
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(2, weight=1)
    from pdf_lover.ui.navigation import masthead
    masthead(page,title)
    source = ctk.CTkFrame(page, fg_color='transparent')
    source.grid(row=1, column=0, sticky='ew', padx=S['xl'], pady=S['sm'])
    source.grid_columnconfigure(0, weight=1)
    body = ctk.CTkFrame(page, fg_color='transparent')
    body.grid(row=2, column=0, sticky='nsew', padx=S['xl'], pady=(0, S['sm']))
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=0, minsize=328)
    body.grid_rowconfigure(0, weight=1)
    rail = (ctk.CTkScrollableFrame(body, width=328, fg_color=C['surface']) if scroll_review
            else ctk.CTkFrame(body, width=328, fg_color=C['surface']))
    rail.grid(row=0, column=1, sticky='nsew', padx=(S['md'], 0))
    rail.grid_columnconfigure(0, weight=1)
    # A single workflow sentence, rather than another tall stepper above the PDF.
    page.label(source, instruction.replace(' → ', ' · '), font=page.font_small, color='muted').grid(row=1, column=0, columnspan=3, sticky='w', pady=(S['xs'], 0))
    return source, body, rail


def save_bar(page, label):
    activity = ctk.CTkFrame(page, fg_color=C['surface'], corner_radius=0)
    activity.grid(row=3, column=0, sticky='ew')
    activity.grid_columnconfigure(0, weight=1)
    page.status_label = page.label(activity, '', textvariable=page.status, font=page.font_small,
                                   wraplength=590, justify='left')
    page.status_label.grid(row=0, column=0, sticky='ew', padx=S['xl'], pady=(S['sm'], 0))
    page.progress = ctk.CTkProgressBar(activity, height=4, fg_color=C['soft'], progress_color=C['accent'])
    page.progress.grid(row=1, column=0, sticky='ew', padx=S['xl'], pady=S['xs'])
    page.progress.set(0)
    page.label(activity, 'Ctrl+O เลือก PDF · Ctrl+Enter บันทึก', font=page.font_small, color='muted').grid(
        row=2, column=0, sticky='w', padx=S['xl'], pady=(0, S['sm']))
    actions = ctk.CTkFrame(activity, fg_color='transparent')
    actions.grid(row=0, column=1, rowspan=3, padx=S['xl'], pady=S['sm'])
    page.start_button = page.button(actions, label, page.start, primary=True, width=232)
    page.start_button.pack(pady=(0, S['xs']))
    page.open_button = page.button(actions, 'เปิดโฟลเดอร์ผลลัพธ์', page.open_result, width=232)
    page.open_button.pack()
    page.open_button.configure(state='disabled')
    def fit(event):
        if event.widget is activity:
            scale = page._get_widget_scaling()
            page.status_label.configure(wraplength=max(240, event.width / scale - 310))
    activity.bind('<Configure>', fit, add='+')


def output_settings(page, rail, row, variable, title):
    settings = ctk.CTkFrame(rail, fg_color='transparent')
    settings.grid(row=row, column=0, sticky='ew', padx=S['md'], pady=S['xs'])
    settings.grid_columnconfigure(0, weight=1)
    page.label(settings, title, font=page.font_small, height=24).grid(row=0, column=0, columnspan=2, sticky='w')
    field = page._entry(settings, variable)
    field.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, S['xs']))
    page.label(settings, 'โฟลเดอร์ปลายทาง', font=page.font_small, height=24).grid(row=2, column=0, columnspan=2, sticky='w')
    page.output_entry = page._entry(settings, page.output)
    page.output_entry.grid(row=3, column=0, sticky='ew', pady=S['xs'], padx=(0, S['xs']))
    browse = page.button(settings, 'เลือก…', page.choose_output, width=72)
    browse.grid(row=3, column=1, pady=S['xs'])
    page.controls.append(browse)
    return field


def selection_workbench(page, *, split=False):
    title = 'แยก PDF' if split else 'จัดเรียงหน้า' if getattr(page, 'ORDER', False) else page.TITLE
    source, body, rail = shell(page, title, 'เลือกเอกสาร → เลือกหน้าและตั้งค่า → ตรวจผล → บันทึกไฟล์ใหม่')
    page.source_label = page.label(source, 'เลือก PDF หรือวางไฟล์จาก Explorer', font=page.font_bold)
    page.source_label.grid(row=0, column=0, sticky='ew', padx=(0, S['sm']))
    page.add_button = page.button(source, 'เลือก PDF…', page.add_files, width=150)
    page.add_button.grid(row=0, column=1)
    page.controls.append(page.add_button)
    # Fit long Thai filenames inside their actual available space.
    source.bind('<Configure>', lambda e: page.source_label.configure(wraplength=max(200, e.width/page._get_widget_scaling()-170)), add='+')
    page.selector = getattr(page, 'SELECTOR_CLASS', PageSelector)(body, page.app, page._settings_changed,
                                title='หน้าเอกสาร' if split else 'หน้าที่จะลบ' if page.DELETE else 'หน้าที่จะบันทึก',
                                hint='ช่วงหน้า เช่น 1-3,5,8-10', select_initial=split or not page.DELETE)
    page.selector.grid(row=0, column=0, sticky='nsew')
    options = ctk.CTkScrollableFrame(rail, height=238, fg_color='transparent', corner_radius=0,
                                    scrollbar_button_color=C['rule'])
    options.grid(row=0,column=0,sticky='ew',padx=S['xs'])
    options.grid_columnconfigure(0,weight=1)
    modes = ctk.CTkFrame(options, fg_color='transparent')
    modes.grid(row=0, column=0, sticky='ew', padx=S['md'], pady=S['xs'])
    modes.grid_columnconfigure(0, weight=1)
    page.mode_buttons = []
    choices = (('pages','หนึ่งไฟล์ต่อหน้า'),('ranges','แบ่งตามช่วงหน้า'),('chunks','แบ่งทุก N หน้า')) if split else (
        () if page.DELETE or getattr(page, 'ORDER', False) else (('single','PDF เดียวรวมหน้าที่เลือก'),('pages','หนึ่งไฟล์ต่อหน้าที่เลือก')))
    if choices:
        page.label(modes, 'ตั้งค่าผลลัพธ์', font=page.font_bold, height=24).grid(row=0, column=0, sticky='w')
        titles=dict(choices)
        page.mode_menu=ctk.CTkOptionMenu(modes,values=list(titles.values()),height=44,
                                       font=page.font_body,dropdown_font=page.font_body,
                                       fg_color=C['soft'],text_color=C['ink'],button_color=C['rule'],
                                       button_hover_color=C['tint'],dropdown_fg_color=C['surface'],
                                       dropdown_text_color=C['ink'],
                                       command=lambda text:page.mode.set(next(k for k,v in titles.items() if v==text)))
        page.mode_menu.grid(row=1,column=0,sticky='ew')
        page.controls.append(page.mode_menu)
        page.mode_menu._canvas.configure(takefocus=1)
        page.mode_menu._canvas.bind('<FocusIn>', lambda _: page.mode_menu.configure(button_color=C['focus']))
        page.mode_menu._canvas.bind('<FocusOut>', lambda _: page.mode_menu.configure(button_color=C['rule']))
        for key in ('<Return>', '<space>', '<Alt-Down>'):
            page.mode_menu._canvas.bind(key, lambda _: page.mode_menu._open_dropdown_menu())
        def sync(*_):
            page.mode_menu.set(titles[page.mode.get()])
            if split and hasattr(page,'chunk_container'):
                page.chunk_container.grid(row=2,column=0,sticky='ew',pady=S['xs']) if page.mode.get()=='chunks' else page.chunk_container.grid_forget()
        page.mode.trace_add('write',sync)
        sync()
    else:
        if getattr(page, 'ORDER', False):
            for index, (title, command) in enumerate((('ย้ายก่อน', lambda: page.selector.nudge(-1)),
                                                    ('ย้ายหลัง', lambda: page.selector.nudge(1)),
                                                    ('คืนลำดับเดิม', page.selector.reset_order))):
                button = page.button(modes, title, command, width=130)
                button.grid(row=index, column=0, sticky='ew', pady=S['xs'])
                page.controls.append(button)
        else:
            page.label(modes, 'เลือกหน้าที่จะลบ\nตรวจหน้าที่เหลือก่อนบันทึก', font=page.font_small, justify='left').grid(row=0,column=0,sticky='w')
    if split:
        chunk = ctk.CTkFrame(modes, fg_color='transparent')
        chunk.grid(row=2,column=0,sticky='ew',pady=S['xs'])
        page.chunk_container=chunk
        page.chunk_entry = page._entry(chunk,page.chunk_size,width=70)
        page.chunk_entry.pack(side='left')
        page.label(chunk,'หน้าต่อไฟล์',font=page.font_small).pack(side='left',padx=S['sm'])
        chunk.grid_forget()
    page.prefix_entry = output_settings(page,options,1,page.prefix,'ชื่อชุดไฟล์' if split else 'ชื่อไฟล์ (ไม่ต้องใส่ .pdf)')
    rail.grid_rowconfigure(2,weight=1)
    page.summary = page.label(rail,'ไฟล์ที่จะได้',font=page.font_bold,wraplength=300,justify='left')
    page.summary.grid(row=1,column=0,sticky='ew',padx=S['md'])
    table = ctk.CTkFrame(rail,fg_color='transparent')
    table.grid(row=2,column=0,sticky='nsew',padx=S['md'],pady=S['xs'])
    table.grid_columnconfigure(0,weight=1);table.grid_rowconfigure(0,weight=1)
    style = ttk.Style(page)
    style.configure('Split.Treeview',font=(FONTS['body'],12),rowheight=32,background=C['surface'],foreground=C['ink'],fieldbackground=C['surface'])
    style.configure('Split.Treeview.Heading',font=(FONTS['body'],12,'bold'))
    page.results = ttk.Treeview(table,columns=('pages','file'),show='headings',style='Split.Treeview',height=2)
    page.results.heading('pages',text='หน้า' if split else 'ใหม่ (เดิม)')
    page.results.heading('file',text='ชื่อไฟล์ที่จะได้')
    page.results.column('pages',width=80,minwidth=70,stretch=False)
    page.results.column('file',width=245,minwidth=140)
    page.results.grid(row=0,column=0,sticky='nsew')
    vertical=ttk.Scrollbar(table,orient='vertical',command=page.results.yview);vertical.grid(row=0,column=1,sticky='ns')
    horizontal=ttk.Scrollbar(table,orient='horizontal',command=page.results.xview);horizontal.grid(row=1,column=0,sticky='ew')
    page.results.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
    nav=ctk.CTkFrame(rail,fg_color='transparent');nav.grid(row=3,column=0,sticky='ew',padx=S['md'],pady=S['xs'])
    nav.grid_columnconfigure(1,weight=1)
    page.prev_outputs=page.button(nav,'ก่อน',lambda:page.move_outputs(-1),width=64);page.prev_outputs.grid(row=0,column=0)
    page.output_counter=page.label(nav,'—',font=page.font_small,anchor='center');page.output_counter.grid(row=0,column=1,sticky='ew')
    page.next_outputs=page.button(nav,'ถัดไป',lambda:page.move_outputs(1),width=64);page.next_outputs.grid(row=0,column=2)
    save_bar(page,'แยกและบันทึก PDF' if split else page.SAVE_LABEL)


def rotation_workbench(page):
    from pdf_lover.ui.icons import rotation_icon
    from pdf_lover.ui.tooltip import Tooltip
    source, body, rail = shell(page,'หมุน PDF','เลือกเอกสาร → เลือกหน้า → หมุนและตรวจภาพ → บันทึกไฟล์ใหม่',scroll_review=True)
    page.documents=ctk.CTkComboBox(source,values=['ยังไม่มี PDF'],command=page.select_document,height=44,
                                  font=page.font_body,dropdown_font=page.font_body,state='readonly',
                                  fg_color=C['surface'],text_color=C['ink'],border_color=C['rule'])
    page.documents.grid(row=0,column=0,sticky='ew',padx=(0,S['sm']))
    page.remove_button=page.button(source,'นำออก',page.remove_document,width=84)
    page.remove_button.grid(row=0,column=1,padx=(0,S['sm']))
    page.add_button=page.button(source,'เพิ่ม PDF…',page.add_files,width=144)
    page.add_button.grid(row=0,column=2)
    page.controls.extend((page.documents,page.remove_button,page.add_button))
    page.selector=PageSelector(body,page.app,page._settings_changed,title='หน้าที่จะหมุน',hint='ช่วงหน้า เช่น 1-3,5 · เลือกแยกได้แต่ละไฟล์')
    page.selector.grid(row=0,column=0,sticky='nsew')
    modes=ctk.CTkFrame(rail,fg_color='transparent');modes.grid(row=0,column=0,sticky='ew',padx=S['md'],pady=S['xs'])
    page.rotation_buttons=[];page.rotation_tooltips=[];page.rotation_images=[]
    for index,(step,title) in enumerate(((-90,'หมุนซ้าย 90° · กดซ้ำได้'),(90,'หมุนขวา 90° · กดซ้ำได้'))):
        images=(rotation_icon(step>0),rotation_icon(step>0,color='muted'))
        button=page.button(modes,'',lambda value=step:page.rotate_step(value),width=44,image=images[0])
        button.grid(row=0,column=index,padx=(0,S['xs']))
        page.rotation_buttons.append(button);page.rotation_images.append(images);page.controls.append(button)
        page.rotation_tooltips.append(Tooltip(button,title,page.font_small))
    page.angle_label=page.label(modes,'',font=page.font_small,color='muted',wraplength=180,justify='left')
    page.angle_label.grid(row=0,column=2,sticky='w')
    rail.grid_rowconfigure(1,weight=1)
    page.preview=PagePreview(rail,page.app)
    page.preview.configure(height=360)
    page.preview.grid_propagate(False)
    page.preview.grid(row=1,column=0,sticky='nsew',padx=S['xs'])
    page.suffix_entry=output_settings(page,rail,2,page.suffix,'ต่อท้ายชื่อไฟล์')
    page.names_button=page.button(rail,'ตรวจชื่อไฟล์ทั้งหมด…',page.show_names,width=290)
    page.names_button.grid(row=3,column=0,sticky='ew',padx=S['md'],pady=(0,S['sm']))
    page.controls.append(page.names_button)
    save_bar(page,'หมุนและบันทึก PDF ใหม่')
