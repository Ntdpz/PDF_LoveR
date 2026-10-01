"""Engine behavior after separating rendering from the desktop page."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image
from pdf_lover.features.png.service import convert_pdf


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

    def test_corrupt_source_does_not_create_an_output_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.pdf"
            source.write_bytes(b"not a PDF")
            with self.assertRaises(Exception):
                convert_pdf(source, root, 150, lambda *_: None)
            self.assertFalse((root / "broken").exists())


if __name__ == "__main__":
    unittest.main()
