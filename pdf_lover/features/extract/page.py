"""แยกหน้า: shared selection workbench and feature-specific headless service."""
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.features.extract.service import build_plan, extract_pdf


class ExtractPage(SelectionPage):
    TITLE = "แยกหน้า"
    SUFFIX = "_เลือกหน้า"
    DELETE = False
    SAVE_LABEL = "บันทึกหน้าที่เลือก"
    build_plan = staticmethod(build_plan)
    export = staticmethod(extract_pdf)
