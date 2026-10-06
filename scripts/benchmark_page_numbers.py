"""Bounded synthetic export audit on two logical CPUs, not low-spec certification."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pymupdf
from scripts.benchmark_resources import counters
from pdf_lover.core.document import inspect_document
from pdf_lover.features.page_numbers.service import NumberSettings,build_plan,number_pdf


def main():
    assert ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(-1),ctypes.c_size_t(3))
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder)/'source.pdf'
        with pymupdf.open() as doc:
            for i in range(1000):doc.new_page().insert_text((72,72),f'Original {i}')
            doc.save(source)
        original=hashlib.sha256(source.read_bytes()).hexdigest()
        plan=build_plan(inspect_document(source),folder,'out','1-1000',NumberSettings(format='page',thai_digits=True))
        start=time.perf_counter();number_pdf(plan);elapsed=time.perf_counter()-start
        memory=counters(os.getpid())
        assert original==hashlib.sha256(source.read_bytes()).hexdigest()
        with pymupdf.open(plan.outputs[0].path) as check:
            assert check.page_count==1000 and 'หน้า ๑๐๐๐' in check[-1].get_text()
        report={'passed':True,'version':'1.12.0','host':platform.platform(),'logical_cpus':os.cpu_count(),
                'affinity_logical_cpus':2,'pages':1000,'elapsed_seconds':round(elapsed,3),
                'output_bytes':plan.outputs[0].path.stat().st_size,'counters':memory,
                'quality':'vector overlay; duplicate font streams merged; no rasterization or typography reduction',
                'limitations':['Synthetic text export; peak includes fixture creation','Logical CPU affinity does not emulate4GB RAM/HDD','No physical low-spec or Windows11 test']}
    (ROOT/'docs/page-numbers-resources-1.12.0.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
