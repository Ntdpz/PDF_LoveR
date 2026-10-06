"""Lossless page concatenation with exclusive publication of the output file."""
from pdf_lover.core.cancellation import checkpoint
from pathlib import Path
import os
import tempfile

import pymupdf


class MergeError(ValueError):
    """An actionable PDF validation error for the native tool."""


def inspect_pdf(path):
    path = Path(path).resolve()
    try:
        with pymupdf.open(path) as document:
            if not document.is_pdf:
                raise MergeError("ไฟล์นี้ไม่ใช่ PDF")
            if document.needs_pass:
                raise MergeError("PDF มีรหัสผ่าน · รุ่นนี้ยังไม่รองรับ")
            if not document.page_count:
                raise MergeError("PDF ไม่มีหน้า")
            return document.page_count
    except MergeError as error:
        raise MergeError(f"{path.name}: {error}") from error
    except Exception as error:
        raise MergeError(f"{path.name}: เปิด PDF ไม่ได้ · ตรวจว่าไฟล์เปิดอ่านได้") from error


def merge_pdfs(paths, destination, progress=None, cancel=None):
    """Merge in list order; never replace an existing file or any input.

    The temporary PDF is fully written and reopened before publication. Windows
    rename refuses an existing destination; POSIX uses an exclusive hard link.
    """
    checkpoint(cancel)
    sources = [Path(path).resolve() for path in paths]
    target = Path(destination).expanduser().resolve()
    if len(sources) < 2:
        raise MergeError("เพิ่ม PDF อย่างน้อย 2 ไฟล์ก่อนรวม")
    if target.suffix.lower() != ".pdf":
        raise MergeError("ชื่อไฟล์ผลลัพธ์ต้องลงท้ายด้วย .pdf")
    if target in sources or (target.exists() and any(os.path.samefile(target, path) for path in sources if path.exists())):
        raise MergeError("ปลายทางเป็นไฟล์ต้นฉบับ · เลือกชื่อไฟล์ใหม่")
    if target.exists():
        raise MergeError("ชื่อไฟล์นี้มีอยู่แล้ว · เลือกชื่อใหม่เพื่อเก็บไฟล์เดิมไว้")
    if not target.parent.is_dir():
        raise MergeError("ไม่พบโฟลเดอร์ปลายทาง · เลือกโฟลเดอร์ที่มีอยู่")
    counts = []
    for path in sources:
        checkpoint(cancel)
        counts.append(inspect_pdf(path))
    checkpoint(cancel)
    total = sum(counts)
    temporary = None
    try:
        with pymupdf.open() as result:
            bookmarks = []
            for index, path in enumerate(sources):
                checkpoint(cancel)
                offset = result.page_count
                # Open again in case a source changed after preflight inspection.
                with pymupdf.open(path) as source:
                    if source.needs_pass or not source.is_pdf or source.page_count != counts[index]:
                        raise MergeError(f"{path.name}: ไฟล์เปลี่ยนระหว่างทำงาน · เพิ่มไฟล์ใหม่แล้วลองอีกครั้ง")
                    result.insert_pdf(source, links=True, annots=True, widgets=True, join_duplicates=False)
                    bookmarks.append([1, path.stem, offset + 1])
                    previous_level = 1
                    for level, title, page in source.get_toc():
                        if 1 <= page <= source.page_count:
                            adjusted_level = min(level + 1, previous_level + 1)
                            bookmarks.append([adjusted_level, title, offset + page])
                            previous_level = adjusted_level
                if progress:
                    progress(index + 1, len(sources), result.page_count, total, path.name)
            checkpoint(cancel)
            result.set_toc(bookmarks)
            result.set_metadata({"title": target.stem, "creator": "PDF LoveR"})
            handle = tempfile.NamedTemporaryFile(prefix=".pdf-lover-", suffix=".pdf", dir=target.parent, delete=False)
            temporary = Path(handle.name)
            handle.close()
            result.save(temporary, garbage=3, deflate=True)
        with pymupdf.open(temporary) as check:
            if check.page_count != total:
                raise MergeError("ตรวจผลลัพธ์ไม่ผ่าน · ยังไม่ได้บันทึกไฟล์ปลายทาง")
        checkpoint(cancel)
        if os.name == "nt":
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
        return total
    except FileExistsError as error:
        raise MergeError("ชื่อไฟล์ปลายทางมีอยู่แล้ว · เลือกชื่อใหม่") from error
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
