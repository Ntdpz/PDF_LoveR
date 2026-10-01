import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

from pdf_lover.core.page_selection import parse_page_groups, selected_pages, format_pages, split_groups, PageSelectionError
from pdf_lover.features.split.service import (inspect_document, build_plan, split_pdf, SplitError,
                                            SplitPlan, SplitOutput, publish_exclusive)
from test_pdf_merge import make_pdf


class PageSelectionTests(unittest.TestCase):
    def test_ranges_selection_and_format(self):
        self.assertEqual([list(group) for group in parse_page_groups(' 1 - 3, 5,8-10 ', 10)], [[1, 2, 3], [5], [8, 9, 10]])
        self.assertEqual(selected_pages('1-3,5', 10), (1, 2, 3, 5))
        self.assertEqual(format_pages([5, 3, 2, 1, 3]), '1-3,5')
        self.assertEqual(format_pages([]), '')

    def test_reject_bad_ranges_duplicates_and_order(self):
        for text in ('', '0', '11', '4-2', '3,2', '1-3,3-5', '1,1', '1,,2', '-1', '1.5', '1-', 'all', '1;2', '1-2-3', '١', '9'*50):
            with self.subTest(text=text), self.assertRaises(PageSelectionError):
                parse_page_groups(text, 10)

    def test_chunks_boundaries_and_modes(self):
        self.assertEqual([list(p) for p in split_groups(5, 'chunks', chunk_size=2)], [[1, 2], [3, 4], [5]])
        self.assertEqual([list(p) for p in split_groups(1, 'pages')], [[1]])
        self.assertEqual([list(p) for p in split_groups(5, 'chunks', chunk_size=5)], [[1, 2, 3, 4, 5]])
        for chunk in (0, -1, 6, 1.5, '2', True):
            with self.assertRaises(PageSelectionError):
                split_groups(5, 'chunks', chunk_size=chunk)
        for count in (0, -1, 1.5, True):
            with self.assertRaises(PageSelectionError):
                split_groups(count, 'pages')
        with self.assertRaises(PageSelectionError):
            split_groups(5, 'unknown')


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix='pdf-split-')
        self.folder = Path(self.sandbox.name)
        self.source = self.folder / 'ต้นฉบับ.pdf'
        make_pdf(self.source, [f'PAGE {i}' for i in range(1, 11)], field='Form value')
        self.info = inspect_document(self.source)
        self.before = hashlib.sha256(self.source.read_bytes()).digest()

    def tearDown(self):
        self.assertEqual(self.before, hashlib.sha256(self.source.read_bytes()).digest())
        self.assertFalse(list(self.folder.glob('.pdf-lover-split-*')))
        self.sandbox.cleanup()

    def plan(self, mode='ranges', expression='1-3,5,8-10', chunk=2):
        return build_plan(self.info, self.folder, 'ผลลัพธ์', mode, expression, chunk)

    def test_all_three_modes_counts_order_and_pixels(self):
        for mode, expected in [('pages', [[i] for i in range(1, 11)]),
                               ('ranges', [[1, 2, 3], [5], [8, 9, 10]]),
                               ('chunks', [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]])]:
            with self.subTest(mode=mode):
                directory = self.folder / mode; directory.mkdir()
                plan = build_plan(self.info, directory, 'ชุด', mode, '1-3,5,8-10', 3)
                progress = []
                paths = split_pdf(plan, lambda *event: progress.append(event))
                self.assertEqual([list(p.pages) for p in plan.outputs], expected)
                self.assertEqual(len(paths), len(expected))
                self.assertEqual(progress[-1][:2], (len(expected), len(expected)))
                with pymupdf.open(self.source) as source:
                    for path, pages in zip(paths, expected):
                        with pymupdf.open(path) as result:
                            self.assertEqual(result.page_count, len(pages))
                            for page, number in zip(result, pages):
                                self.assertEqual(page.get_text().splitlines()[0], f'PAGE {number}')
                                self.assertEqual(page.rect, source[number - 1].rect)
                                self.assertEqual(page.rotation, source[number - 1].rotation)
                                self.assertEqual(page.get_pixmap(dpi=72).samples, source[number - 1].get_pixmap(dpi=72).samples)

    def test_links_forms_annotations_and_bookmark_mapping(self):
        paths = split_pdf(self.plan())
        with pymupdf.open(paths[0]) as result:
            self.assertEqual(next(result[0].widgets()).field_value, 'Form value')
            self.assertTrue(any(link.get('page') == 1 for link in result[0].get_links()))
            self.assertTrue(any(link.get('uri') == 'https://example.com' for link in result[0].get_links()))
            self.assertEqual(next(result[1].annots()).info['content'], 'Preserve annotation')
            self.assertIn([1, 'Start', 1], result.get_toc())
        with pymupdf.open(paths[-1]) as result:
            self.assertEqual(result.get_toc(), [[1, 'End', 3]])

    def test_existing_files_and_source_alias_never_overwritten(self):
        plan = self.plan()
        plan.outputs[1].path.write_bytes(b'KEEP')
        with self.assertRaisesRegex(SplitError, 'มีอยู่แล้ว'):
            split_pdf(plan)
        self.assertFalse(plan.outputs[0].path.exists())
        self.assertEqual(plan.outputs[1].path.read_bytes(), b'KEEP')
        for path in (self.source, self.folder / 'alias.pdf'):
            if path != self.source:
                os.link(self.source, path)
            with self.assertRaisesRegex(SplitError, 'ต้นฉบับ'):
                split_pdf(SplitPlan(self.info, (SplitOutput(path, range(1, 2)),)))

    def test_invalid_filename_directory_and_forged_plan(self):
        for prefix in ('', ' ', 'a/b', 'a\\b', 'a:', 'CON', 'COM1', 'LPT¹', 'NUL.txt', 'x.', ' x', 'x'*101):
            with self.subTest(prefix=prefix), self.assertRaises(SplitError):
                build_plan(self.info, self.folder, prefix)
        with self.assertRaises(SplitError):
            build_plan(self.info, self.folder / 'missing', 'new')
        for pages in (range(0, 2), range(1, 12), range(2, 1), range(1, 4, 2)):
            with self.assertRaises(SplitError):
                split_pdf(SplitPlan(self.info, (SplitOutput(self.folder / 'bad.pdf', pages),)))

    def test_corrupt_missing_password_and_non_pdf(self):
        bad = self.folder / 'bad.pdf'; bad.write_bytes(b'BROKEN')
        locked = self.folder / 'locked.pdf'
        with pymupdf.open(self.source) as source:
            source.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='secret', owner_pw='owner')
        for path in (bad, self.folder / 'gone.pdf', locked):
            with self.assertRaises(SplitError):
                inspect_document(path)

    def test_changed_source_since_preview_rejected(self):
        plan = self.plan()
        stat = self.source.stat()
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10000000))
        with self.assertRaisesRegex(SplitError, 'เปลี่ยน'):
            split_pdf(plan)
        self.assertFalse(any(output.path.exists() for output in plan.outputs))

    def test_write_failure_leaves_no_published_outputs(self):
        plan = self.plan()
        with patch('pymupdf.Document.save', side_effect=OSError('disk full')):
            with self.assertRaises(SplitError):
                split_pdf(plan)
        self.assertFalse(any(output.path.exists() for output in plan.outputs))

    def test_race_during_publication_rolls_back_own_files(self):
        plan = self.plan()
        calls = []
        def race(temporary, target):
            calls.append(target)
            if len(calls) == 2:
                target.write_bytes(b'NEW EXTERNAL FILE')
            publish_exclusive(temporary, target)
        with patch('pdf_lover.features.split.service.publish_exclusive', side_effect=race):
            with self.assertRaises(SplitError):
                split_pdf(plan)
        self.assertFalse(plan.outputs[0].path.exists())
        self.assertEqual(plan.outputs[1].path.read_bytes(), b'NEW EXTERNAL FILE')
        self.assertFalse(plan.outputs[2].path.exists())

    def test_prepublication_race_preserves_existing_set(self):
        plan = self.plan()
        def progress(done, total, name):
            if done == total:
                plan.outputs[1].path.write_bytes(b'KEEP')
        with self.assertRaises(SplitError):
            split_pdf(plan, progress)
        self.assertFalse(plan.outputs[0].path.exists())
        self.assertEqual(plan.outputs[1].path.read_bytes(), b'KEEP')
