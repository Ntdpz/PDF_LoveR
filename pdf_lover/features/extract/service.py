"""Headless extraction planning and export."""
from pathlib import Path
from pdf_lover.core.document import DocumentError, inspect_document, validate_prefix
from pdf_lover.core.page_selection import selected_pages, PageSelectionError
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, export_pages


def build_plan(info, directory, prefix, expression, mode='single'):
    validate_prefix(prefix)
    if mode not in ('single', 'pages'):
        raise DocumentError("เลือกบันทึกเป็น PDF เดียว หรือหนึ่งไฟล์ต่อหน้า")
    try:
        pages = selected_pages(expression, info.page_count)
    except PageSelectionError as error:
        raise DocumentError(str(error)) from error
    folder = Path(directory).expanduser().resolve()
    width = max(3, len(str(info.page_count)))
    outputs = (PageOutput(folder/f'{prefix}.pdf', pages),) if mode == 'single' else tuple(
        PageOutput(folder/f'{prefix}_{index:0{width}d}_p{page:0{width}d}.pdf', (page,))
        for index, page in enumerate(pages, 1))
    plan = PagePlan(info, outputs)
    validate_targets(plan)
    return plan


def extract_pdf(plan, progress=None, cancel=None):
    return export_pages(plan, progress, cancel)
