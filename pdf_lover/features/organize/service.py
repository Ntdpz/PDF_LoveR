"""Reorder the original page objects without rasterization or GUI imports."""
from pathlib import Path
import tempfile
import pymupdf
from dataclasses import dataclass
from pdf_lover.core.document import DocumentError, signature, validate_prefix
from pdf_lover.core.cancellation import checkpoint
from pdf_lover.core.pdf_output import PagePlan, PageOutput, validate_targets, publish_staged, publication_error


@dataclass(frozen=True)
class EditPlan:
    document: object
    sources: tuple
    outputs: tuple
    references: tuple


def build_edit_plan(sources, directory, prefix, references):
    """Each identity is (source index, one-based original page), unique once."""
    validate_prefix(prefix)
    refs = tuple(references)
    if not sources or not refs or len(refs) != len(set(refs)):
        raise DocumentError('ต้องเหลืออย่างน้อยหนึ่งหน้า และไม่มีหน้าซ้ำ')
    for source, page in refs:
        if type(source) is not int or type(page) is not int or not 0 <= source < len(sources) or not 1 <= page <= sources[source].page_count:
            raise DocumentError('หน้าอ้างอิงไม่ถูกต้อง')
    target = Path(directory).expanduser().resolve() / f'{prefix}.pdf'
    for info in sources:
        validate_targets(PagePlan(info, (PageOutput(target, (1,)),)))
    return EditPlan(sources[0], tuple(sources), (PageOutput(target, refs),), refs)


def organize_pdf(plan, progress=None, cancel=None):
    """Append native pages once, remove omitted xrefs, then move retained xrefs."""
    if isinstance(plan, PagePlan):
        return reorder_pdf(plan, progress, cancel)
    checkpoint(cancel)
    if len(plan.outputs) != 1 or plan.outputs[0].pages != plan.references:
        raise DocumentError('แผนจัดระเบียบต้องมี PDF ใหม่หนึ่งไฟล์พร้อมลำดับที่ตรงกัน')
    output = plan.outputs[0]
    build_edit_plan(plan.sources, output.path.parent, output.path.stem, plan.references)
    published = []
    try:
        def check_sources():
            for info in plan.sources:
                checkpoint(cancel)
                if signature(info.path) != info.signature:
                    raise DocumentError('ต้นฉบับเปลี่ยนหลังแสดงตัวอย่าง · เลือกไฟล์ใหม่')
        check_sources()
        with tempfile.TemporaryDirectory(prefix='.pdf-lover-order-', dir=output.path.parent) as staging:
            temporary = Path(staging) / 'organized.pdf'
            with pymupdf.open(plan.sources[0].path) as document:
                identities = [(0, p) for p in range(1, document.page_count + 1)]
                toc_groups = [(0, document.get_toc(simple=False))]
                used_sources = {identity[0] for identity in plan.references}
                for source_index, info in enumerate(plan.sources[1:], 1):
                    checkpoint(cancel)
                    if source_index not in used_sources:
                        continue
                    with pymupdf.open(info.path) as source:
                        toc_groups.append((source_index, source.get_toc(simple=False)))
                        document.insert_pdf(source, links=True, annots=True, widgets=True, join_duplicates=False)
                        identities.extend((source_index, p) for p in range(1, source.page_count + 1))
                checkpoint(cancel)
                xrefs = dict(zip(identities, (document.page_xref(i) for i in range(document.page_count))))
                selected = set(plan.references)
                omitted = [i for i, identity in enumerate(identities) if identity not in selected]
                if omitted:
                    document.delete_pages(omitted)
                current = [identity for identity in identities if identity in selected]
                # Positions update with native moves; direct links use retained page xrefs.
                for position, identity in enumerate(plan.references):
                    checkpoint(cancel)
                    old = current.index(identity, position)
                    if old != position:
                        document.move_page(old, position)
                        current.insert(position, current.pop(old))
                    if progress and (position % 20 == 0 or position == len(current) - 1):
                        progress(position + 1, len(current), output.path.name)
                mapping = {identity: i for i, identity in enumerate(plan.references, 1)}
                toc = []
                for source_index, entries in toc_groups:
                    previous_level = 0
                    for entry in entries:
                        mapped = mapping.get((source_index, entry[2]))
                        if mapped is None:
                            continue
                        entry[0] = min(entry[0], previous_level + 1)
                        previous_level = entry[0]
                        entry[2] = mapped
                        if entry[3].get('kind') == pymupdf.LINK_GOTO:
                            entry[3]['page'] = mapped - 1
                        toc.append(entry)
                document.set_toc(toc)
                expected = [xrefs[identity] for identity in plan.references]
                if [document.page_xref(i) for i in range(document.page_count)] != expected:
                    raise DocumentError('ตรวจหน้าอ้างอิงไม่ผ่าน')
                checkpoint(cancel)
                document.save(temporary, garbage=0, deflate=True)
            checkpoint(cancel)
            with pymupdf.open(temporary) as check:
                if [check.page_xref(i) for i in range(check.page_count)] != expected:
                    raise DocumentError('ตรวจลำดับไฟล์ใหม่ไม่ผ่าน')
            check_sources()
            build_edit_plan(plan.sources, output.path.parent, output.path.stem, plan.references)
            publish_staged([(temporary, output.path, signature(temporary))], published, cancel)
        return (output.path,)
    except Exception as error:
        publication_error(published, error)


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
