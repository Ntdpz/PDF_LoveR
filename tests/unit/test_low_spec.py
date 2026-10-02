"""Verify bounded preview accounting and stale/staged low-spec review rejection."""
import contextlib
import io
import json
from pathlib import Path
import queue
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from unittest.mock import patch
import weakref

from pdf_lover.ui.pdf_previews import PreviewCache, PreviewCoordinator, PreviewWorker
from scripts.check_low_spec import check
from scripts.update_diagrams import digest, snapshot
from scripts import install_hooks
from pdf_lover.features.png.service import convert_pdf


class PreviewBudgetTests(unittest.TestCase):
    def test_byte_budget_evicts_and_clear_releases_accounting(self):
        evicted = []
        cache = PreviewCache(32, 100, evicted.append)
        cache['one'] = (2, 2, b'0' * 12)
        cache['two'] = (2, 2, b'0' * 12)
        cache['three'] = (2, 2, b'0' * 12)
        self.assertEqual(list(cache), ['two', 'three'])
        self.assertEqual(evicted, ['one'])
        self.assertEqual(cache.resident_bytes, 96)
        cache.clear(); self.assertEqual(cache.resident_bytes, 0)

    def pool(self):
        pool = PreviewCoordinator()
        pool.process = SimpleNamespace(is_alive=lambda: True)
        pool.requests = queue.Queue(maxsize=pool.MAX_REQUESTS)
        pool.results = queue.Queue(maxsize=4)
        return pool

    def test_request_limit_and_duplicate_backpressure(self):
        pool = self.pool(); worker = PreviewWorker(pool)
        worker.set_required(range(20))
        for key in range(16):self.assertTrue(worker.submit(key))
        self.assertTrue(worker.submit(0))
        self.assertFalse(worker.submit(17))
        self.assertEqual(len(pool.outstanding), 16)
        pool.paused = True
        self.assertFalse(worker.submit(18))

    def test_stale_generations_and_other_clients_do_not_receive_wrong_image(self):
        pool = self.pool(); a = PreviewWorker(pool); b = PreviewWorker(pool)
        a.set_required(['old']); a.submit('old'); old = a.generation
        a.set_required(['new']); a.submit('new')
        b.set_required(['other']); b.submit('other')
        pool.results.put((a.token, old, 'old', 'stale'))
        pool.results.put((b.token, b.generation, 'other', 'B'))
        pool.results.put((a.token, a.generation, 'new', 'A'))
        self.assertEqual(a.get_nowait(), ('new', 'A'))
        self.assertEqual(b.get_nowait(), ('other', 'B'))
        self.assertFalse(pool.outstanding)
        with self.assertRaises(queue.Empty):a.get_nowait()

    def test_undelivered_replies_count_toward_budget_and_cannot_drop_valid_result(self):
        pool=self.pool();worker=PreviewWorker(pool);worker.set_required(range(20))
        for key in range(16):worker.mailbox.append((key,'ready'))
        self.assertFalse(worker.submit(17))
        self.assertEqual(worker.get_nowait(),(0,'ready'))
        self.assertTrue(worker.submit(17))
        pool.results.put((worker.token,worker.generation,17,'new'))
        pool.pump()
        self.assertEqual(list(worker.mailbox),[(key,'ready') for key in range(1,16)]+[(17,'new')])

    def test_closing_one_facade_keeps_shared_child_until_last_client(self):
        pool = self.pool(); pool.stop = Mock()
        a = PreviewWorker(pool); b = PreviewWorker(pool)
        a.close(); pool.stop.assert_not_called()
        self.assertIsNone(a.process)
        self.assertIs(b.process, pool.process)
        b.close(); pool.stop.assert_called_once()


class LowSpecGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'pdf_lover').mkdir(); (self.root/'docs').mkdir()
        (self.root/'pdf_lover/app.py').write_text('cache_limit = 16\n')
        self.evidence = self.root/'docs/performance.json'
        self.evidence.write_text('{"passed": true}')
        self.review = {'schema_version': 1, 'decision': 'accepted',
                       'target': {'cpu_cores': 2, 'ram_gib': 4, 'disk': 'HDD'},
                       'impact': {k: 'Bounded resource use reviewed and checked.' for k in
                                  ('memory','cpu_ui','disk_startup','dependencies','output_quality')},
                       'limitations': ['Physical low-spec hardware not tested'],
                       'evidence': [{'path':'docs/performance.json','sha256':digest(self.evidence.read_bytes())}],
                       'source_files': snapshot(self.root)}
        self.path = self.root/'docs/low-spec-review.json'; self.write()

    def write(self):self.path.write_text(json.dumps(self.review))
    def result(self, staged=False):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check(self.root, staged)

    def test_changed_source_requires_new_review(self):
        self.assertEqual(self.result(), 0)
        (self.root/'pdf_lover/app.py').write_text('cache_limit = 10000\n')
        self.assertEqual(self.result(), 1)

    def test_missing_category_or_changed_evidence_is_rejected(self):
        self.review['impact'].pop('memory'); self.write(); self.assertEqual(self.result(), 1)
        self.review['impact']['memory'] = 'Bounded memory has been reviewed.'; self.write()
        self.evidence.write_text('{"passed": false}'); self.assertEqual(self.result(), 1)

    def test_staged_review_is_required_even_if_worktree_review_is_fresh(self):
        def git(*args):subprocess.run(['git',*args],cwd=self.root,capture_output=True,check=True)
        git('init','-q');git('add','.')
        self.assertEqual(self.result(staged=True), 0)
        (self.root/'pdf_lover/app.py').write_text('cache_limit = 24\n');git('add','pdf_lover/app.py')
        self.review['source_files'] = snapshot(self.root);self.write()
        self.assertEqual(self.result(), 0)
        self.assertEqual(self.result(staged=True), 1)
        git('add','docs/low-spec-review.json');self.assertEqual(self.result(staged=True), 0)


class WorkerLifetimeAndHookTests(unittest.TestCase):
    def test_previous_png_pixmap_is_released_before_next_render(self):
        previous = []
        class Pixmap:
            def save(self, path):pass
        class Page:
            def get_pixmap(self, **kwargs):
                if previous and previous[0]() is not None:
                    raise AssertionError('Previous full-page Pixmap still alive')
                image = Pixmap();previous[:] = [weakref.ref(image)];return image
        doc = Mock();doc.page_count = 3
        doc.__enter__ = Mock(return_value=doc);doc.__exit__ = Mock(return_value=False)
        doc.__iter__ = Mock(return_value=iter([Page(),Page(),Page()]))
        with tempfile.TemporaryDirectory() as tmp, patch('pdf_lover.features.png.service.pymupdf.open',return_value=doc):
            convert_pdf(Path(tmp)/'fixture.pdf',Path(tmp),600,lambda *args:None)
        self.assertIsNone(previous[0]())

    def test_installer_updates_only_known_managed_legacy_and_preserves_custom_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);subprocess.run(['git','init','-q'],cwd=root,check=True,capture_output=True)
            (root/'.githooks').mkdir();source=(Path(__file__).resolve().parents[2]/'.githooks/pre-commit').read_bytes()
            (root/'.githooks/pre-commit').write_bytes(source);target=root/'.git/hooks/pre-commit'
            target.write_bytes(install_hooks.LEGACY)
            with patch.object(install_hooks,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):install_hooks.main()
            self.assertEqual(target.read_bytes(),source)
            target.write_bytes(b'#!/bin/sh\necho custom\n')
            with patch.object(install_hooks,'ROOT',root),self.assertRaises(SystemExit):install_hooks.main()
            self.assertEqual(target.read_bytes(),b'#!/bin/sh\necho custom\n')


if __name__ == '__main__':unittest.main()
