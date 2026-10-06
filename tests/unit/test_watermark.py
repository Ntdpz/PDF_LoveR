import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch
import pymupdf
from PIL import Image
from pdf_lover.core.document import inspect_document, DocumentError
from pdf_lover.core.cancellation import Cancelled
from pdf_lover.features.watermark.service import *
from tests.unit.test_pdf_merge import make_pdf


class WatermarkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        make_pdf(self.folder/'base.pdf',[f'Original {i}' for i in range(4)],width=500,height=700,field='KEEP')
        self.source=self.folder/'fixture.pdf'
        with pymupdf.open(self.folder/'base.pdf') as doc:
            for i,page in enumerate(doc):
                page.set_cropbox((20,30,480,650));page.set_rotation(i*90)
            embedded=self.folder/'original-image.png';Image.new('RGB',(16,8),'navy').save(embedded)
            doc[0].insert_image((180,180,220,200),filename=str(embedded))
            doc.save(self.source)
        self.original=self.source.read_bytes()
        self.info=inspect_document(self.source)
        self.image=self.folder/'alpha.png'
        Image.new('RGBA',(200,100),(255,0,0,128)).save(self.image)
        self.image_info=inspect_image(self.image)

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(),self.original)
        self.assertFalse(list(self.folder.glob('.pdf-lover-*')))
        self.temp.cleanup()

    def plan(self,settings=WatermarkSettings(size=20),expression='1-4',name='out'):
        return build_plan(self.info,self.folder,name,expression,settings)

    def test_positions_rotations_cropbox_angles_and_fonts(self):
        for position in POSITIONS:
            for rotation in (0,90,180,270):
                for angle in (-45,0,30,90):
                    with pymupdf.open() as doc:
                        p=doc.new_page(width=500,height=700)
                        p.set_cropbox((30,40,470,650));p.set_rotation(rotation)
                        stamp_page(p,WatermarkSettings(text='ไทย COPY',size=18,position=position,angle=angle,color='#123456'))
                        spans=[s for b in p.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
                        self.assertIn('ไทย',''.join(s['text'] for s in spans))
                        for span in spans:self.assertTrue(p.rect.contains(pymupdf.Rect(span['bbox'])*p.rotation_matrix))
                        self.assertTrue(any(s['color']==0x123456 for s in spans))
                        pix=p.get_pixmap();self.assertGreater(len(pix.samples),0)
        for font in FONTS:
            with pymupdf.open() as doc:
                p=doc.new_page();stamp_page(p,WatermarkSettings(font=font,text='ไทย English',size=24))
                self.assertIn('ไทย',p.get_text())

    def test_images_alpha_jpg_size_and_opacity(self):
        for kind in ('RGBA','RGB'):
            path=self.folder/('image.png' if kind=='RGBA' else 'image.jpg')
            Image.new(kind,(200,100),(255,0,0,128) if kind=='RGBA' else 'red').save(path)
            info=inspect_image(path)
            for opacity in (0,.25,1):
                for angle in (-60,0,90,180):
                    with pymupdf.open() as doc:
                        p=doc.new_page(width=400,height=600)
                        stamp_page(p,WatermarkSettings(kind='image',image=info,opacity=opacity,angle=angle,image_width=25))
                        pix=p.get_pixmap(alpha=False)
                        center=(300*pix.width+200)*3
                        rgb=tuple(pix.samples[center:center+3])
                        expected=255*(1-opacity*(128/255 if kind=='RGBA' else 1))
                        self.assertAlmostEqual(rgb[0],255,delta=2)
                        self.assertAlmostEqual(rgb[1],expected,delta=3)
                        self.assertAlmostEqual(rgb[2],expected,delta=3)
                        self.assertEqual(p.get_images()[0][2:4],(200,100))
                        if kind=='RGBA':self.assertGreater(p.get_images()[0][1],0)

    def test_selection_fidelity_preview_and_editable_form(self):
        plan=self.plan(expression='1,3')
        watermark_pdf(plan)
        with pymupdf.open(self.source) as before,pymupdf.open(plan.outputs[0].path) as after:
            self.assertEqual(before.get_toc(),after.get_toc())
            for i,(a,b) in enumerate(zip(before,after)):
                self.assertEqual(a.cropbox,b.cropbox);self.assertEqual(a.rotation,b.rotation)
                self.assertEqual([{k:v for k,v in x.items() if k!='xref'} for x in a.get_links()],[{k:v for k,v in x.items() if k!='xref'} for x in b.get_links()])
                self.assertEqual([x.info for x in a.annots()],[x.info for x in b.annots()])
                self.assertEqual(a.get_drawings(),b.get_drawings())
                self.assertEqual([x[2:8] for x in a.get_images()],[x[2:8] for x in b.get_images()])
                for x,y in zip(a.get_images(),b.get_images()):self.assertEqual(before.xref_stream(x[0]),after.xref_stream(y[0]))
                if i+1 in plan.selected:stamp_page(a,plan.settings)
                self.assertEqual(a.get_pixmap().samples,b.get_pixmap().samples)
            p=after[0];widget=next(p.widgets());self.assertEqual(widget.field_value,'KEEP')
            widget.field_value='EDITED';widget.update();after.save(self.folder/'edited.pdf')
        with pymupdf.open(self.folder/'edited.pdf') as check:
            p=check[0];self.assertEqual(next(p.widgets()).field_value,'EDITED')

    def test_invalid_values_images_and_fit(self):
        for change in ({'opacity':float('nan')},{'angle':181},{'size':0},{'image_width':101},{'color':'red'},{'text':''},{'text':'a\nb'},{'font':'bad'},{'position':'bad'},{'kind':'image'}):
            with self.assertRaises(DocumentError):self.plan(replace(WatermarkSettings(),**change))
        bad=self.folder/'bad.png';bad.write_bytes(b'invalid')
        with self.assertRaises(DocumentError):inspect_image(bad)
        huge=self.folder/'huge.png';Image.new('1',(4001,4000)).save(huge)
        with self.assertRaises(DocumentError):inspect_image(huge)
        with pymupdf.open() as doc:
            p=doc.new_page(width=80,height=80)
            with self.assertRaises(DocumentError):stamp_page(p,WatermarkSettings(size=144))

    def test_cancel_retry_existing_source_and_error_cleanup(self):
        plan=self.plan();cancel=threading.Event()
        with self.assertRaises(Cancelled):watermark_pdf(plan,lambda *_:cancel.set(),cancel)
        self.assertFalse(plan.outputs[0].path.exists())
        with patch('pdf_lover.features.watermark.service.stamp_page',side_effect=OSError('disk')):
            with self.assertRaises(DocumentError):watermark_pdf(plan)
        watermark_pdf(plan,cancel=threading.Event())
        digest=hashlib.sha256(plan.outputs[0].path.read_bytes()).digest()
        with self.assertRaises(DocumentError):watermark_pdf(plan)
        self.assertEqual(hashlib.sha256(plan.outputs[0].path.read_bytes()).digest(),digest)
        with self.assertRaises(DocumentError):self.plan(name=self.source.stem)

    def test_changed_image_and_source_rejected(self):
        plan=self.plan(WatermarkSettings(kind='image',image=self.image_info))
        self.image.unlink()
        with self.assertRaises(DocumentError):self.plan(WatermarkSettings(kind='image',image=self.image_info))
        self.image.write_bytes(b'changed')
        with self.assertRaises(DocumentError):watermark_pdf(plan)
        with patch('pdf_lover.features.watermark.service.signature',return_value=('changed',)):
            with self.assertRaises(DocumentError):watermark_pdf(self.plan())

if __name__=='__main__':unittest.main()
