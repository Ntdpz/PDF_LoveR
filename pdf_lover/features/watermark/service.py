"""Headless watermarks: visible rotated CropBox, native PDF content preserved."""
from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path
import html
import math
import re
import tempfile
import warnings
import pymupdf
from PIL import Image
from pdf_lover.core.document import DocumentError, signature, validate_prefix
from pdf_lover.core.page_selection import selected_pages, PageSelectionError
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, publish_staged, publication_error
from pdf_lover.core.cancellation import checkpoint
from pdf_lover.features.page_numbers.service import FONT_DIR

POSITIONS = ('top-left', 'top-center', 'top-right', 'center-left', 'center', 'center-right', 'bottom-left', 'bottom-center', 'bottom-right')
FONTS = ('Noto Sans Thai', 'serif')
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


def inspect_image(path):
    """Decode/verify once in the import worker; never retain full image in Tk/cache."""
    path = Path(path).expanduser().resolve()
    try:
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg') or path.stat().st_size > MAX_IMAGE_BYTES:
            raise DocumentError('ภาพต้องเป็น PNG/JPG ไม่เกิน 20 MiB')
        before = signature(path)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.format not in ('PNG', 'JPEG') or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise DocumentError('ภาพต้องเป็น PNG/JPG ไม่เกิน 16 ล้านพิกเซล')
                size = image.size
                image.verify()
            with Image.open(path) as image:
                image.load()
        if signature(path) != before:
            raise DocumentError('ภาพเปลี่ยนระหว่างตรวจ')
        return ImageInfo(path, before, size)
    except DocumentError:
        raise
    except Exception as error:
        raise DocumentError('อ่านภาพไม่ได้ · เลือก PNG/JPG ที่สมบูรณ์') from error


@dataclass(frozen=True)
class ImageInfo:
    path: Path
    signature: tuple
    size: tuple


