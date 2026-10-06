"""Reorder the original page objects without rasterization or GUI imports."""
from pathlib import Path
import tempfile
import pymupdf
from pdf_lover.core.document import DocumentError, signature, validate_prefix
from pdf_lover.core.cancellation import checkpoint
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, publish_staged, publication_error


def validate_order(pages, count):
    if len(pages) != count or any(type(p) is not int for p in pages) or set(pages) != set(range(1, count + 1)):
        raise DocumentError("ลำดับต้องมีทุกหน้าเพียงครั้งเดียว · ไม่มีหน้าซ้ำหรือขาด")


def validate_plan(plan):
    if len(plan.outputs) != 1:
        raise DocumentError("จัดเรียงเป็น PDF ใหม่หนึ่งไฟล์")
    validate_order(plan.outputs[0].pages, plan.document.page_count)
    # Reuse path/alias/race guards with an ascending view; the export order is immutable.
    validate_targets(PagePlan(plan.document, (PageOutput(plan.outputs[0].path, tuple(range(1, plan.document.page_count + 1))),)))


def build_plan(info, directory, prefix, order, mode='single'):
    validate_prefix(prefix)
    plan = PagePlan(info, (PageOutput(Path(directory).expanduser().resolve() / f'{prefix}.pdf', tuple(order)),))
    validate_plan(plan)
    return plan


def reorder_pdf(plan, progress=None, cancel=None):
    checkpoint(cancel)
    validate_plan(plan)
    info, output = plan.document, plan.outputs[0]
    published = []
    try:
        if signature(info.path) != info.signature:
            raise DocumentError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่")
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-order-', dir=output.path.parent) as staging:
            temporary = Path(staging) / 'ordered.pdf'
            with pymupdf.open(info.path) as document:
                if document.needs_pass or document.page_count != info.page_count:
                    raise DocumentError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง")
                # Original xrefs retain widgets, annotations and direct link destinations.
                expected = [document.page_xref(p - 1) for p in output.pages]
                toc = document.get_toc(simple=False)
                mapping = {p: i for i, p in enumerate(output.pages, 1)}
                current = list(range(1, info.page_count + 1))
                for position, original in enumerate(output.pages):
                    checkpoint(cancel)
                    old = current.index(original, position)
                    if old != position:
                        document.move_page(old, position)
                        current.insert(position, current.pop(old))
                    if progress and (position % 20 == 0 or position == info.page_count - 1):
                        progress(position + 1, info.page_count, output.path.name)
                for entry in toc:
                    if entry[2] in mapping:
                        entry[2] = mapping[entry[2]]
                        if entry[3].get('kind') == pymupdf.LINK_GOTO:
                            entry[3]['page'] = entry[2] - 1
                document.set_toc(toc)
                checkpoint(cancel)
                if [document.page_xref(i) for i in range(document.page_count)] != expected:
                    raise DocumentError("ตรวจลำดับหน้าไม่ผ่าน · ยังไม่บันทึก")
                document.save(temporary, garbage=0, deflate=True)
            checkpoint(cancel)
            with pymupdf.open(temporary) as check:
                if check.page_count != info.page_count or [check.page_xref(i) for i in range(check.page_count)] != expected:
                    raise DocumentError("ตรวจลำดับไฟล์ใหม่ไม่ผ่าน")
            if signature(info.path) != info.signature:
                raise DocumentError("ต้นฉบับเปลี่ยนระหว่างทำงาน")
            validate_plan(plan)
            publish_staged([(temporary, output.path, signature(temporary))], published, cancel)
        return (output.path,)
    except Exception as error:
        publication_error(published, error)
