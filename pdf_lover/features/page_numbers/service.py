"""Headless vector overlays in visible CropBox coordinates; shared by preview/export."""
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
import pymupdf
from pdf_lover.core.document import DocumentError, signature, validate_prefix
from pdf_lover.core.page_selection import selected_pages, PageSelectionError
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, publish_staged, publication_error
from pdf_lover.core.cancellation import checkpoint

FONT_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'
POSITIONS = ('top-left', 'top-center', 'top-right', 'bottom-left', 'bottom-center', 'bottom-right')


@dataclass(frozen=True)
class NumberSettings:
    start: int = 1
    sequence: str = 'original'
    position: str = 'bottom-center'
    size: int = 12
    color: str = '#000000'
    format: str = 'number'
    thai_digits: bool = False

    def validate(self):
        if type(self.start) is not int or not 1 <= self.start <= 999999:
            raise DocumentError('เลขเริ่มต้นต้องเป็นจำนวนเต็ม 1–999999')
        if type(self.size) is not int or not 6 <= self.size <= 72:
            raise DocumentError('ขนาดตัวอักษรต้องเป็นจำนวนเต็ม 6–72 pt')
        if self.sequence not in ('original', 'selected') or self.position not in POSITIONS:
            raise DocumentError('เลือกวิธีนับเลขและตำแหน่งที่ถูกต้อง')
        if self.format not in ('number', 'page', 'total') or type(self.thai_digits) is not bool:
            raise DocumentError('เลือกรูปแบบหมายเลขที่ถูกต้อง')
        if not isinstance(self.color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', self.color):
            raise DocumentError('สีต้องเป็น #RRGGBB เช่น #000000')


@dataclass(frozen=True)
class NumberPlan:
    document: object
    outputs: tuple
    selected: tuple
    settings: NumberSettings


def label_for(settings, page, ordinal, count, selected_count):
    settings.validate()
    number = settings.start + (page - 1 if settings.sequence == 'original' else ordinal)
    # Denominator is a count, never the last printed number (start can exceed it).
    total = count if settings.sequence == 'original' else selected_count
    text = str(number) if settings.format == 'number' else f'หน้า {number}' if settings.format == 'page' else f'{number} / {total}'
    return text.translate(str.maketrans('0123456789', '๐๑๒๓๔๕๖๗๘๙')) if settings.thai_digits else text


def build_plan(info, directory, prefix, expression, settings):
    settings.validate()
    validate_prefix(prefix)
    try:
        pages = selected_pages(expression, info.page_count)
    except PageSelectionError as error:
        raise DocumentError(str(error)) from error
    plan = NumberPlan(info, (PageOutput(Path(directory).expanduser().resolve() / (prefix + '.pdf'), tuple(range(1, info.page_count + 1))),), pages, settings)
    validate_plan(plan)
    return plan


def validate_plan(plan):
    plan.settings.validate()
    if (len(plan.outputs) != 1 or not plan.selected or
            tuple(sorted(set(plan.selected))) != plan.selected or
            any(type(p) is not int or p < 1 or p > plan.document.page_count for p in plan.selected) or
            plan.outputs[0].pages != tuple(range(1, plan.document.page_count + 1))):
        raise DocumentError('เลือกหน้าตามลำดับเดิมอย่างน้อยหนึ่งหน้า')
    validate_targets(PagePlan(plan.document, plan.outputs))


def stamp_page(page, text, settings):
    """Compose one small vector PDF, then map it into unrotated CropBox coordinates.

    Story shapes Thai with the bundled OFL font. No system font is required.
    Rotation is counteracted by show_pdf_page so the displayed overlay stays upright.
    """
    settings.validate()
    width, height = page.rect.width, page.rect.height
    margin = 12
    box_height = settings.size * 2.4
    if width < 2 * margin + settings.size * len(text) or height < 2 * margin + box_height:
        # Conservative bound prevents clipping without silently shrinking typography.
        font = pymupdf.Font(fontfile=str(FONT_DIR / 'NotoSansThai.ttf'))
        if width < 2 * margin + font.text_length(text, fontsize=settings.size) or height < 2 * margin + box_height:
            raise DocumentError('หมายเลขไม่พอดีกับหน้าที่เลือก · ลดขนาดตัวอักษรหรือเปลี่ยนรูปแบบ')
    top, align = settings.position.split('-')
    y = margin if top == 'top' else height - margin - box_height
    css = f"@font-face {{font-family: NumberThai; src: url(NotoSansThai.ttf);}} * {{font-family: NumberThai; font-size: {settings.size}pt; color: {settings.color};}} p {{margin:0; text-align:{align};}}"
    with pymupdf.open() as overlay:
        sheet = overlay.new_page(width=width, height=height)
        spare, scale = sheet.insert_htmlbox(pymupdf.Rect(margin, y, width-margin, y+box_height), f'<p>{text}</p>', css=css, archive=pymupdf.Archive(str(FONT_DIR)), scale_low=1)
        if spare < 0 or scale != 1:
            raise DocumentError('หมายเลขไม่พอดีกับหน้าที่เลือก · ลดขนาดหรือเปลี่ยนรูปแบบ')
        target = page.rect * page.derotation_matrix
        rotation = page.rotation
        # PyMuPDF's rotated transformation_matrix omits CropBox offsets.
        # Insert with the unrotated matrix, restoring the page property in finally.
        page.set_rotation(0)
        try:
            page.show_pdf_page(target, overlay, 0, rotate=rotation, overlay=True)
        finally:
            page.set_rotation(rotation)


def number_pdf(plan, progress=None, cancel=None):
    checkpoint(cancel)
    validate_plan(plan)
    info, output = plan.document, plan.outputs[0]
    published = []
    try:
        if signature(info.path) != info.signature:
            raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่')
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-numbers-', dir=output.path.parent) as staging:
            temporary = Path(staging) / 'numbered.pdf'
            with pymupdf.open(info.path) as document:
                if document.needs_pass or document.page_count != info.page_count:
                    raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง')
                geometry = [(p.rotation, tuple(p.cropbox), tuple(p.mediabox)) for p in document]
                for ordinal, number in enumerate(plan.selected):
                    checkpoint(cancel)
                    text = label_for(plan.settings, number, ordinal, info.page_count, len(plan.selected))
                    stamp_page(document[number-1], text, plan.settings)
                    if progress and (ordinal % 20 == 0 or ordinal == len(plan.selected)-1):
                        progress(ordinal+1, len(plan.selected), output.path.name)
                checkpoint(cancel)
                # Deduplicate embedded font streams from the independently shaped labels.
                # This changes object numbers, never original content/quality.
                document.save(temporary, garbage=4, deflate=True)
            checkpoint(cancel)
            with pymupdf.open(temporary) as check:
                if check.page_count != info.page_count or [(p.rotation, tuple(p.cropbox), tuple(p.mediabox)) for p in check] != geometry:
                    raise DocumentError('ตรวจไฟล์ผลลัพธ์ไม่ผ่าน')
            if signature(info.path) != info.signature:
                raise DocumentError('ต้นฉบับเปลี่ยนระหว่างทำงาน')
            validate_plan(plan)
            publish_staged([(temporary, output.path, signature(temporary))], published, cancel)
        return (output.path,)
    except Exception as error:
        publication_error(published, error)
