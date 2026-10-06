"""Order workbench with the existing worker, cancellation and publication lifecycle."""
from pdf_lover.features.selection_page import SelectionPage
from pdf_lover.ui.page_order import PageOrder
from pdf_lover.features.organize.service import build_plan, reorder_pdf


class OrganizePage(SelectionPage):
    TITLE = 'จัดเรียงหน้า PDF'
    SUFFIX = '_จัดเรียง'
    SAVE_LABEL = 'บันทึก PDF ตามลำดับใหม่'
    ORDER = True
    EVENT_LIMIT = 32
    SELECTOR_CLASS = PageOrder
    export = staticmethod(reorder_pdf)

    def build_plan(self, info, directory, prefix, expression, mode):
        return build_plan(info, directory, prefix, self.selector.order)
