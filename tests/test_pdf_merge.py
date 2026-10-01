import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
from PIL import Image, ImageDraw
from pdf_merge import MergeError, inspect_pdf, merge_pdfs


def make_pdf(path, labels, width=200, height=300, field=None):
    with pymupdf.open() as document:
        for index, label in enumerate(labels):
            page = document.new_page(width=width, height=height)
            page.insert_text((20, 35), label, fontsize=16)
            page.draw_rect(pymupdf.Rect(20, 60, 90, 100), color=(0.2, 0.4, 0.6), fill=(0.7, 0.8, 0.9))
            if field and index == 0:
                widget = pymupdf.Widget()
                widget.field_name = 'shared_name'
                widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
                widget.field_value = field
                widget.rect = pymupdf.Rect(20, 110, 130, 140)
                page.add_widget(widget)
        document.set_toc([[1, 'Start', 1], [2, 'End', len(labels)]])
        if len(labels) > 1:
            document[0].insert_link({'kind': pymupdf.LINK_GOTO, 'from': pymupdf.Rect(20, 150, 80, 170), 'page': 1})
            document[0].insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(90, 150, 140, 170), 'uri': 'https://example.com'})
            document[1].set_rotation(90)
            document[1].add_text_annot((30, 180), 'Preserve annotation')
        document.save(path)


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix='pdf-merge-test-')
        self.folder = Path(self.sandbox.name)
        self.a = self.folder/'เอกสาร A.pdf'
        self.b = self.folder/'เอกสาร B.pdf'
        self.target = self.folder/'รวมเอกสาร.pdf'
        make_pdf(self.a, ['A-1', 'A-2'], field='Alpha')
        make_pdf(self.b, ['B-1'], width=340, height=200, field='Beta')

    def tearDown(self):
        self.sandbox.cleanup()

    def assert_clean(self):
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.folder.glob('.pdf-lover-*')), [])

    def test_order_text_geometry_rotation_and_visual_fidelity(self):
        original = [hashlib.sha256(path.read_bytes()).digest() for path in [self.a, self.b]]
        self.assertEqual(merge_pdfs([self.b, self.a], self.target), 3)
        with pymupdf.open(self.target) as result, pymupdf.open(self.a) as a, pymupdf.open(self.b) as b:
            for page, source, label in zip(result, [b[0], a[0], a[1]], ['B-1', 'A-1', 'A-2']):
                self.assertIn(label, page.get_text())
                self.assertEqual(page.rect, source.rect)
                self.assertEqual(page.rotation, source.rotation)
                self.assertEqual(page.get_pixmap(dpi=72).samples, source.get_pixmap(dpi=72).samples)
        self.assertEqual(original, [hashlib.sha256(path.read_bytes()).digest() for path in [self.a, self.b]])

    def test_bookmarks_links_annotations_and_independent_forms(self):
        merge_pdfs([self.b, self.a], self.target)
        with pymupdf.open(self.target) as document:
            toc = document.get_toc()
            self.assertIn([1, self.b.stem, 1], toc)
            self.assertIn([1, self.a.stem, 2], toc)
            self.assertIn([3, 'End', 3], toc)
            links = document[1].get_links()
            self.assertTrue(any(link['kind'] == pymupdf.LINK_GOTO and link['page'] == 2 for link in links))
            self.assertTrue(any(link.get('uri') == 'https://example.com' for link in links))
            self.assertEqual(next(document[2].annots()).info['content'], 'Preserve annotation')
            widgets = [widget for page in document for widget in page.widgets()]
            self.assertEqual(sorted(widget.field_value for widget in widgets), ['Alpha', 'Beta'])
            self.assertEqual(len({widget.field_name for widget in widgets}), 2)
            self.assertEqual(document.xref_get_key(document.pdf_catalog(), 'AcroForm')[0], 'xref')

    def test_embedded_image_is_kept(self):
        image = Image.new('RGB', (80, 40), 'navy')
        ImageDraw.Draw(image).rectangle((5, 5, 30, 30), fill='yellow')
        data = io.BytesIO(); image.save(data, format='PNG')
        source = self.folder/'image.pdf'
        with pymupdf.open() as document:
            page = document.new_page(width=180, height=120)
            page.insert_image(pymupdf.Rect(10, 10, 170, 90), stream=data.getvalue())
            document.save(source)
        merge_pdfs([source, self.a], self.target)
        with pymupdf.open(source) as before, pymupdf.open(self.target) as after:
            self.assertEqual(after[0].get_pixmap().samples, before[0].get_pixmap().samples)
            self.assertEqual(len(after[0].get_images()), 1)

    def test_existing_file_and_original_cannot_be_replaced(self):
        self.target.write_bytes(b'KEEP THIS FILE')
        with self.assertRaises(MergeError):
            merge_pdfs([self.a, self.b], self.target)
        self.assertEqual(self.target.read_bytes(), b'KEEP THIS FILE')
        original = self.a.read_bytes()
        with self.assertRaises(MergeError):
            merge_pdfs([self.a, self.b], self.a)
        self.assertEqual(self.a.read_bytes(), original)

    def test_source_alias_cannot_be_replaced(self):
        alias = self.folder/'source-alias.pdf'
        os.link(self.a, alias)
        with self.assertRaisesRegex(MergeError, 'ต้นฉบับ'):
            merge_pdfs([self.a, self.b], alias)

    def test_corrupt_and_missing_sources_leave_no_output(self):
        broken = self.folder/'เสีย.pdf'; broken.write_bytes(b'not a PDF')
        for path in [broken, self.folder/'missing.pdf']:
            with self.assertRaises(MergeError):
                merge_pdfs([self.a, path], self.target)
            self.assert_clean()

    def test_password_pdf_is_rejected(self):
        locked = self.folder/'locked.pdf'
        with pymupdf.open(self.b) as document:
            document.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='secret', owner_pw='owner')
        with self.assertRaisesRegex(MergeError, 'รหัสผ่าน'):
            merge_pdfs([self.a, locked], self.target)
        self.assert_clean()

    def test_publication_race_preserves_newly_created_file(self):
        def progress(done, total, *_):
            if done == total:
                self.target.write_bytes(b'CREATED WHILE MERGING')
        with self.assertRaises(MergeError):
            merge_pdfs([self.a, self.b], self.target, progress)
        self.assertEqual(self.target.read_bytes(), b'CREATED WHILE MERGING')
        self.assertFalse(list(self.folder.glob('.pdf-lover-*')))

    def test_save_failure_cleans_temporary_file(self):
        with patch.object(pymupdf.Document, 'save', side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                merge_pdfs([self.a, self.b], self.target)
        self.assert_clean()

    def test_invalid_count_extension_and_destination(self):
        for paths, target in [([self.a], self.target), ([self.a, self.b], self.folder/'out.txt'),
                              ([self.a, self.b], self.folder/'missing'/'out.pdf')]:
            with self.assertRaises(MergeError):
                merge_pdfs(paths, target)
        self.assert_clean()

    def test_progress_reports_order_and_page_totals(self):
        progress = []
        merge_pdfs([self.b, self.a], self.target, lambda *args: progress.append(args))
        self.assertEqual(progress, [(1, 2, 1, 3, self.b.name), (2, 2, 3, 3, self.a.name)])


if __name__ == '__main__':
    unittest.main()
