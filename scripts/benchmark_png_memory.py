"""Compare 600-DPI PNG peak memory against the recorded 1.5.1 engine."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_resources import counters


def child(origin):
    import pymupdf
    if origin == 'baseline':
        source = subprocess.check_output(['git','show','fb51da245641bdf75086b3a5176a996224e2eff6:pdf_lover/features/png/service.py'],cwd=ROOT)
        scope = {};exec(compile(source,'baseline-png-service','exec'),scope);convert = scope['convert_pdf']
    else:
        from pdf_lover.features.png.service import convert_pdf as convert
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp);path=folder/'fixture.pdf'
        with pymupdf.open() as doc:
            for i in range(3):doc.new_page().insert_text((72,72),f'Page {i+1}')
            doc.save(path)
        started=time.perf_counter();output=convert(path,folder,600,lambda *args:None)
        elapsed=time.perf_counter()-started
        memory=counters(__import__('os').getpid())
        hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.png'))]
    return {'origin':origin,'elapsed_seconds':round(elapsed,3),
            'peak_working_set_mib':round(memory['peak_working_set_mib'],2),'png_sha256':hashes}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--child',choices=['baseline','current'])
    parser.add_argument('--report',type=Path);parser.add_argument('--runs',type=int,default=5)
    args=parser.parse_args()
    if args.child:print(json.dumps(child(args.child)));return
    if not args.report or args.runs<1:parser.error('--report and positive --runs required')
    runs=[]
    for _ in range(args.runs):
        for origin in ('baseline','current'):
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--child',origin],cwd=ROOT,
                                  capture_output=True,text=True,check=True,timeout=90)
            runs.append(json.loads(result.stdout.strip()))
    assert all(r['png_sha256']==runs[0]['png_sha256'] for r in runs)
    report={'passed':True,'scope':'Windows headless fresh process per run, 3 synthetic text A4 pages at 600 DPI',
            'baseline_commit':'fb51da245641bdf75086b3a5176a996224e2eff6','runs':runs,
            'median_peak_working_set_mib':{o:statistics.median(r['peak_working_set_mib'] for r in runs if r['origin']==o) for o in ('baseline','current')},
            'output_png_hashes_identical':True,'limitations':['Physical 4-GiB/HDD PC not tested','Not a large scan or huge-page workload','Peak working set includes engine/imports']}
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report['median_peak_working_set_mib']))


if __name__=='__main__':main()
