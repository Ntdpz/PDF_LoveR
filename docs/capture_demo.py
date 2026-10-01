"""Capture the real app with generated sample PDFs, without user documents."""
import ctypes
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import customtkinter as ctk
import pymupdf
from PIL import ImageGrab
import pdf_to_png

IMAGES = Path(__file__).resolve().parent / "images"


def capture(root):
    root.state("normal")
    root.geometry("1080x780+40+40")
    root.update()
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    shot = ImageGrab.grab(window=hwnd).convert("RGB")
    assert shot.size == (1080, 780), shot.size
    return shot


def pump(root, seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.02)


def main():
    ctk.set_appearance_mode("light")
    ctk.set_widget_scaling(1)
    ctk.set_window_scaling(1)
    original_convert = pdf_to_png.convert_pdf

    def paced_convert(path, destination, dpi, progress):
        def page_done(page, total):
            progress(page, total)
            time.sleep(0.22)
        return original_convert(path, destination, dpi, page_done)

    pdf_to_png.convert_pdf = paced_convert
    frames, durations = [], []
    previous_directory = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="pdf-lover-demo-") as sandbox:
        os.chdir(sandbox)
        for name in ("Project Brief.pdf", "Product Guide.pdf"):
            with pymupdf.open() as document:
                for index in range(6):
                    page = document.new_page(width=300, height=200)
                    page.insert_text((24, 48), name.removesuffix(".pdf"), fontsize=20)
                    page.insert_text((24, 80), f"Sample page {index + 1}", fontsize=12)
                document.save(name)
        root = ctk.CTk()
        app = pdf_to_png.App(root)
        app.show_tool("pdf-png")
        root.geometry("1080x780+40+40")
        root.resizable(False, False)
        app.output.set("PNG")
        pump(root)
        empty = capture(root)
        empty.save(IMAGES / "app-overview.png")
        frames.append(empty); durations.append(1000)
        app.add_paths(["Project Brief.pdf", "Product Guide.pdf"])
        pump(root)
        queue = capture(root)
        queue.save(IMAGES / "app-queue.png")
        frames.append(queue); durations.append(1500)
        app.start()
        while app.busy:
            pump(root, 0.4)
            frames.append(capture(root)); durations.append(400)
        pump(root)
        complete = capture(root)
        complete.save(IMAGES / "app-complete.png")
        frames.append(complete); durations.append(2200)
        assert not app.errors
        assert len(list(Path("PNG").rglob("*.png"))) == 12
        for timer in root.tk.call("after", "info"):
            root.after_cancel(timer)
        root.destroy()
        os.chdir(previous_directory)
    frames[0].save(IMAGES / "workflow.gif", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    print(f"Captured real workflow: {len(frames)} frames; two sample PDFs, twelve output pages.")


if __name__ == "__main__":
    main()
