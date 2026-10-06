"""Headless relative rotation, batch planning and staged exclusive publication."""
from pdf_lover.core.cancellation import checkpoint
from dataclasses import dataclass
from pathlib import Path
import tempfile
import pymupdf
from pdf_lover.core.document import DocumentError, inspect_document, signature, validate_prefix
from pdf_lover.core.page_selection import selected_pages, PageSelectionError
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, publish_staged, publication_error


@dataclass(frozen=True)
class RotationJob:
    info: object
    selected: tuple
    output: PageOutput


@dataclass(frozen=True)
class RotationPlan:
    jobs: tuple
    angle: int


def build_plan(documents, directory, suffix='_หมุน', angle=90, expressions=None):
    if type(angle) is not int or angle not in (90,180,270):
        raise DocumentError('เลือกมุมหมุน 90, 180 หรือ 270 องศา')
    if not documents:
        raise DocumentError('เพิ่ม PDF อย่างน้อยหนึ่งไฟล์')
    if len(suffix)>40 or suffix!=suffix.strip():
        raise DocumentError('ข้อความต่อท้ายชื่อไม่เกิน 40 ตัวอักษร ไม่มีช่องว่างต้นหรือท้าย')
    folder=Path(directory).expanduser().resolve()
    expressions={} if expressions is None else expressions
    jobs=[];names=set();sources=set()
    for info in documents:
        if info.path in sources:
            raise DocumentError('มีเอกสารซ้ำในชุดงาน · นำไฟล์ซ้ำออก')
        sources.add(info.path)
        try:
            selected=selected_pages(expressions.get(info.path,f'1-{info.page_count}'),info.page_count)
        except PageSelectionError as error:
            raise DocumentError(f'{info.path.name}: {error}') from error
        prefix=info.path.stem[:100-len(suffix)]+suffix
        validate_prefix(prefix)
        name=prefix+'.pdf';index=2
        while name.casefold() in names:
            tail=f'_{index:03d}';name=prefix[:100-len(tail)]+tail+'.pdf';index+=1
        names.add(name.casefold())
        jobs.append(RotationJob(info,selected,PageOutput(folder/name,tuple(range(1,info.page_count+1)))))
    plan=RotationPlan(tuple(jobs),angle)
    validate_plan(plan)
    return plan


def validate_plan(plan, check_source=False):
    if type(plan.angle) is not int or plan.angle not in (90,180,270) or not plan.jobs:
        raise DocumentError('แผนหมุน PDF ไม่ถูกต้อง')
    targets=set();sources={j.info.path for j in plan.jobs}
    for job in plan.jobs:
        if (not job.selected or any(type(p) is not int or p<1 or p>job.info.page_count for p in job.selected)
                or tuple(sorted(set(job.selected)))!=job.selected
                or job.output.pages!=tuple(range(1,job.info.page_count+1))):
            raise DocumentError('แผนหน้าไม่ถูกต้อง · หมุนโดยเก็บทุกหน้าตามลำดับเดิม')
        target=job.output.path.resolve()
        if target in targets or target in sources:
            raise DocumentError('ชื่อไฟล์ผลลัพธ์ซ้ำหรือเป็นต้นฉบับ · เปลี่ยนชื่อหรือโฟลเดอร์')
        targets.add(target)
        validate_targets(PagePlan(job.info,(job.output,)))
        if target.parent!=plan.jobs[0].output.path.resolve().parent:
            raise DocumentError('ชุดไฟล์ต้องอยู่ในโฟลเดอร์เดียวกัน')
        if check_source and signature(job.info.path)!=job.info.signature:
            raise DocumentError(f'{job.info.path.name}: ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่')


def rotate_pdf(plan, progress=None, cancel=None):
    checkpoint(cancel)
    published=[]
    try:
        validate_plan(plan,check_source=True)
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-rotate-',dir=plan.jobs[0].output.path.parent) as staging:
            staged=[]
            for index,job in enumerate(plan.jobs,1):
                checkpoint(cancel)
                temporary=Path(staging)/f'{index}.pdf'
                with pymupdf.open(job.info.path) as document:
                    if document.needs_pass or not document.is_pdf or document.page_count!=job.info.page_count:
                        raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่')
                    expected=[p.rotation for p in document]
                    for number in job.selected:
                        checkpoint(cancel)
                        page=document[number-1]
                        expected[number-1]=(page.rotation+plan.angle)%360
                        page.set_rotation(expected[number-1])
                    document.save(temporary,garbage=3,deflate=True)
                with pymupdf.open(temporary) as result:
                    if result.page_count!=job.info.page_count or [p.rotation for p in result]!=expected:
                        raise DocumentError('ตรวจจำนวนหน้าและมุมหมุนไม่ผ่าน · ยังไม่ได้บันทึกชุดไฟล์')
                staged.append((temporary,job.output.path,signature(temporary)))
                if progress:progress(index,len(plan.jobs),job.output.path.name)
            validate_plan(plan,check_source=True)
            publish_staged(staged,published,cancel)
        return tuple(job.output.path for job in plan.jobs)
    except Exception as error:
        publication_error(published,error)
