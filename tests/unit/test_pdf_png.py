"""Engine behavior after separating rendering from the desktop page."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image
from pdf_lover.features.png.service import convert_pdf, ImageOptions, FORMATS


class PngTests(unittest.TestCase):
    def test_order_dimensions_repeat_conversion_and_original_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.pdf"
            with pymupdf.open() as doc:
                for _ in range(2):
                    doc.new_page(width=144, height=72)
                doc.save(source)
            original = hashlib.sha256(source.read_bytes()).digest()
            progress = []
            first = convert_pdf(source, root, 150, lambda *value: progress.append(value))
            images = sorted(first.glob("*.png"))
            self.assertEqual([path.name for path in images], ["sample_page_001.png", "sample_page_002.png"])
            with Image.open(images[0]) as image:
                self.assertEqual(image.size, (300, 150))
            self.assertEqual(progress, [(1, 2), (2, 2)])
            before = images[0].read_bytes()
            second = convert_pdf(source, root, 150, lambda *_: None)
            self.assertNotEqual(first, second)
            self.assertEqual(images[0].read_bytes(), before)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), original)

    def test_selected_pages_keep_original_names_pixels_and_progress(self):
        from pdf_lover.core.document import inspect_document
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);source = root / "selected.pdf"
            with pymupdf.open() as doc:
                for index in range(5):
                    page=doc.new_page(width=144,height=72)
                    page.insert_text((10,30),str(index+1))
                doc.save(source)
            original=source.read_bytes();info=inspect_document(source)
            for codec,extension in FORMATS.items():
                progress=[]
                output=convert_pdf(source,root,150,lambda *v:progress.append(v),ImageOptions(codec),pages=(2,5),info=info)
                self.assertEqual([p.name for p in sorted(output.glob('*.'+extension))],['selected_page_002.'+extension,'selected_page_005.'+extension])
                self.assertEqual(progress,[(1,2),(2,2)])
                with pymupdf.open(source) as doc:
                    for n in (2,5):
                        with Image.open(output/f'selected_page_{n:03}.{extension}') as image:
                            self.assertEqual(image.size,(300,150))
                            if codec!='JPG':self.assertEqual(image.convert('RGB').tobytes(),doc[n-1].get_pixmap(dpi=150,alpha=False).samples)
            self.assertEqual(source.read_bytes(),original)

    def test_invalid_selection_and_changed_source_create_no_folder(self):
        from pdf_lover.core.document import inspect_document
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'range.pdf'
            with pymupdf.open() as doc:
                doc.new_page();doc.new_page();doc.save(source)
            for pages in ((),(0,),(3,),(2,1),(1,1),(True,),('1',)):
                with self.subTest(pages=pages), self.assertRaises(ValueError):
                    convert_pdf(source,root,72,lambda *_:None,pages=pages)
                self.assertFalse((root/'range').exists())
            info=inspect_document(source)
            source.write_bytes(source.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'ไฟล์เปลี่ยน'):
                convert_pdf(source,root,72,lambda *_:None,pages=(1,),info=info)
            self.assertFalse((root/'range').exists())

    def test_corrupt_source_does_not_create_an_output_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.pdf"
            source.write_bytes(b"not a PDF")
            with self.assertRaises(Exception):
                convert_pdf(source, root, 150, lambda *_: None)
            self.assertFalse((root / "broken").exists())

    def test_formats_lossless_pixels_and_size_warning_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "สีและข้อความ.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page(width=144, height=72)
                page.draw_rect(pymupdf.Rect(8, 8, 120, 60), color=(1, 0, 0), fill=(0.1, 0.6, 0.9))
                page.insert_text((12, 35), "Detail", fontsize=14)
                doc.save(source)
            original = source.read_bytes()
            with pymupdf.open(source) as doc:
                reference = doc[0].get_pixmap(dpi=150, alpha=False, colorspace=pymupdf.csRGB).samples
            for file_type, extension in FORMATS.items():
                with self.subTest(file_type=file_type):
                    warnings = []
                    output = convert_pdf(source, root, 150, lambda *_: None,
                                         ImageOptions(file_type=file_type, max_bytes=1),
                                         lambda *values: warnings.append(values))
                    image_path = next(output.glob("*." + extension))
                    with Image.open(image_path) as image:
                        self.assertEqual(image.size, (300, 150))
                        if file_type != "JPG":
                            self.assertEqual(image.convert("RGB").tobytes(), reference)
                    self.assertEqual(len(warnings), 1)
                    self.assertEqual(warnings[0][1], image_path.stat().st_size)
                    with (output / "image_report.csv").open(encoding="utf-8-sig", newline="") as report:
                        row = next(csv.DictReader(report))
                        self.assertEqual(int(row["bytes"]), image_path.stat().st_size)
                        self.assertEqual(row["over_limit"], "True")
            self.assertEqual(source.read_bytes(), original)

    def test_pixel_bounds_single_dimension_rotation_and_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "aspect.pdf"
            with pymupdf.open() as doc:
                page = doc.new_page(width=300, height=200)
                page.set_cropbox(pymupdf.Rect(20, 10, 220, 110))
                page.set_rotation(90)
                doc.save(source)
            for options, expected in ((ImageOptions(width=400), (400, 800)),
                                      (ImageOptions(height=400), (200, 400)),
                                      (ImageOptions(width=400, height=400), (200, 400))):
                output = convert_pdf(source, root, 150, lambda *_: None, options)
                with Image.open(next(output.glob("*.png"))) as image:
                    self.assertEqual(image.size, expected)

    def test_invalid_options_and_resource_limit_never_silently_downscale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "large.pdf"
            with pymupdf.open() as doc:
                doc.new_page(width=1000, height=1000)
                doc.save(source)
            for options in (ImageOptions(file_type="BMP"), ImageOptions(width=0),
                            ImageOptions(max_bytes=0), ImageOptions(jpeg_quality=101)):
                with self.assertRaises(ValueError):
                    convert_pdf(source, root, 150, lambda *_: None, options)
            self.assertFalse((root / "large").exists())
            with self.assertRaisesRegex(ValueError, "40"):
                convert_pdf(source, root, 150, lambda *_: None, ImageOptions(width=20000))
            self.assertFalse(list((root / "large").glob("*.png")))

    def test_password_document_creates_no_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "locked.pdf"
            with pymupdf.open() as doc:
                doc.new_page()
                doc.save(source, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
            with self.assertRaisesRegex(ValueError, "รหัสผ่าน"):
                convert_pdf(source, root, 150, lambda *_: None)
            self.assertFalse((root / "locked").exists())


if __name__ == "__main__":
    unittest.main()
