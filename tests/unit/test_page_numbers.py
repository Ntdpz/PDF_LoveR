import hashlib
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import pymupdf
from PIL import Image
from pdf_lover.core.document import inspect_document, DocumentError
from pdf_lover.core.cancellation import Cancelled
from pdf_lover.features.page_numbers.service import NumberSettings, build_plan, number_pdf, stamp_page, label_for, POSITIONS
from tests.unit.test_pdf_merge import make_pdf


class NumberTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'original.pdf'
        make_pdf(self.source, ['Original 1','Original 2','Original 3','Original 4'], width=400,height=600,field='KEEP')
        with pymupdf.open(self.source) as doc:
            for i,page in enumerate(doc):
                page.set_cropbox(pymupdf.Rect(20,30,380,550))
                page.set_rotation(i*90)
            image = io.BytesIO();Image.new('RGB',(10,10),'red').save(image,format='PNG')
            doc[0].insert_image((150,150,170,170),stream=image.getvalue())
            doc.save(self.folder/'fixture.pdf')
        self.source = self.folder/'fixture.pdf'
        self.original = self.source.read_bytes()
        self.info = inspect_document(self.source)

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertFalse(list(self.folder.glob('.pdf-lover-*')))
        self.temp.cleanup()

    def plan(self, settings=NumberSettings(), expression='1-4', name='out'):
        return build_plan(self.info,self.folder,name,expression,settings)

    def test_modes_start_total_and_thai_digits(self):
        self.assertEqual(label_for(NumberSettings(start=5,format='total'),4,1,10,2),'8 / 10')
        self.assertEqual(label_for(NumberSettings(start=5,sequence='selected',format='total'),4,1,10,2),'6 / 2')
        self.assertEqual(label_for(NumberSettings(format='page',thai_digits=True),2,0,10,1),'หน้า ๒')

    def test_every_position_rotation_cropbox_and_size(self):
        for position in POSITIONS:
            for rotation in (0,90,180,270):
                with pymupdf.open() as doc:
                    page=doc.new_page(width=480,height=680)
                    page.set_cropbox((40,70,400,590));page.set_rotation(rotation)
                    stamp_page(page,'หน้า ๑ / ๑๐',NumberSettings(position=position,size=18,color='#123456'))
                    spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
                    self.assertEqual(''.join(s['text'] for s in spans),'หน้า ๑ / ๑๐')
                    bbox=pymupdf.Rect(spans[0]['bbox'])*page.rotation_matrix
                    self.assertTrue(page.rect.contains(bbox))
                    if position.startswith('top'):self.assertLess(bbox.y1,80)
                    else:self.assertGreater(bbox.y0,page.rect.height-80)
                    if position.endswith('center'):self.assertAlmostEqual((bbox.x0+bbox.x1)/2,page.rect.width/2,delta=1)
                    if position.endswith('left'):self.assertLess(bbox.x0,25)
                    if position.endswith('right'):self.assertGreater(bbox.x1,page.rect.width-25)

    def test_output_preserves_objects_and_selected_content(self):
        plan=self.plan(NumberSettings(format='page',thai_digits=True),'1,3')
        number_pdf(plan)
        with pymupdf.open(self.source) as before,pymupdf.open(plan.outputs[0].path) as after:
            self.assertEqual(before.get_toc(),after.get_toc())
            for i,(a,b) in enumerate(zip(before,after)):
                self.assertEqual(a.cropbox,b.cropbox);self.assertEqual(a.rotation,b.rotation)
                self.assertEqual([{k:v for k,v in x.items() if k!='xref'} for x in a.get_links()],
                                 [{k:v for k,v in x.items() if k!='xref'} for x in b.get_links()])
                self.assertEqual([x[2:8] for x in a.get_images()],[x[2:8] for x in b.get_images()])
                for x,y in zip(a.get_images(),b.get_images()):self.assertEqual(before.xref_stream(x[0]),after.xref_stream(y[0]))
                self.assertEqual(a.get_drawings(),b.get_drawings())
                self.assertEqual([w.field_value for w in a.widgets()],[w.field_value for w in b.widgets()])
                self.assertEqual([x.info for x in a.annots()],[x.info for x in b.annots()])
                if i in (0,2):
                    self.assertIn('หน้า',b.get_text())
                    for font in b.get_fonts(full=True):
                        if 'NotoSansThai' in font[3].replace(' ', ''):self.assertGreater(len(after.extract_font(font[0])[3]),0)
                else:self.assertEqual(a.get_pixmap().samples,b.get_pixmap().samples)
            widget_page=after[0];widget=next(widget_page.widgets());widget.field_value='EDITED';widget.update()
            after.save(self.folder/'edited.pdf')
        with pymupdf.open(self.folder/'edited.pdf') as doc:self.assertEqual(next(doc[0].widgets()).field_value,'EDITED')

    def test_validation_and_collision_safety(self):
        for settings in (NumberSettings(start=0),NumberSettings(size=73),NumberSettings(color='red'),NumberSettings(sequence='x'),NumberSettings(format='x')):
            with self.assertRaises(DocumentError):self.plan(settings)
        for expression in ('','9','2,2','3-1'):
            with self.assertRaises(DocumentError):self.plan(expression=expression)
        with self.assertRaises(DocumentError):self.plan(name='fixture')
        plan=self.plan();plan.outputs[0].path.write_bytes(b'KEEP')
        with self.assertRaises(DocumentError):number_pdf(plan)
        self.assertEqual(plan.outputs[0].path.read_bytes(),b'KEEP')

    def test_cancel_during_pages_then_restart(self):
        plan=self.plan();cancel=threading.Event()
        with self.assertRaises(Cancelled):number_pdf(plan,lambda *_:cancel.set(),cancel)
        self.assertFalse(plan.outputs[0].path.exists())
        number_pdf(plan,cancel=threading.Event())
        self.assertTrue(plan.outputs[0].path.exists())

    def test_disk_error_and_changed_source(self):
        plan=self.plan()
        with patch('pdf_lover.features.page_numbers.service.stamp_page',side_effect=OSError('disk')):
            with self.assertRaises(Exception):number_pdf(plan)
        self.assertFalse(plan.outputs[0].path.exists())
        with patch('pdf_lover.features.page_numbers.service.signature',return_value=('changed',)):
            with self.assertRaises(DocumentError):number_pdf(plan)

    def test_clipping_rejected_without_font_shrink(self):
        with pymupdf.open() as doc:
            page=doc.new_page(width=30,height=30)
            with self.assertRaises(DocumentError):stamp_page(page,'หน้า 999999',NumberSettings(size=72))


if __name__ == '__main__':unittest.main()
