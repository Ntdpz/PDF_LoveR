"""PDF to Image engine; one page in memory, no Tk dependencies."""
from dataclasses import dataclass
import csv
import math
from pathlib import Path
import pymupdf
from PIL import Image, features
from pdf_lover.core.document import signature

FORMATS = {"PNG": "png", "JPG": "jpg", "WebP": "webp", "TIFF": "tiff"}
MAX_PIXELS = 40_000_000


@dataclass(frozen=True)
class ImageOptions:
    file_type: str = "PNG"
    width: int | None = None
    height: int | None = None
    max_bytes: int | None = None
    jpeg_quality: int = 95

    def validate(self):
        if self.file_type not in FORMATS:
            raise ValueError("ประเภทไฟล์ไม่รองรับ")
        for value in (self.width, self.height):
            if value is not None and (type(value) is not int or not 1 <= value <= 20000):
                raise ValueError("ขนาดภาพต้องเป็นจำนวนเต็ม 1–20000 พิกเซล")
        if self.max_bytes is not None and (type(self.max_bytes) is not int or self.max_bytes < 1):
            raise ValueError("เพดานขนาดไฟล์ต้องมากกว่า 0")
        if type(self.jpeg_quality) is not int or not 1 <= self.jpeg_quality <= 100:
            raise ValueError("คุณภาพ JPG ต้องอยู่ระหว่าง 1–100")
        if self.file_type == "WebP" and not features.check("webp"):
            raise ValueError("ระบบนี้ไม่มีตัวเข้ารหัส WebP")


def pixel_dimensions(page, dpi, options):
    """One dimension is exact; two dimensions define an aspect-preserving box."""
    width, height = page.rect.width, page.rect.height
    if options.width is not None or options.height is not None:
        scale = min(options.width / width if options.width else math.inf,
                    options.height / height if options.height else math.inf)
        result = (max(1, math.floor(width * scale + 1e-7)),
                  max(1, math.floor(height * scale + 1e-7)))
    else:
        result = (math.ceil(width * dpi / 72), math.ceil(height * dpi / 72))
    if result[0] * result[1] > MAX_PIXELS:
        raise ValueError("ภาพเกิน 40 ล้านพิกเซล · โปรดเลือกขนาดใหม่ (โปรแกรมไม่ลดให้เอง)")
    return result


def available_folder(parent: Path, name: str) -> Path:
    number = 1
    while True:
        candidate = parent / (name if number == 1 else f"{name}_{number}")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            number += 1


def convert_pdf(pdf_path: Path, output_root: Path, dpi: int, progress,
                options: ImageOptions | None = None, warning=None, *, pages=None, info=None) -> Path:
    options = options or ImageOptions()
    options.validate()
    if type(dpi) is not int or not 36 <= dpi <= 600:
        raise ValueError("DPI ไม่ถูกต้อง · ใส่จำนวนเต็มระหว่าง 36 ถึง 600")
    if info is not None and (Path(pdf_path).resolve() != info.path or signature(pdf_path) != info.signature):
        raise ValueError("ไฟล์เปลี่ยนหลังเลือกหน้า · เลือกหน้าใหม่ก่อนแปลง")
    with pymupdf.open(pdf_path) as document:
        if document.needs_pass:
            raise ValueError("PDF มีรหัสผ่าน · กรุณาปลดล็อกก่อนแปลง")
        if document.page_count == 0:
            raise ValueError("PDF ไม่มีหน้า")
        if not document.is_pdf:
            raise ValueError("ไฟล์นี้ไม่ใช่ PDF")
        if info is not None and document.page_count != info.page_count:
            raise ValueError("จำนวนหน้าเปลี่ยน · เลือกหน้าใหม่ก่อนแปลง")
        selected = range(1, document.page_count + 1) if pages is None else tuple(pages)
        previous = 0
        for number in selected:
            if type(number) is not int or not previous < number <= document.page_count:
                raise ValueError("หน้าที่เลือกต้องเรียงจากน้อยไปมาก ไม่ซ้ำ และอยู่ใน PDF")
            previous = number
        if not selected:
            raise ValueError("เลือกอย่างน้อยหนึ่งหน้า")
        if info is not None and signature(pdf_path) != info.signature:
            raise ValueError("ไฟล์เปลี่ยนหลังเลือกหน้า · เลือกหน้าใหม่ก่อนแปลง")
        output_folder = available_folder(output_root, pdf_path.stem)
        digits = max(3, len(str(document.page_count)))
        # Stream rows instead of retaining all results in RAM.
        with (output_folder / "image_report.csv").open("x", newline="", encoding="utf-8-sig") as report:
            writer = csv.writer(report)
            writer.writerow(("file", "width_px", "height_px", "bytes", "limit_bytes", "over_limit"))
            source_pages = enumerate(document, start=1) if pages is None else ((n, document[n - 1]) for n in selected)
            for done, (index, page) in enumerate(source_pages, start=1):
                size = pixel_dimensions(page, dpi, options)
                if options.width is not None or options.height is not None:
                    scale = max(size[0] / page.rect.width, size[1] / page.rect.height)
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False,
                                            colorspace=pymupdf.csRGB)
                else:
                    pixmap = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
                path = output_folder / f"{pdf_path.stem}_page_{index:0{digits}d}.{FORMATS[options.file_type]}"
                try:
                    # Preserve native PNG DPI export and its existing memory behavior.
                    if options.file_type == "PNG" and options.width is None and options.height is None:
                        pixmap.save(path)
                        actual_size = (pixmap.width, pixmap.height)
                    else:
                        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                        del pixmap
                        pixmap = None
                        try:
                            if image.size != size:
                                resized = image.resize(size, Image.Resampling.LANCZOS)
                                image.close()
                                image = resized
                            settings = {"PNG": {"compress_level": 9},
                                        "JPG": {"quality": options.jpeg_quality, "subsampling": 0, "optimize": True},
                                        "WebP": {"lossless": True, "quality": 100, "method": 4},
                                        "TIFF": {"compression": "tiff_deflate"}}[options.file_type]
                            with path.open("xb") as target:
                                image.save(target, format="JPEG" if options.file_type == "JPG" else options.file_type.upper(),
                                           dpi=(dpi, dpi), **settings)
                            actual_size = image.size
                        finally:
                            image.close()
                finally:
                    del pixmap
                byte_count = path.stat().st_size
                over = options.max_bytes is not None and byte_count > options.max_bytes
                writer.writerow((path.name, *actual_size, byte_count, options.max_bytes or "", over))
                if over and warning:
                    warning(path, byte_count, options.max_bytes)
                progress(done, len(selected))
    return output_folder
