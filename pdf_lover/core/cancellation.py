"""Cooperative cancellation at file-safe boundaries; no GUI dependencies."""
from pdf_lover.core.document import DocumentError


class Cancelled(DocumentError):
    """A requested stop after the current native operation has completed."""

    def __init__(self, message="ยกเลิกงานแล้ว · เก็บต้นฉบับและไฟล์เดิมไว้", output_folder=None):
        super().__init__(message)
        self.output_folder = output_folder


def checkpoint(cancel, output_folder=None):
    if cancel is not None and cancel.is_set():
        message = (f"ยกเลิกงานแล้ว · เก็บภาพที่เขียนเสร็จและ CSV ไว้ที่ {output_folder}"
                   if output_folder is not None else "ยกเลิกงานแล้ว · เก็บต้นฉบับและไฟล์เดิมไว้")
        raise Cancelled(message, output_folder)