@dataclass(frozen=True)
class WatermarkSettings:
    kind: str = 'text'
    text: str = 'สำเนา / COPY'
    font: str = 'Noto Sans Thai'
    size: float = 36
    color: str = '#808080'
    opacity: float = .3
    angle: float = 0
    position: str = 'center'
    image_width: float = 40
    image: object = None

    def validate(self):
        if self.kind not in ('text', 'image') or self.font not in FONTS or self.position not in POSITIONS:
            raise DocumentError('เลือกชนิด ฟอนต์ และตำแหน่งที่ถูกต้อง')
        for value, low, high, label in ((self.size,6,144,'ขนาดข้อความ 6–144 pt'), (self.opacity,0,1,'ความทึบ 0–100%'), (self.angle,-180,180,'มุม −180 ถึง 180°'), (self.image_width,1,100,'ความกว้างภาพ 1–100%')):
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not low <= value <= high:
                raise DocumentError(label)
        if not isinstance(self.color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',self.color):
            raise DocumentError('สีต้องเป็น #RRGGBB')
        if self.kind == 'text' and (not isinstance(self.text,str) or not self.text.strip() or len(self.text)>500 or any(ord(c)<32 for c in self.text)):
            raise DocumentError('ข้อความหนึ่งบรรทัด 1–500 ตัวอักษร ไม่ใช้ control characters')
        if self.kind == 'image' and not isinstance(self.image,ImageInfo):
            raise DocumentError('เลือกและตรวจภาพ PNG/JPG ก่อนเริ่ม')


@dataclass(frozen=True)
class WatermarkPlan:
    document: object
    outputs: tuple
    selected: tuple
    settings: WatermarkSettings


def build_plan(info, directory, prefix, expression, settings):
    settings.validate()
    validate_prefix(prefix)
    try:
        pages = selected_pages(expression, info.page_count)
    except PageSelectionError as error:
        raise DocumentError(str(error)) from error
    plan = WatermarkPlan(info,(PageOutput(Path(directory).expanduser().resolve()/(prefix+'.pdf'),tuple(range(1,info.page_count+1))),),pages,settings)
    validate_plan(plan)
    return plan


def validate_plan(plan):
    plan.settings.validate()
    if (len(plan.outputs)!=1 or not plan.selected or tuple(sorted(set(plan.selected)))!=plan.selected or any(type(p) is not int or not 1<=p<=plan.document.page_count for p in plan.selected) or plan.outputs[0].pages!=tuple(range(1,plan.document.page_count+1))):
        raise DocumentError('เลือกหน้าตามลำดับเดิมอย่างน้อยหนึ่งหน้า')
    validate_targets(PagePlan(plan.document,plan.outputs))
    if plan.settings.kind=='image':
        try:
            current=signature(plan.settings.image.path)
        except OSError as error:
            raise DocumentError('อ่านภาพไม่ได้ · เลือกภาพใหม่') from error
        if current!=plan.settings.image.signature:
            raise DocumentError('ภาพเปลี่ยนหลังตรวจ · เลือกภาพใหม่')


class PreparedWatermarks:
    """At most eight small PDF overlays; output grafting reuses identical font/image objects."""
    LIMIT = 8

    def __init__(self):
        self.items = OrderedDict()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        for overlay in self.items.values():
            overlay.close()
        self.items.clear()

    def get(self, width, height, settings):
        key = (width, height, settings)
        overlay = self.items.pop(key, None)
        if overlay is None:
            overlay = _compose_overlay(width, height, settings)
        self.items[key] = overlay
        limit = 2 if settings.kind == 'image' else self.LIMIT
        if len(self.items) > limit:
            self.items.popitem(last=False)[1].close()
        return overlay


def _compose_overlay(width, height, settings):
    settings.validate()
    overlay=pymupdf.open()
    try:
        with pymupdf.open() as content:
            if settings.kind=='text':
                font=pymupdf.Font(fontfile=str(FONT_DIR/'NotoSansThai.ttf'))
                # Story calculates exact shaped bounds, including the selected family.
                css=f"@font-face {{font-family: WatermarkThai; src:url(NotoSansThai.ttf);}} * {{font-family:{'WatermarkThai' if settings.font=='Noto Sans Thai' else 'serif, WatermarkThai'};font-size:{settings.size}pt;color:{settings.color};}} p {{margin:0;white-space:nowrap;}}"
                w=max(font.text_length(settings.text,fontsize=settings.size),settings.size)+settings.size
                if settings.font=='serif':
                    w=max(w,pymupdf.Font('tiro').text_length(settings.text,fontsize=settings.size)+settings.size)
                h=settings.size*2.4
                sheet=content.new_page(width=w,height=h)
                spare,scale=sheet.insert_htmlbox(sheet.rect,f'<p>{html.escape(settings.text)}</p>',css=css,archive=pymupdf.Archive(str(FONT_DIR)),scale_low=1,opacity=settings.opacity)
                if spare<0 or scale!=1:
                    raise DocumentError('ข้อความไม่พอดี · ลดขนาดหรือข้อความ')
            else:
                image=settings.image
                if signature(image.path)!=image.signature:
                    raise DocumentError('ภาพเปลี่ยนหลังตรวจ · เลือกภาพใหม่')
                w=width*settings.image_width/100
                h=w*image.size[1]/image.size[0]
                sheet=content.new_page(width=w,height=h)
                sheet.insert_image(sheet.rect,filename=str(image.path),keep_proportion=True)
                # Apply group opacity without flattening the image or its alpha mask.
                alpha=content.get_new_xref()
                content.update_object(alpha,f'<< /Type /ExtGState /ca {settings.opacity} /CA {settings.opacity} >>')
                resources=content.xref_get_key(sheet.xref,'Resources')[1]
                resource_xref=int(resources.split()[0])
                content.xref_set_key(resource_xref,'ExtGState',f'<< /WMAlpha {alpha} 0 R >>')
                streams=sheet.get_contents()
                for xref in streams:
                    content.update_stream(xref,b'q /WMAlpha gs\n'+content.xref_stream(xref)+b'\nQ')
            radians=math.radians(settings.angle)
            bw=abs(w*math.cos(radians))+abs(h*math.sin(radians))
            bh=abs(w*math.sin(radians))+abs(h*math.cos(radians))
            if bw>width-24 or bh>height-24:
                raise DocumentError('ลายน้ำหลังหมุนไม่พอดีขอบ 12 pt · ลดขนาด/มุม/ความกว้าง')
            horizontal=settings.position.split('-')[-1] if '-' in settings.position else 'center'
            vertical=settings.position.split('-')[0] if '-' in settings.position else 'center'
            x=12 if horizontal=='left' else width-12-bw if horizontal=='right' else (width-bw)/2
            y=12 if vertical=='top' else height-12-bh if vertical=='bottom' else (height-bh)/2
            canvas=overlay.new_page(width=width,height=height)
            # Reopen the small stamp to avoid cached PNG premultiplication rounding
            # differing from the saved PDF by one channel level. Never serialize the source PDF.
            with pymupdf.open(stream=content.tobytes(),filetype='pdf') as normalized:
                canvas.show_pdf_page(pymupdf.Rect(x,y,x+bw,y+bh),normalized,0,rotate=settings.angle,keep_proportion=True)
        return overlay
    except Exception:
        overlay.close()
        raise


def stamp_page(page, settings, prepared=None):
    """Position an overlay in visible rotated CropBox; shared by preview and export.

    Image width is a percentage of visible width before rotation. Positive angle
    is counterclockwise. Rotated bounds must fit the 12pt margin; never shrink.
    """
    settings.validate()
    if settings.kind == 'image' and signature(settings.image.path) != settings.image.signature:
        raise DocumentError('ภาพเปลี่ยนหลังตรวจ · เลือกภาพใหม่')
    if prepared is None:
        with PreparedWatermarks() as cache:
            return stamp_page(page, settings, cache)
    overlay=prepared.get(page.rect.width,page.rect.height,settings)
    target=page.rect*page.derotation_matrix
    rotation=page.rotation
    page.set_rotation(0)
    try:
        page.show_pdf_page(target,overlay,0,rotate=rotation,overlay=True)
    finally:
        page.set_rotation(rotation)


def watermark_pdf(plan, progress=None, cancel=None):
    checkpoint(cancel)
    validate_plan(plan)
    info, output = plan.document, plan.outputs[0]
    published = []
    try:
        if signature(info.path) != info.signature:
            raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่')
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-watermark-', dir=output.path.parent) as staging:
            temporary = Path(staging) / 'watermarked.pdf'
            with pymupdf.open(info.path) as document, PreparedWatermarks() as prepared:
                if document.needs_pass or document.page_count != info.page_count:
                    raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง')
                geometry = [(p.rotation, tuple(p.cropbox), tuple(p.mediabox)) for p in document]
                for ordinal, number in enumerate(plan.selected):
                    checkpoint(cancel)
                    stamp_page(document[number-1], plan.settings, prepared)
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
