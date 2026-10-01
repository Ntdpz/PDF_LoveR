"""Add a feature here when its engine and page are ready to ship."""
from pdf_lover.catalog import TOOLS
from pdf_lover.features.merge.page import MergePage
from pdf_lover.features.png.page import PngPage
from pdf_lover.features.split.page import SplitPage

PAGE_FACTORIES = {"pdf-png": PngPage, "merge": MergePage, "split": SplitPage}


def validate_registry(factories=PAGE_FACTORIES, tools=TOOLS):
    ids = [tool.id for tool in tools]
    if len(ids) != len(set(ids)):
        raise ValueError("Tool IDs must be unique")
    ready = {tool.id for tool in tools if tool.ready}
    if ready != set(factories):
        raise ValueError(f"Ready tools and registered pages differ: {ready ^ set(factories)}")
