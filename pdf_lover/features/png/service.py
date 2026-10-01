"""PDF to PNG engine; independent of Tk and navigation."""
from pathlib import Path
import pymupdf


def available_folder(parent: Path, name: str) -> Path:
    candidate = parent / name
    number = 2
    while candidate.exists():
        candidate = parent / f"{name}_{number}"
        number += 1
    candidate.mkdir()
    return candidate


def convert_pdf(pdf_path: Path, output_root: Path, dpi: int, progress) -> Path:
    with pymupdf.open(pdf_path) as document:
        if document.page_count == 0:
            raise ValueError("PDF ไม่มีหน้า")
        output_folder = available_folder(output_root, pdf_path.stem)
        digits = max(3, len(str(document.page_count)))
        for index, page in enumerate(document, start=1):
            image = page.get_pixmap(dpi=dpi, alpha=False)
            image.save(output_folder / f"{pdf_path.stem}_page_{index:0{digits}d}.png")
            progress(index, document.page_count)
    return output_folder
