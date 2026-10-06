"""Stop real engines at safe boundaries and check ownership, quality and retry."""
import csv
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import pymupdf
from PIL import Image
from pdf_lover.core.cancellation import Cancelled
from pdf_lover.core.document import inspect_document, DocumentError
from pdf_lover.core import pdf_output
from pdf_lover.features.split import service as split
from pdf_lover.features.rotate import service as rotate
from pdf_lover.features.extract import service as extract
from pdf_lover.features.delete_pages import service as delete
from pdf_lover.features.merge.service import merge_pdfs
from pdf_lover.features.png.service import convert_pdf, ImageOptions, FORMATS


class CancellationTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.root = Path(self.sandbox.name)
        self.sources = [self.root / 'original.pdf', self.root / 'second.pdf']
        for path in self.sources:
            with pymupdf.open() as doc:
                for n in range(3):
                    doc.new_page(width=144, height=72).insert_text((10, 30), f'Page {n}')
                doc.save(path)
        self.hashes = [hashlib.sha256(p.read_bytes()).digest() for p in self.sources]
        self.info = inspect_document(self.sources[0])
        self.cancel = threading.Event()

    def tearDown(self):
        self.assertEqual(self.hashes, [hashlib.sha256(p.read_bytes()).digest() for p in self.sources])
        self.assertFalse(list(self.root.rglob('.pdf-lover-*')))
        self.sandbox.cleanup()

    def jobs(self):
        return [
            (split.split_pdf, split.build_plan(self.info, self.root, 'split')),
            (extract.extract_pdf, extract.build_plan(self.info, self.root, 'extract', '1,3', 'pages')),
            (delete.delete_pdf, delete.build_plan(self.info, self.root, 'delete', '2')),
            (rotate.rotate_pdf, rotate.build_plan([self.info], self.root, '_rotate')),
        ]

    def test_pre_cancel_all_engines_creates_no_output(self):
        self.cancel.set()
        for engine, plan in self.jobs():
            with self.subTest(engine=engine.__name__), self.assertRaises(Cancelled):
                engine(plan, cancel=self.cancel)
        with self.assertRaises(Cancelled):
            merge_pdfs(self.sources, self.root/'merged.pdf', cancel=self.cancel)
        with self.assertRaises(Cancelled):
            convert_pdf(self.sources[0], self.root, 72, lambda *_: None, cancel=self.cancel)
        self.assertEqual(set(self.root.iterdir()), set(self.sources))

    def test_stop_after_staging_rolls_back_and_retry_succeeds(self):
        for engine, plan in self.jobs():
            with self.subTest(engine=engine.__name__):
                self.cancel.clear()
                with self.assertRaises(Cancelled):
                    engine(plan, lambda *_: self.cancel.set(), cancel=self.cancel)
                self.assertEqual(set(self.root.iterdir()), set(self.sources))
                paths = engine(plan)
                self.assertTrue(all(p.is_file() for p in paths))
                for path in paths:
                    path.unlink()

    def test_merge_stop_preserves_existing_files_and_retry(self):
        existing = self.root/'existing.pdf';existing.write_bytes(b'existing data')
        target = self.root/'merged.pdf'
        with self.assertRaises(Cancelled):
            merge_pdfs(self.sources, target, lambda *_: self.cancel.set(), self.cancel)
        self.assertFalse(target.exists())
        self.assertEqual(existing.read_bytes(), b'existing data')
        self.assertEqual(merge_pdfs(self.sources, target), 6)

    def test_pdf_stop_during_publication_rolls_back_job(self):
        for module, engine, plan in [
            (split, split.split_pdf, split.build_plan(self.info,self.root,'split')),
            (pdf_output, extract.extract_pdf, extract.build_plan(self.info,self.root,'extract','1-3','pages')),
            (pdf_output, rotate.rotate_pdf, rotate.build_plan([self.info],self.root,'_rotate')),
        ]:
            self.cancel.clear(); publish = module.publish_exclusive
            def stop(temporary, target):
                publish(temporary, target)
                self.cancel.set()
            with self.subTest(engine=engine.__name__), patch.object(module,'publish_exclusive',stop):
                with self.assertRaises(Cancelled):engine(plan,cancel=self.cancel)
            self.assertEqual(set(self.root.iterdir()),set(self.sources))

    def test_rollback_keeps_changed_foreign_output_and_reports_it(self):
        plan = extract.build_plan(self.info,self.root,'extract','1-3','pages')
        publish = pdf_output.publish_exclusive
        def changed(temporary,target):
            publish(temporary,target)
            target.write_bytes(b'replaced externally')
            self.cancel.set()
        with patch.object(pdf_output,'publish_exclusive',changed):
            with self.assertRaisesRegex(DocumentError,'extract_001'):
                extract.extract_pdf(plan,cancel=self.cancel)
        self.assertEqual(plan.outputs[0].path.read_bytes(),b'replaced externally')

    def test_images_keep_one_complete_page_and_csv_all_codecs(self):
        for file_type, extension in FORMATS.items():
            with self.subTest(file_type=file_type):
                self.cancel.clear()
                with self.assertRaises(Cancelled) as caught:
                    convert_pdf(self.sources[0],self.root,72,lambda *_:self.cancel.set(),
                                ImageOptions(file_type=file_type,width=200,max_bytes=1),pages=(2,3),cancel=self.cancel)
                folder=caught.exception.output_folder
                paths=list(folder.glob('*.'+extension))
                self.assertEqual([p.name for p in paths],['original_page_002.'+extension])
                with Image.open(paths[0]) as image:
                    self.assertEqual(image.size,(200,100));image.load()
                    if file_type!='JPG':
                        with pymupdf.open(self.sources[0]) as doc:
                            pixmap=doc[1].get_pixmap(matrix=pymupdf.Matrix(200/144,200/144),alpha=False)
                        reference=Image.frombytes('RGB',(pixmap.width,pixmap.height),pixmap.samples)
                        self.assertEqual(image.convert('RGB').tobytes(),reference.tobytes())
                        reference.close()
                with (folder/'image_report.csv').open(encoding='utf-8-sig',newline='') as report:
                    rows=list(csv.DictReader(report))
                self.assertEqual(len(rows),1)
                self.assertEqual(int(rows[0]['bytes']),paths[0].stat().st_size)
                self.assertEqual(rows[0]['over_limit'],'True')
                retried=convert_pdf(self.sources[0],self.root,72,lambda *_:None,
                                    ImageOptions(file_type=file_type,width=200),pages=(2,3))
                self.assertNotEqual(retried,folder)
                self.assertEqual(len(list(retried.glob('*.'+extension))),2)

    def test_merge_cancel_after_commit_is_success(self):
        target=self.root/'merged.pdf'
        import os
        original=os.rename if os.name=='nt' else os.link
        def committed(*args):
            original(*args);self.cancel.set()
        with patch('pdf_lover.features.merge.service.os.'+('rename' if os.name=='nt' else 'link'),committed):
            self.assertEqual(merge_pdfs(self.sources,target,cancel=self.cancel),6)
        self.assertTrue(target.is_file())
