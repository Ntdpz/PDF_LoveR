"""Repeatable native UI / conversion smoke check; writes actual-window previews.

Run from the project root: python tests/ui/verify_png.py
"""
import ctypes
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import customtkinter as ctk
import pymupdf
from PIL import Image, ImageGrab
from pdf_lover.app import App
from pdf_lover.features.png.service import convert_pdf
from pdf_lover.ui.theme import COLORS, export_css

PROJECT = Path(__file__).resolve().parents[2]
ARTIFACTS = PROJECT / "build-verification" / "ui"


def contrast(a, b):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(channels, (0.2126, 0.7152, 0.0722)))
    low, high = sorted((luminance(a), luminance(b)))
    return (high + 0.05) / (low + 0.05)


def screenshot(root, name):
    root.update()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ImageGrab.grab(window=hwnd).save(ARTIFACTS / name)


def pump(root, seconds=0.5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (PROJECT / "tokens.css").write_text(export_css(), encoding="utf-8")
    for ink, paper in (("ink", "paper"), ("muted", "surface"), ("muted", "paper"),
                       ("accent-ink", "accent"), ("graphite-muted", "graphite"),
                       ("success", "surface"), ("error", "surface")):
        value = contrast(COLORS[ink], COLORS[paper])
        assert value >= 4.5, (ink, paper, value)
        print(f"Contrast {ink}/{paper}: {value:.2f}:1")
    assert contrast(COLORS["focus"], COLORS["accent"]) >= 3
    ctk.set_appearance_mode("light")
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    with tempfile.TemporaryDirectory(prefix="pdf-png-design-") as sandbox:
        folder = Path(sandbox)
        document = pymupdf.open()
        for index in range(3):
            page = document.new_page(width=320, height=240)
            page.insert_text((24, 60), f"PDF to PNG - Test page {index + 1}", fontsize=18)
        source = folder / "เอกสารทดสอบ.pdf"
        document.save(source)
        document.close()
        broken = folder / "ไฟล์เสีย.pdf"
        broken.write_bytes(b"not a PDF")

        root = ctk.CTk()
        app = App(root)
        app.show_tool("pdf-png")
        callback_errors = []
        root.report_callback_exception = lambda kind, value, trace: callback_errors.append(str(value))
        root.geometry("1080x780+40+40")
        pump(root)
        screenshot(root, "preview-empty.png")
        app.png.start()
        assert not app.busy and "ยังไม่มี PDF" in app.png.status.get()
        app.png.add_paths([source, source])
        assert len(app.png.files) == 1
        app.png.dpi.set("abc")
        app.png.start()
        assert not app.busy and "DPI ไม่ถูกต้อง" in app.png.status.get()
        app.png.dpi.set("72")
        app.png.output.set("")
        app.png.start()
        assert not app.busy and "ยังไม่มีปลายทาง" in app.png.status.get()
        app.png.output.set(str(folder / "output"))
        app.png.add_paths([broken])
        pump(root)
        screenshot(root, "preview-queue.png")
        app.png.start()
        assert app.busy
        app.png.remove_file(source)
        app.png.add_paths([folder / "ignored.pdf"])
        assert len(app.png.files) == 2
        app.png.start()  # duplicate start is ignored, including the keyboard shortcut.
        pump(root, 0.05)
        deadline = time.monotonic() + 20
        while app.busy and time.monotonic() < deadline:
            pump(root, 0.1)
        assert not app.busy, "Conversion did not finish"
        assert len(app.png.errors) == 1, app.png.errors
        assert app.png.file_states[source] == "เสร็จแล้ว"
        assert app.png.file_states[broken] == "ผิดพลาด"
        images = sorted((folder / "output" / source.stem).glob("*.png"))
        assert len(images) == 3
        assert images[0].name == "เอกสารทดสอบ_page_001.png"
        with Image.open(images[0]) as image:
            assert image.size == (320, 240)
        screenshot(root, "preview-errors.png")

        app.png.remove_file(broken)
        app.png.dpi.set("150")
        app.png.start()
        while app.busy and time.monotonic() < deadline:
            pump(root, 0.1)
        assert not app.busy and not app.png.errors
        assert (folder / "output" / "เอกสารทดสอบ_2").is_dir()
        with Image.open(folder / "output" / "เอกสารทดสอบ_2" / "เอกสารทดสอบ_page_001.png") as image:
            assert image.size == (667, 500)
        screenshot(root, "preview-success.png")
        root.geometry("920x700+40+40")
        pump(root)
        screenshot(root, "preview-compact.png")
        app.png.clear_files()
        assert not app.png.files
        for timer in root.tk.call("after", "info"):
            root.after_cancel(timer)
        root.destroy()
        # Verify startup at 125%, rather than changing scaling on a live window.
        ctk.set_widget_scaling(1.25)
        ctk.set_window_scaling(1.25)
        root = ctk.CTk()
        root.report_callback_exception = lambda kind, value, trace: callback_errors.append(str(value))
        app = App(root)
        app.show_tool("pdf-png")
        root.geometry("1080x780+10+10")
        pump(root)
        screenshot(root, "preview-scaled.png")
        assert not callback_errors, callback_errors
        root.destroy()
    print("PASS: native rendering, 100%/125% scaling, input validation, queue guards,")
    print("mixed success/failure, page progress, ordered PNGs, custom DPI, repeat-folder safety.")


if __name__ == "__main__":
    main()
