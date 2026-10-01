"""One-based, ascending page groups shared by page manipulation tools."""
import re


class PageSelectionError(ValueError):
    pass


def parse_page_groups(expression, page_count):
    """Each comma-separated item is a group; reject overlap and reordering.

    Returning ranges keeps plans compact even for large documents. Callers use
    one-based numbers until the PDF engine boundary.
    """
    if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1:
        raise PageSelectionError("จำนวนหน้า PDF ต้องมากกว่า 0")
    if not expression.strip():
        raise PageSelectionError("ระบุหน้าที่ต้องการ เช่น 1-3,5,8-10")
    groups = []
    previous = 0
    for item in expression.split(","):
        match = re.fullmatch(r"\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?", item)
        if not match or len(item) > 40:
            raise PageSelectionError("รูปแบบช่วงหน้าไม่ถูกต้อง · ใช้ 1-3,5,8-10")
        first, last = int(match[1]), int(match[2] or match[1])
        if first < 1 or last > page_count:
            raise PageSelectionError(f"เลือกได้เฉพาะหน้า 1–{page_count}")
        if last < first:
            raise PageSelectionError("ช่วงหน้าต้องเรียงจากน้อยไปมาก เช่น 1-3")
        if first <= previous:
            raise PageSelectionError("หน้าซ้ำหรือสลับลำดับ · เรียงช่วงจากน้อยไปมากและไม่ซ้ำกัน")
        groups.append(range(first, last + 1))
        previous = last
    return tuple(groups)


def selected_pages(expression, page_count):
    return tuple(page for group in parse_page_groups(expression, page_count) for page in group)


def format_pages(pages):
    """Format a sorted unique selection back into editable contiguous ranges."""
    ordered = sorted(set(pages))
    parts = []
    for page in ordered:
        if not parts or page != parts[-1][1] + 1:
            parts.append([page, page])
        else:
            parts[-1][1] = page
    return ",".join(str(a) if a == b else f"{a}-{b}" for a, b in parts)


def split_groups(page_count, mode, expression="", chunk_size=1):
    if not isinstance(page_count, int) or isinstance(page_count, bool) or page_count < 1:
        raise PageSelectionError("จำนวนหน้า PDF ต้องมากกว่า 0")
    if mode == "ranges":
        return parse_page_groups(expression, page_count)
    if mode == "pages":
        chunk_size = 1
    elif mode != "chunks":
        raise PageSelectionError("เลือกวิธีแยก PDF ที่รองรับ")
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or not 1 <= chunk_size <= page_count:
        raise PageSelectionError(f"จำนวนหน้าต่อไฟล์ต้องเป็นจำนวนเต็ม 1–{page_count}")
    return tuple(range(first, min(first + chunk_size, page_count + 1))
                 for first in range(1, page_count + 1, chunk_size))
