"""Selected-page exports with staged, exclusive publication; no GUI imports."""
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

import pymupdf

from pdf_lover.core.document import DocumentInfo, DocumentError, inspect_document, signature, validate_prefix


@dataclass(frozen=True)
class PageOutput:
    path: Path
    pages: tuple


@dataclass(frozen=True)
class PagePlan:
    document: DocumentInfo
    outputs: tuple


def validate_targets(plan):
    if not plan.outputs:
        raise DocumentError("เลือกอย่างน้อยหนึ่งหน้าก่อนบันทึก")
    seen = set()
    previous = 0
    for output in plan.outputs:
        pages = output.pages
        if (not pages or any(type(p) is not int or p < 1 or p > plan.document.page_count for p in pages)
                or tuple(sorted(set(pages))) != tuple(pages) or pages[0] <= previous):
            raise DocumentError("แผนหน้าไม่ถูกต้อง · เลือกหน้าตามลำดับและไม่ซ้ำ")
        previous = pages[-1]
        target = output.path.resolve()
        if target.suffix.lower() != '.pdf' or target in seen:
            raise DocumentError("ชื่อไฟล์ผลลัพธ์ไม่ถูกต้องหรือซ้ำกัน")
        seen.add(target)
        if target == plan.document.path or (target.exists() and os.path.samefile(target, plan.document.path)):
            raise DocumentError("ปลายทางเป็นไฟล์ต้นฉบับ · เลือกชื่อใหม่")
        if os.path.lexists(output.path):
            raise DocumentError(f"ไฟล์มีอยู่แล้ว: {output.path.name} · เปลี่ยนชื่อหรือโฟลเดอร์")
        if not target.parent.is_dir():
            raise DocumentError("ไม่พบโฟลเดอร์ปลายทาง · เลือกโฟลเดอร์ที่มีอยู่")
        if target.parent != plan.outputs[0].path.resolve().parent:
            raise DocumentError("ชุดไฟล์ต้องอยู่ในโฟลเดอร์เดียวกัน")


def publish_exclusive(temporary, target):
    if os.name == 'nt':
        os.rename(temporary, target)
    else:
        os.link(temporary, target)


def export_pages(plan, progress=None):
    """Preserve retained-page links/widgets/annotations and rollback this job on failure."""
    validate_targets(plan)
    info = plan.document
    published = []
    try:
        if signature(info.path) != info.signature:
            raise DocumentError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่")
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-pages-', dir=plan.outputs[0].path.parent) as staging:
            staged = []
            with pymupdf.open(info.path) as source:
                if source.needs_pass or not source.is_pdf or source.page_count != info.page_count:
                    raise DocumentError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่")
                for index, output in enumerate(plan.outputs, 1):
                    temporary = Path(staging) / f'{index}.pdf'
                    with pymupdf.open() as result:
                        pages = output.pages
                        if pages[-1] - pages[0] + 1 == len(pages):
                            result.insert_pdf(source, from_page=pages[0]-1, to_page=pages[-1]-1,
                                              links=True, annots=True, widgets=True)
                        else:
                            # Copy once, then delete omitted pages. PyMuPDF remaps internal links
                            # across gaps and preserves form fields, annotations and rotations.
                            result.insert_pdf(source, links=True, annots=True, widgets=True)
                            keep = set(pages)
                            result.delete_pages([p-1 for p in range(1, info.page_count+1) if p not in keep])
                        mapping = {p: i for i, p in enumerate(pages, 1)}
                        toc, previous_level = [], 0
                        for level, title, page in source.get_toc():
                            if page in mapping:
                                previous_level = min(level, previous_level+1)
                                toc.append([previous_level, title, mapping[page]])
                        result.set_toc(toc)
                        result.set_metadata({**source.metadata, 'title':output.path.stem, 'creator':'PDF LoveR'})
                        result.save(temporary, garbage=3, deflate=True)
                    with pymupdf.open(temporary) as check:
                        if not check.is_pdf or check.page_count != len(pages):
                            raise DocumentError("ตรวจจำนวนหน้าผลลัพธ์ไม่ผ่าน · ยังไม่ได้บันทึก")
                    staged.append((temporary, output.path, signature(temporary)))
                    if progress:
                        progress(index, len(plan.outputs), output.path.name)
            if signature(info.path) != info.signature:
                raise DocumentError("ต้นฉบับเปลี่ยนระหว่างทำงาน · เลือกไฟล์ใหม่")
            validate_targets(plan)
            publish_staged(staged, published)
        return tuple(output.path for output in plan.outputs)
    except Exception as error:
        publication_error(published, error)


def publish_staged(staged, published):
    """Publish exclusively, tracking identities for rollback by the caller."""
    for temporary, target, identity in staged:
        publish_exclusive(temporary, target)
        published.append((target, identity))


def publication_error(published, error):
    """Rollback unchanged files owned by this job and raise an actionable error."""
    remaining = []
    for path, identity in reversed(published):
        try:
            if signature(path) == identity:
                path.unlink()
            else:
                remaining.append(path.name)
        except FileNotFoundError:
            pass
        except OSError:
            remaining.append(path.name)
    if remaining:
        raise DocumentError("บันทึกไม่ครบ · ยังมีไฟล์จากงานนี้: " + ', '.join(remaining)) from error
    if isinstance(error, DocumentError):
        raise
    if isinstance(error, FileExistsError):
        raise DocumentError("มีไฟล์ชื่อซ้ำระหว่างบันทึก · เก็บไฟล์เดิมไว้และคืนชุดงานนี้แล้ว") from error
    if isinstance(error, OSError):
        raise DocumentError("อ่านหรือบันทึก PDF ไม่ได้ · ตรวจพื้นที่ว่าง สิทธิ์โฟลเดอร์ และต้นฉบับ") from error
    raise DocumentError("สร้าง PDF ไม่สำเร็จ · ตรวจต้นฉบับแล้วลองอีกครั้ง") from error
