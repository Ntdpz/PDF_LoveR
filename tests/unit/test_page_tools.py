import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pymupdf
from pdf_lover.core.document import DocumentError, inspect_document
from pdf_lover.core.pdf_output import PagePlan, PageOutput, export_pages, publish_exclusive
from pdf_lover.features.extract.service import build_plan as extract_plan, extract_pdf
from pdf_lover.features.delete_pages.service import build_plan as delete_plan, delete_pdf
from test_pdf_merge import make_pdf


class PageToolsTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory(prefix='pdf-page-tools-')
        self.folder = Path(self.sandbox.name)
        self.source = self.folder/'ต้นฉบับ.pdf'
        make_pdf(self.source, [f'PAGE {i}' for i in range(1, 11)], field='Form value')
        with pymupdf.open(self.source) as source:
            source[0].insert_link({'kind':pymupdf.LINK_GOTO,'from':pymupdf.Rect(20,70,80,90),'page':9,'to':pymupdf.Point(0,0)})
            source[1].insert_link({'kind':pymupdf.LINK_GOTO,'from':pymupdf.Rect(10,20,40,30),'page':9,'to':pymupdf.Point(0,0)})
            source.saveIncr()
        self.info = inspect_document(self.source)
        self.before = hashlib.sha256(self.source.read_bytes()).digest()

    def tearDown(self):
        self.assertEqual(self.before, hashlib.sha256(self.source.read_bytes()).digest())
        self.assertFalse(list(self.folder.glob('.pdf-lover-pages-*')))
        self.sandbox.cleanup()

    def extract(self, expression='1-3,5,8-10', mode='single'):
        return extract_plan(self.info, self.folder, 'หน้าที่เลือก', expression, mode)

    def delete(self, expression='3-4,6-7'):
        return delete_plan(self.info, self.folder, 'หน้าที่เหลือ', expression)

    def assert_pages(self, plan):
        with pymupdf.open(self.source) as source:
            for output in plan.outputs:
                with pymupdf.open(output.path) as result:
                    self.assertEqual(result.page_count,len(output.pages))
                    for page,number in zip(result, output.pages):
                        original=source[number-1]
                        self.assertEqual(page.get_text().splitlines()[0],f'PAGE {number}')
                        self.assertEqual(page.rotation,original.rotation)
                        self.assertEqual(page.rect,original.rect)
                        self.assertEqual(page.get_pixmap(dpi=72).samples,original.get_pixmap(dpi=72).samples)

    def test_extract_single_non_contiguous_counts_order_pixels(self):
        plan=self.extract(); progress=[]
        self.assertEqual(extract_pdf(plan,lambda *e:progress.append(e)),tuple(o.path for o in plan.outputs))
        self.assertEqual(plan.outputs[0].pages,(1,2,3,5,8,9,10))
        self.assertEqual(progress[-1][:2],(1,1));self.assert_pages(plan)

    def test_extract_one_file_per_selected_page(self):
        plan=self.extract(mode='pages');extract_pdf(plan);self.assert_pages(plan)
        self.assertEqual(len(plan.outputs),7)
        self.assertEqual(plan.outputs[3].path.name,'หน้าที่เลือก_004_p005.pdf')

    def test_delete_retained_order_pixels(self):
        plan=self.delete();delete_pdf(plan)
        self.assertEqual(plan.outputs[0].pages,(1,2,5,8,9,10));self.assert_pages(plan)

    def test_extract_contiguous_and_all(self):
        for expression,prefix in [('2-4','ช่วง'),('1-10','ทั้งหมด')]:
            plan=extract_plan(self.info,self.folder,prefix,expression);extract_pdf(plan);self.assert_pages(plan)

    def test_delete_first_last_leaves_one(self):
        plan=self.delete('1-9');delete_pdf(plan);self.assert_pages(plan)
        self.assertEqual(plan.outputs[0].pages,(10,))

    def test_reject_empty_all_deleted_duplicate_reverse_and_out_of_bounds(self):
        for function in (self.extract,self.delete):
            for text in ('','0','11','3-2','2,1','1,1','1-3,3','1,,2'):
                with self.subTest(function=function,text=text),self.assertRaises(DocumentError):function(text)
        with self.assertRaisesRegex(DocumentError,'ลบทุกหน้า'):self.delete('1-10')

    def test_reject_unknown_export_mode(self):
        with self.assertRaises(DocumentError):self.extract(mode='unknown')
        with self.assertRaises(DocumentError):delete_plan(self.info,self.folder,'ใหม่','1','pages')

    def test_links_forms_annotations_bookmarks_across_gaps(self):
        for plan in (self.extract('1-2,10'),self.delete('3-9')):
            export_pages(plan)
            with pymupdf.open(plan.outputs[0].path) as result:
                self.assertEqual(next(result[0].widgets()).field_value,'Form value')
                self.assertEqual(len(list(result[1].annots())),1)
                self.assertTrue(any(l.get('page')==2 for l in result[0].get_links()))
                self.assertTrue(any(l.get('page')==2 for l in result[1].get_links()))
                self.assertTrue(any(l.get('uri')=='https://example.com' for l in result[0].get_links()))
                self.assertEqual(result.get_toc(),[[1,'Start',1],[2,'End',3]])

    def test_links_to_removed_pages_are_removed(self):
        plan=self.extract('1,5');extract_pdf(plan)
        with pymupdf.open(plan.outputs[0].path) as result:
            self.assertFalse(any(l['kind']==pymupdf.LINK_GOTO for l in result[0].get_links()))
            self.assertTrue(any(l['kind']==pymupdf.LINK_URI for l in result[0].get_links()))

    def test_output_existing_original_alias_invalid_name_directory(self):
        existing=self.folder/'เดิม.pdf';existing.write_bytes(b'keep')
        for prefix in ('เดิม','ต้นฉบับ','CON','bad/name',' name','bad.'):
            with self.subTest(prefix=prefix),self.assertRaises(DocumentError):extract_plan(self.info,self.folder,prefix,'1')
        alias=self.folder/'alias.pdf';os.link(self.source,alias)
        with self.assertRaisesRegex(DocumentError,'ต้นฉบับ'):extract_plan(self.info,self.folder,'alias','1')
        with self.assertRaises(DocumentError):extract_plan(self.info,self.folder/'missing','ใหม่','1')
        self.assertEqual(existing.read_bytes(),b'keep')

    def test_forged_plans_invalid_pages_and_duplicate_targets(self):
        for pages in ((),(1,1),(2,1),(0,),(11,),(True,)):
            with self.assertRaises(DocumentError):export_pages(PagePlan(self.info,(PageOutput(self.folder/'ใหม่.pdf',pages),)))
        output=PageOutput(self.folder/'same.pdf',(1,))
        with self.assertRaises(DocumentError):export_pages(PagePlan(self.info,(output,output)))
        with self.assertRaises(DocumentError):export_pages(PagePlan(self.info,(
            output,PageOutput(self.folder/'different.pdf',(1,)))))

    def test_changed_source_since_preview(self):
        plan=self.extract()
        from dataclasses import replace
        plan=replace(plan,document=replace(self.info,signature=(0,0,0,0)))
        with self.assertRaisesRegex(DocumentError,'เปลี่ยน'):extract_pdf(plan)
        self.assertFalse(plan.outputs[0].path.exists())

    def test_save_failure_leaves_no_outputs(self):
        plan=self.extract(mode='pages')
        with patch('pymupdf.Document.save',side_effect=OSError('disk full')):
            with self.assertRaises(DocumentError):extract_pdf(plan)
        self.assertFalse(any(o.path.exists() for o in plan.outputs))

    def test_conflict_before_publication_keeps_existing_file(self):
        plan=self.extract(mode='pages');target=plan.outputs[-1].path
        def progress(done,total,name):
            if done==total:target.write_bytes(b'external')
        with self.assertRaises(DocumentError):extract_pdf(plan,progress)
        self.assertEqual(target.read_bytes(),b'external')
        self.assertFalse(any(o.path.exists() for o in plan.outputs[:-1]))

    def test_publication_race_rolls_back_only_this_job(self):
        plan=self.extract(mode='pages');target=plan.outputs[1].path
        def publisher(temporary,path):
            if path==target:path.write_bytes(b'external')
            publish_exclusive(temporary,path)
        with patch('pdf_lover.core.pdf_output.publish_exclusive',side_effect=publisher):
            with self.assertRaises(DocumentError):extract_pdf(plan)
        self.assertEqual(target.read_bytes(),b'external')
        self.assertFalse(plan.outputs[0].path.exists())

    def test_missing_corrupt_encrypted_pdf(self):
        corrupt=self.folder/'bad.pdf';corrupt.write_bytes(b'not a pdf')
        encrypted=self.folder/'locked.pdf'
        with pymupdf.open(self.source) as src:src.save(encrypted,encryption=pymupdf.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner')
        for path in (self.folder/'missing.pdf',corrupt,encrypted):
            with self.assertRaises(DocumentError):inspect_document(path)


if __name__=='__main__':unittest.main()
