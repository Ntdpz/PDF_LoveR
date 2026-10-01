"""ลบหน้าออก: shared selection workbench and feature-specific headless service."""
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.features.delete_pages.service import build_plan, delete_pdf


class DeletePagesPage(SelectionPage):
    TITLE = "ลบหน้าออก"
    SUFFIX = "_ลบหน้า"
    DELETE = True
    SAVE_LABEL = "ลบหน้าและบันทึกไฟล์ใหม่"
    build_plan = staticmethod(build_plan)
    export = staticmethod(delete_pdf)
