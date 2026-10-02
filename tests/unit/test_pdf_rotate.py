from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pymupdf
from PIL import Image, ImageChops
from test_pdf_merge import make_pdf
from pdf_lover.core.document import DocumentError, inspect_document
from pdf_lover.core.pdf_output import publish_exclusive
from pdf_lover.features.rotate.service import build_plan, rotate_pdf


class RotateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.a=self.folder/'เอกสาร A.pdf';self.b=self.folder/'เอกสาร B.pdf'
        make_pdf(self.a,['A1','A2','A3'],field='Form value');make_pdf(self.b,['B1'],width=340,height=200)
        with pymupdf.open(self.a) as src:src.embfile_add('note.txt',b'attachment retained');src.saveIncr()
        self.infos=tuple(inspect_document(p) for p in (self.a,self.b))
        self.hashes={p:hashlib.sha256(p.read_bytes()).digest() for p in (self.a,self.b)}

    def tearDown(self):
        for p,h in self.hashes.items():self.assertEqual(hashlib.sha256(p.read_bytes()).digest(),h)
        self.assertFalse(list(self.folder.glob('.pdf-lover-rotate-*')));self.tmp.cleanup()

    def plan(self,angle=90,expressions=None):return build_plan(self.infos,self.folder,'_หมุน',angle,expressions)

    def test_all_angles_all_pages_and_visual_rotation(self):
        for angle,transpose in ((90,Image.Transpose.ROTATE_270),(180,Image.Transpose.ROTATE_180),(270,Image.Transpose.ROTATE_90)):
            out=self.folder/str(angle);out.mkdir();plan=build_plan(self.infos,out,angle=angle)
            rotate_pdf(plan)
            for job in plan.jobs:
                with pymupdf.open(job.info.path) as source,pymupdf.open(job.output.path) as result:
                    self.assertEqual(result.page_count,source.page_count)
                    self.assertEqual(result.get_toc(),source.get_toc())
                    for before,after in zip(source,result):
                        self.assertEqual(after.rotation,(before.rotation+angle)%360)
                        self.assertEqual(after.get_text(),before.get_text())
                        # Raster edge sampling changes with orientation. Restore the original
                        # orientation to prove that the saved content itself is untouched.
                        after.set_rotation(before.rotation)
                        original=before.get_pixmap(dpi=72);rendered=after.get_pixmap(dpi=72)
                        expected=Image.frombytes('RGB',(original.width,original.height),original.samples)
                        actual=Image.frombytes('RGB',(rendered.width,rendered.height),rendered.samples)
                        self.assertEqual(actual.size,expected.size)
                        self.assertIsNone(ImageChops.difference(actual,expected).getbbox())

    def test_selection_per_document_retains_unselected_and_existing_rotation(self):
        plan=self.plan(expressions={self.a:'2',self.b:'1'});rotate_pdf(plan)
        with pymupdf.open(plan.jobs[0].output.path) as result:
            self.assertEqual([p.rotation for p in result],[0,180,0])
            self.assertEqual([p.get_text().splitlines()[0] for p in result],['A1','A2','A3'])

    def test_forms_annotations_links_bookmarks_attachments(self):
        plan=self.plan();rotate_pdf(plan)
        with pymupdf.open(plan.jobs[0].output.path) as result:
            self.assertEqual(next(result[0].widgets()).field_value,'Form value')
            self.assertEqual(len(list(result[1].annots())),1)
            self.assertTrue(any(l.get('page')==1 for l in result[0].get_links()))
            self.assertTrue(any(l.get('uri')=='https://example.com' for l in result[0].get_links()))
            self.assertEqual(result.get_toc(),[[1,'Start',1],[2,'End',3]])
            self.assertEqual(result.embfile_get('note.txt'),b'attachment retained')

    def test_invalid_angles_ranges_and_empty_inputs(self):
        for angle in (0,45,360,-90,True,'90',90.0):
            with self.assertRaises(DocumentError):self.plan(angle)
        for expression in ('','0','4','2,1','1,1','1-3,3','3-2'):
            with self.assertRaises(DocumentError):self.plan(expressions={self.a:expression})
        with self.assertRaises(DocumentError):self.plan(expressions={self.b:'2'})
        with self.assertRaises(DocumentError):build_plan((),self.folder)

    def test_name_collisions_get_unique_stable_names(self):
        copy=self.folder/'other';copy.mkdir();other=copy/self.a.name;other.write_bytes(self.a.read_bytes())
        plan=build_plan((self.infos[0],inspect_document(other)),self.folder)
        self.assertEqual([j.output.path.name for j in plan.jobs],['เอกสาร A_หมุน.pdf','เอกสาร A_หมุน_002.pdf'])
        rotate_pdf(plan)

    def test_duplicate_inputs_original_alias_existing_and_bad_names(self):
        with self.assertRaises(DocumentError):build_plan((self.infos[0],self.infos[0]),self.folder)
        with self.assertRaises(DocumentError):build_plan(self.infos,self.folder,suffix='')
        for suffix in ('/bad',' bad','bad.','x'*41):
            with self.assertRaises(DocumentError):build_plan(self.infos,self.folder,suffix=suffix)
        with self.assertRaises(DocumentError):build_plan(self.infos,self.folder/'missing')
        target=self.folder/'เอกสาร A_หมุน.pdf';target.write_bytes(b'keep')
        with self.assertRaises(DocumentError):self.plan()
        self.assertEqual(target.read_bytes(),b'keep')

    def test_changed_source_rejected_before_any_publish(self):
        plan=self.plan();job=replace(plan.jobs[1],info=replace(self.infos[1],signature=(0,0,0,0)))
        with self.assertRaises(DocumentError):rotate_pdf(replace(plan,jobs=(plan.jobs[0],job)))
        self.assertFalse(plan.jobs[0].output.path.exists())

    def test_forged_plan_cannot_drop_or_reorder_pages(self):
        plan=self.plan();job=plan.jobs[0]
        for pages in ((),(True,),(0,),(4,),(2,1),(1,1)):
            with self.assertRaises(DocumentError):rotate_pdf(replace(plan,jobs=(replace(job,selected=pages),)))
        with self.assertRaises(DocumentError):rotate_pdf(replace(plan,jobs=(replace(job,output=replace(job.output,pages=(1,))),)))

    def test_write_failure_cleans_entire_batch(self):
        plan=self.plan()
        with patch('pymupdf.Document.save',side_effect=OSError('disk full')):
            with self.assertRaises(DocumentError):rotate_pdf(plan)
        self.assertFalse(any(j.output.path.exists() for j in plan.jobs))

    def test_prepublication_collision_preserves_external_output(self):
        plan=self.plan();target=plan.jobs[1].output.path
        def progress(done,total,name):
            if done==total:target.write_bytes(b'external')
        with self.assertRaises(DocumentError):rotate_pdf(plan,progress)
        self.assertEqual(target.read_bytes(),b'external');self.assertFalse(plan.jobs[0].output.path.exists())

    def test_publication_race_rolls_back_own_batch(self):
        plan=self.plan();target=plan.jobs[1].output.path
        def publish(temp,path):
            if path==target:path.write_bytes(b'external')
            publish_exclusive(temp,path)
        with patch('pdf_lover.core.pdf_output.publish_exclusive',side_effect=publish):
            with self.assertRaises(DocumentError):rotate_pdf(plan)
        self.assertEqual(target.read_bytes(),b'external');self.assertFalse(plan.jobs[0].output.path.exists())

    def test_progress_and_missing_corrupt_encrypted_sources(self):
        progress=[];plan=self.plan();rotate_pdf(plan,lambda *event:progress.append(event))
        self.assertEqual([e[:2] for e in progress],[(1,2),(2,2)])
        bad=self.folder/'bad.pdf';bad.write_bytes(b'bad')
        locked=self.folder/'locked.pdf'
        with pymupdf.open(self.a) as src:src.save(locked,encryption=pymupdf.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner')
        for p in (bad,locked,self.folder/'missing.pdf'):
            with self.assertRaises(DocumentError):inspect_document(p)


if __name__=='__main__':unittest.main()
