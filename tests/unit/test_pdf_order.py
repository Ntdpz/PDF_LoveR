import hashlib
from dataclasses import replace
import itertools
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import pymupdf
from pdf_lover.core.document import inspect_document, DocumentError
from pdf_lover.core.cancellation import Cancelled
from pdf_lover.core.page_order import move_selected
from pdf_lover.features.organize.service import build_plan, reorder_pdf
from test_pdf_merge import make_pdf


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'ต้นฉบับ.pdf'
        make_pdf(self.source, ['PAGE 1', 'PAGE 2', 'PAGE 3', 'PAGE 4'], field='Keep value')
        self.info = inspect_document(self.source)
        self.original = self.source.read_bytes()

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(list(self.folder.glob('.pdf-lover-order-*')))
        self.temp.cleanup()

    def plan(self, order=(4, 2, 3, 1), name='new'):
        return build_plan(self.info, self.folder, name, order)

    def test_real_order_links_toc_annots_widgets_rotation_pixels(self):
        plan = self.plan()
        reorder_pdf(plan)
        with pymupdf.open(self.source) as source, pymupdf.open(plan.outputs[0].path) as result:
            self.assertEqual(result.get_toc(), [[1, 'Start', 4], [2, 'End', 1]])
            for slot, original in enumerate(plan.outputs[0].pages):
                a, b = source[original - 1], result[slot]
                self.assertEqual(a.xref, b.xref)
                self.assertEqual(a.get_text(), b.get_text())
                self.assertEqual(a.rotation, b.rotation)
                self.assertEqual(a.rect, b.rect)
                self.assertEqual(a.get_pixmap().samples, b.get_pixmap().samples)
            self.assertEqual(next(result[3].widgets()).field_value, 'Keep value')
            self.assertEqual(next(result[1].annots()).info['content'], 'Preserve annotation')
            self.assertTrue(any(l.get('page') == 1 for l in result[3].get_links()))
            self.assertTrue(any(l.get('uri') == 'https://example.com' for l in result[3].get_links()))
            widget = next(result[3].widgets())
            widget.field_value = 'Editable after reorder'
            widget.update()
            result.save(self.folder / 'edited.pdf')
        with pymupdf.open(self.folder / 'edited.pdf') as result:
            self.assertEqual(next(result[3].widgets()).field_value, 'Editable after reorder')

    def test_invalid_missing_duplicate_types(self):
        for order in ((), (1, 2), (1, 1, 3, 4), (0, 2, 3, 4), (True, 2, 3, 4), (1, 2, 3, 5)):
            with self.assertRaises(DocumentError):
                self.plan(order)

    def test_original_alias_and_existing_output(self):
        alias = self.folder / 'alias.pdf'
        os.link(self.source, alias)
        for name in ('ต้นฉบับ', 'alias'):
            with self.assertRaises(DocumentError):
                self.plan(name=name)
        existing = self.folder / 'new.pdf'
        existing.write_bytes(b'keep')
        with self.assertRaises(DocumentError):
            self.plan()
        self.assertEqual(existing.read_bytes(), b'keep')

    def test_cancel_during_order_then_restart(self):
        plan = self.plan()
        event = threading.Event()
        with self.assertRaises(Cancelled):
            reorder_pdf(plan, lambda *_: event.set(), event)
        self.assertFalse(plan.outputs[0].path.exists())
        event.clear()
        reorder_pdf(plan, cancel=event)
        self.assertTrue(plan.outputs[0].path.exists())

    def test_cancel_after_publication_rolls_back(self):
        from pdf_lover.core.pdf_output import publish_exclusive
        event = threading.Event()
        plan = self.plan()
        def publish(*args):
            publish_exclusive(*args)
            event.set()
        with patch('pdf_lover.core.pdf_output.publish_exclusive', side_effect=publish), self.assertRaises(Cancelled):
            reorder_pdf(plan, cancel=event)
        self.assertFalse(plan.outputs[0].path.exists())

    def test_disk_failure_and_collision(self):
        plan = self.plan()
        with patch('pymupdf.Document.save', side_effect=OSError('full')), self.assertRaises(DocumentError):
            reorder_pdf(plan)
        self.assertFalse(plan.outputs[0].path.exists())
        def collision(*_):
            plan.outputs[0].path.write_bytes(b'external')
        with self.assertRaises(DocumentError):
            reorder_pdf(plan, collision)
        self.assertEqual(plan.outputs[0].path.read_bytes(), b'external')

    def test_multi_selection_preserves_relative_order(self):
        self.assertEqual(move_selected((1,2,3,4,5), {2,4}, 5), (1,3,5,2,4))
        self.assertEqual(move_selected((1,2,3,4,5), {2,4}, 0), (2,4,1,3,5))
        self.assertEqual(move_selected((1,2,3), {1,2,3}, 1), (1,2,3))

    def test_all_four_page_permutations(self):
        for index, order in enumerate(itertools.permutations(range(1,5))):
            plan = self.plan(order, name=f'permutation-{index}')
            reorder_pdf(plan)
            with pymupdf.open(plan.outputs[0].path) as result:
                self.assertEqual([p.get_text().splitlines()[0] for p in result], [f'PAGE {n}' for n in order])
                self.assertEqual(result.get_toc(), [[1,'Start',order.index(1)+1],[2,'End',order.index(4)+1]])

    def test_source_changed_and_cancel_after_save(self):
        plan = self.plan()
        stale = replace(plan, document=replace(self.info, signature=(0,0,0,0)))
        with self.assertRaises(DocumentError):
            reorder_pdf(stale)
        event = threading.Event()
        original_save = pymupdf.Document.save
        def save(document, *args, **kwargs):
            original_save(document, *args, **kwargs)
            event.set()
        with patch('pymupdf.Document.save',save), self.assertRaises(Cancelled):
            reorder_pdf(plan, cancel=event)
        self.assertFalse(plan.outputs[0].path.exists())


if __name__ == '__main__':
    unittest.main()
