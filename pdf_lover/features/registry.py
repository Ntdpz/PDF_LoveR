"""Add a feature here when its engine and page are ready to ship."""
from pdf_lover.catalog import TOOLS
from dataclasses import dataclass
from importlib import import_module

@dataclass(frozen=True)
class LazyPageFactory:
    module: str
    class_name: str

    def load(self):
        from pdf_lover.features.base import ToolPage
        page = getattr(import_module(self.module), self.class_name)
        if not issubclass(page, ToolPage) or page.__abstractmethods__:
            raise ValueError(f"Page does not implement ToolPage: {self.class_name}")
        return page

    def __call__(self, parent, app):
        return self.load()(parent, app)


PAGE_FACTORIES = {tool: LazyPageFactory(f"pdf_lover.features.{feature}.page", page)
                  for tool, feature, page in (
                      ("pdf-png", "png", "PngPage"), ("merge", "merge", "MergePage"),
                      ("split", "split", "SplitPage"), ("extract-pages", "extract", "ExtractPage"),
                      ("delete-pages", "delete_pages", "DeletePagesPage"), ("rotate", "rotate", "RotatePage"),
                      ("organize", "organize", "OrganizePage"),
                      ("page-numbers", "page_numbers", "PageNumbersPage"),
                      ("watermark", "watermark", "WatermarkPage"))}


def validate_registry(factories=PAGE_FACTORIES, tools=TOOLS):
    ids = [tool.id for tool in tools]
    if len(ids) != len(set(ids)):
        raise ValueError("Tool IDs must be unique")
    ready = {tool.id for tool in tools if tool.ready}
    if ready != set(factories):
        raise ValueError(f"Ready tools and registered pages differ: {ready ^ set(factories)}")
    if not all(callable(factory) for factory in factories.values()):
        raise ValueError("Page factories must be callable")
