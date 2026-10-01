"""Protect extension boundaries and the ready-tool registration contract."""
import subprocess
import sys
import unittest
from pathlib import Path

from pdf_lover.catalog import TOOLS
from pdf_lover.features.base import ToolPage
from pdf_lover.features.registry import PAGE_FACTORIES, validate_registry

ROOT = Path(__file__).resolve().parents[2]


class ArchitectureTests(unittest.TestCase):
    def test_ready_pages_implement_the_feature_contract(self):
        validate_registry()
        for page in PAGE_FACTORIES.values():
            self.assertTrue(issubclass(page, ToolPage))
            self.assertFalse(page.__abstractmethods__)

    def test_missing_page_cannot_be_advertised_as_ready(self):
        with self.assertRaises(ValueError):
            validate_registry({"merge": PAGE_FACTORIES["merge"]})

    def test_unplanned_page_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_registry({**PAGE_FACTORIES, "ocr": object})
        with self.assertRaises(ValueError):
            validate_registry(tools=(*TOOLS, TOOLS[0]))

    def test_pdf_engines_can_run_without_loading_tk(self):
        result = subprocess.run([sys.executable, "-c",
            "import sys; import pdf_lover.features.png.service; "
            "import pdf_lover.features.merge.service; "
            "import pdf_lover.features.split.service; import pdf_lover.core.page_selection; "
            "assert 'tkinter' not in sys.modules; assert 'customtkinter' not in sys.modules"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
