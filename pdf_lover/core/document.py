"""Shared PDF inspection and Windows file-name validation; no GUI imports."""
from dataclasses import dataclass
from pathlib import Path
import re
import pymupdf

class DocumentError(ValueError):
    pass

@dataclass(frozen=True)
class DocumentInfo:
    path: Path
    page_count: int
    signature: tuple

def signature(path):
    stat = Path(path).stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def inspect_document(path):
    path = Path(path).expanduser().resolve()
    try:
        before = signature(path)
        with pymupdf.open(path) as document:
            if not document.is_pdf:
                raise DocumentError("ไฟล์นี้ไม่ใช่ PDF")
            if document.needs_pass:
                raise DocumentError("PDF มีรหัสผ่าน · รุ่นนี้ยังไม่รองรับ")
            if document.page_count < 1:
                raise DocumentError("PDF ไม่มีหน้า")
            count = document.page_count
        if signature(path) != before:
            raise DocumentError("ไฟล์เปลี่ยนระหว่างอ่าน · เลือกไฟล์ใหม่")
        return DocumentInfo(path, count, before)
    except DocumentError:
        raise
    except Exception as error:
        raise DocumentError(f"{path.name}: เปิด PDF ไม่ได้ · ตรวจว่าไฟล์เปิดอ่านได้") from error


def validate_prefix(prefix):
    if not prefix or prefix != prefix.strip() or len(prefix) > 100:
        raise DocumentError("ระบุชื่อชุดไฟล์ 1–100 ตัวอักษร โดยไม่มีช่องว่างต้นหรือท้าย")
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', prefix) or prefix.endswith("."):
        raise DocumentError("ชื่อชุดไฟล์มีอักขระที่ Windows ใช้ไม่ได้")
    if prefix.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                                         *(f"COM{i}" for i in "123456789¹²³"),
                                         *(f"LPT{i}" for i in "123456789¹²³")}:
        raise DocumentError("ชื่อชุดไฟล์เป็นชื่อสงวนของ Windows · เลือกชื่อใหม่")
