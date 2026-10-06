"""Split planning and staged, exclusive publication. No GUI imports."""
from pdf_lover.core.cancellation import checkpoint
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

import pymupdf

from pdf_lover.core.page_selection import split_groups, PageSelectionError


from pdf_lover.core.document import (DocumentError as SplitError, DocumentInfo,
                                     inspect_document, signature, validate_prefix)

@dataclass(frozen=True)
class SplitOutput:
    path: Path
    pages: range


@dataclass(frozen=True)
class SplitPlan:
    document: DocumentInfo
    outputs: tuple



def build_plan(info, directory, prefix, mode="pages", expression="", chunk_size=1):
    validate_prefix(prefix)
    folder = Path(directory).expanduser().resolve()
    try:
        groups = split_groups(info.page_count, mode, expression, chunk_size)
    except PageSelectionError as error:
        raise SplitError(str(error)) from error
    width = max(3, len(str(info.page_count)))
    outputs = tuple(SplitOutput(folder / (f"{prefix}_{index:0{width}d}_"
                                          f"p{group.start:0{width}d}-{group.stop - 1:0{width}d}.pdf"), group)
                    for index, group in enumerate(groups, 1))
    plan = SplitPlan(info, outputs)
    validate_targets(plan)
    return plan


def validate_targets(plan):
    if not plan.outputs:
        raise SplitError("ยังไม่ได้เลือกหน้าที่ต้องการแยก")
    seen = set()
    previous = 0
    for output in plan.outputs:
        target = output.path.resolve()
        pages = output.pages
        if (not isinstance(pages, range) or pages.step != 1 or not pages
                or pages.start <= previous or pages.start < 1 or pages.stop - 1 > plan.document.page_count):
            raise SplitError("แผนช่วงหน้าไม่ถูกต้อง · เลือกหน้าตามลำดับและไม่ซ้ำ")
        previous = pages.stop - 1
        if target.suffix.lower() != ".pdf" or target in seen:
            raise SplitError("ชื่อไฟล์ผลลัพธ์ไม่ถูกต้องหรือซ้ำกัน")
        seen.add(target)
        if target == plan.document.path or (target.exists() and plan.document.path.exists()
                                            and os.path.samefile(target, plan.document.path)):
            raise SplitError("ปลายทางเป็นไฟล์ต้นฉบับ · เลือกชื่อใหม่")
        if os.path.lexists(output.path):
            raise SplitError(f"ไฟล์มีอยู่แล้ว: {output.path.name} · เปลี่ยนชื่อชุดไฟล์หรือโฟลเดอร์")
        if not target.parent.is_dir():
            raise SplitError("ไม่พบโฟลเดอร์ปลายทาง · เลือกโฟลเดอร์ที่มีอยู่")


def publish_exclusive(temporary, target):
    if os.name == "nt":
        os.rename(temporary, target)
    else:
        os.link(temporary, target)


def split_pdf(plan, progress=None, cancel=None):
    """Write and verify every file before publishing any; rollback this job on failure."""
    checkpoint(cancel)
    validate_targets(plan)
    info = plan.document
    published = []
    try:
        if signature(info.path) != info.signature:
            raise SplitError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่ก่อนแยก")
        with tempfile.TemporaryDirectory(prefix=".pdf-lover-split-", dir=plan.outputs[0].path.parent) as staging:
            staged = []
            with pymupdf.open(info.path) as source:
                if source.needs_pass or not source.is_pdf or source.page_count != info.page_count:
                    raise SplitError("ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่")
                for index, output in enumerate(plan.outputs, 1):
                    checkpoint(cancel)
                    temporary = Path(staging) / f"{index}.pdf"
                    with pymupdf.open() as result:
                        result.insert_pdf(source, from_page=output.pages.start - 1, to_page=output.pages.stop - 2,
                                          links=True, annots=True, widgets=True)
                        # Keep bookmarks whose destinations survive, with valid levels.
                        toc = []
                        level_before = 0
                        for level, title, page in source.get_toc():
                            if page in output.pages:
                                level_before = min(level, level_before + 1)
                                toc.append([level_before, title, page - output.pages.start + 1])
                        result.set_toc(toc)
                        result.set_metadata({**source.metadata, "title": output.path.stem, "creator": "PDF LoveR"})
                        result.save(temporary, garbage=3, deflate=True)
                    with pymupdf.open(temporary) as check:
                        if not check.is_pdf or check.page_count != len(output.pages):
                            raise SplitError("ตรวจจำนวนหน้าผลลัพธ์ไม่ผ่าน · ยังไม่ได้บันทึกชุดไฟล์")
                    staged.append((temporary, output.path, signature(temporary)))
                    if progress:
                        progress(index, len(plan.outputs), output.path.name)
            if signature(info.path) != info.signature:
                raise SplitError("ต้นฉบับเปลี่ยนระหว่างทำงาน · เลือกไฟล์ใหม่")
            checkpoint(cancel)
            validate_targets(plan)
            for temporary, target, identity in staged:
                checkpoint(cancel)
                publish_exclusive(temporary, target)
                published.append((target, identity))
            checkpoint(cancel)
        return tuple(output.path for output in plan.outputs)
    except Exception as error:
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
            raise SplitError("บันทึกไม่ครบ · ยังมีไฟล์จากงานนี้: " + ", ".join(remaining)) from error
        if isinstance(error, SplitError):
            raise
        if isinstance(error, FileExistsError):
            raise SplitError("มีไฟล์ชื่อซ้ำระหว่างบันทึก · เก็บไฟล์เดิมไว้และคืนชุดงานนี้แล้ว") from error
        if isinstance(error, OSError):
            raise SplitError("อ่านหรือบันทึก PDF ไม่ได้ · ตรวจพื้นที่ว่าง สิทธิ์โฟลเดอร์ และต้นฉบับ") from error
        raise SplitError("แยก PDF ไม่สำเร็จ · ตรวจต้นฉบับแล้วลองอีกครั้ง") from error
