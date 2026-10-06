"""Hallmark · document desk navigation. P5 H5 E4 S5 R5 V5.
Native navigation only; ToolPage/app retain ownership and busy guards.
"""
import customtkinter as ctk
from pdf_lover.catalog import TOOLS
from pdf_lover.ui.activity import ActivityIndicator
from pdf_lover.ui.theme import COLORS as C, SPACE as S


def masthead(page, title):
    app=page.app
    header=ctk.CTkFrame(page,fg_color=C['graphite'],corner_radius=0)
    header.grid(row=0,column=0,sticky='ew');header.grid_columnconfigure(1,weight=1)
    app.label(header,'PDF LoveR',font=app.font_bold,color='accent-ink').grid(row=0,column=0,padx=(S['xl'],S['xl']),pady=S['md'])
    app.label(header,title,font=app.font_title,color='accent-ink').grid(row=0,column=1,sticky='w',pady=S['md'])
    page.activity_indicator = ActivityIndicator(header, app.font_small)
    page.activity_indicator.grid(row=0, column=2, padx=S['sm'])
    tools={t.title:t.id for t in TOOLS if t.ready}
    def change_tool(text):
        menu.set('เปลี่ยนเครื่องมือ')
        app.show_tool(tools[text])
    menu=ctk.CTkOptionMenu(header,values=list(tools),font=app.font_small,dropdown_font=app.font_body,height=40,width=176,
        fg_color=C['graphite'],button_color=C['graphite'],button_hover_color=C['accent'],text_color=C['accent-ink'],
        dropdown_fg_color=C['surface'],dropdown_text_color=C['ink'],command=change_tool)
    page.tool_menu=menu
    menu.set('เปลี่ยนเครื่องมือ');menu.grid(row=0,column=4,padx=S['sm']);page.controls.append(menu)
    menu._canvas.configure(takefocus=1)
    menu._canvas.bind('<FocusIn>',lambda _:menu.configure(button_color=C['accent']))
    menu._canvas.bind('<FocusOut>',lambda _:menu.configure(button_color=C['graphite']))
    for key in ('<Return>','<space>','<Alt-Down>'):menu._canvas.bind(key,lambda _:menu._open_dropdown_menu())
    page.home_button=app.button(header,'หน้าแรก',app.show_home,width=104)
    page.home_button.grid(row=0,column=5,padx=(S['sm'],S['xl']),pady=S['sm']);page.controls.append(page.home_button)
    page.cancel_button=app.button(header,'ยกเลิก',page.request_cancel,width=88)
    page.cancel_button.configure(font=app.font_small)
    page.cancel_button.grid(row=0,column=3,padx=S['sm'])
    page.cancel_button.grid_remove()
    return header
