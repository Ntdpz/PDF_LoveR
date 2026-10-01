"""Exercise stale and partially staged documentation in isolated workspaces."""
import contextlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.update_diagrams import SPECS, check, digest, snapshot


class DiagramGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "pdf_lover").mkdir()
        (self.root / "pdf_lover/app.py").write_bytes(b"route = 'home'\n")
        folder = self.root / "docs/diagrams"
        folder.mkdir(parents=True)
        records = []
        for name, kind in SPECS.items():
            item = {"name": name}
            for field, filename, content in (
                ("specification", f"{name}.{kind}.json", b"{}\n"),
                ("artifact", f"{name}.html", b"<html></html>\n")):
                path = folder / filename
                path.write_bytes(content)
                item[field] = {"path": path.relative_to(self.root).as_posix(), "canonical_sha256": digest(content)}
            records.append(item)
        (folder / "manifest.json").write_text(json.dumps({"source_files": snapshot(self.root), "diagrams": records}), encoding="utf-8")

    def result(self, staged=False):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return check(self.root, staged)

    def test_new_feature_cannot_keep_old_manifest(self):
        self.assertEqual(self.result(), 0)
        (self.root / "pdf_lover/new_feature.py").write_bytes(b"def new_tool(): pass\n")
        self.assertEqual(self.result(), 1)

    def test_changed_function_requires_refresh(self):
        (self.root / "pdf_lover/app.py").write_bytes(b"route = 'merge'\n")
        self.assertEqual(self.result(), 1)

    def test_tampered_specification_or_html_fails(self):
        for filename in ("application.architecture.json", "processing.html"):
            with self.subTest(filename=filename):
                path = self.root / "docs/diagrams" / filename
                original = path.read_bytes()
                path.write_bytes(original + b"changed\n")
                self.assertEqual(self.result(), 1)
                path.write_bytes(original)

    def test_git_line_endings_do_not_invalidate_review(self):
        (self.root / "pdf_lover/app.py").write_bytes(b"route = 'home'\r\n")
        self.assertEqual(self.result(), 0)

    @unittest.skipUnless(shutil.which("git"), "Git needed for staged-index verification")
    def test_index_is_checked_even_when_worktree_evidence_is_current(self):
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        git("init", "-q")
        git("add", ".")
        self.assertEqual(self.result(staged=True), 0)
        (self.root / "pdf_lover/app.py").write_bytes(b"route = 'merge'\n")
        git("add", "pdf_lover/app.py")
        manifest_path = self.root / "docs/diagrams/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source_files"] = snapshot(self.root)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(self.result(), 0)
        self.assertEqual(self.result(staged=True), 1)
        git("add", "docs/diagrams/manifest.json")
        self.assertEqual(self.result(staged=True), 0)


if __name__ == "__main__":
    unittest.main()
