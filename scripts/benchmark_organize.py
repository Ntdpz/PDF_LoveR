"""Synthetic multi-source edit/export audit; affinity is not hardware certification."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pymupdf
from scripts.benchmark_resources import counters
from pdf_lover.core.document import inspect_document
from pdf_lover.core.page_order import OrderHistory
from pdf_lover.core.cancellation import Cancelled
from pdf_lover.features.organize.service import build_edit_plan, organize_pdf
from pdf_lover.version import VERSION


def main():
    assert ctypes.windll.kernel32.SetProcessAffinityMask(ctypes.c_void_p(-1), ctypes.c_size_t(3))
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        sources = []
        for source in range(2):
            path = folder / f'source-{source}.pdf'
            with pymupdf.open() as document:
                for number in range(500):
                    document.new_page(width=400+source*100, height=600).insert_text((72,72), f'{source}:{number+1}')
                document.save(path)
            sources.append(inspect_document(path))
        hashes = [hashlib.sha256(info.path.read_bytes()).hexdigest() for info in sources]
        references = tuple((source, number) for number in range(500,0,-1) if number % 5 for source in (1,0))
        plan = build_edit_plan(sources, folder, 'organized', references)
        event = threading.Event()
        try:
            organize_pdf(plan, lambda *_: event.set(), event)
        except Cancelled:
            pass
        else:
            raise AssertionError('Cancellation ignored')
        assert not plan.outputs[0].path.exists()
        started = time.perf_counter()
        organize_pdf(plan)
        elapsed = time.perf_counter()-started
        history = OrderHistory()
        for _ in range(80):
            history.record((references, ''))
        assert len(history.undo_stack) <= 32
        with pymupdf.open(plan.outputs[0].path) as check:
            assert check.page_count == 800
            assert [p.get_text().strip() for p in check] == [f'{source}:{number}' for source,number in references]
        assert hashes == [hashlib.sha256(info.path.read_bytes()).hexdigest() for info in sources]
        report = {'passed':True, 'version':VERSION, 'host':platform.platform(), 'logical_cpus':os.cpu_count(),
                  'affinity_logical_cpus':2, 'input_pages':1000, 'output_pages':800,
                  'export_seconds':round(elapsed,3), 'output_bytes':plan.outputs[0].path.stat().st_size,
                  'counters':counters(os.getpid()), 'cancel_restart':True, 'sources_unchanged':True,
                  'history_entries':len(history.undo_stack), 'history_identity_budget':100000,
                  'limitations':['Synthetic text PDFs; process peak includes fixture creation',
                                 'Not physical 2-core/4-GiB/HDD or Windows11 certification',
                                 'Native insert/delete/save calls must finish before cancellation; no scan/frozen/HDD peak measured']}
    (ROOT/f'docs/organize-resources-{VERSION}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
