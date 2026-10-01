"""Headless deletion planning; the original document is never modified."""
from pathlib import Path
from pdf_lover.core.document import DocumentError, inspect_document, validate_prefix
from pdf_lover.core.page_selection import selected_pages, PageSelectionError
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, export_pages


def build_plan(info, directory, prefix, expression, mode='single'):
    validate_prefix(prefix)
    if mode != 'single':
        raise DocumentError("ลบหน้าบันทึกเป็น PDF ใหม่หนึ่งไฟล์")
    try:
        removed = set(selected_pages(expression, info.page_count))
    except PageSelectionError as error:
        raise DocumentError(str(error)) from error
    pages = tuple(p for p in range(1, info.page_count+1) if p not in removed)
    if not pages:
        raise DocumentError("ลบทุกหน้าไม่ได้ · ต้องเหลืออย่างน้อยหนึ่งหน้า")
    plan = PagePlan(info, (PageOutput(Path(directory).expanduser().resolve()/f'{prefix}.pdf', pages),))
    validate_targets(plan)
    return plan


def delete_pdf(plan, progress=None):
    return export_pages(plan, progress)
