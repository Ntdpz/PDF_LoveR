"""PDF thumbnails in a separate process, away from Tk and its Python GIL.

PyMuPDF explicitly does not support concurrent use from multiple threads.
Only small RGB thumbnails cross the bounded results queue.
"""
import multiprocessing as mp
import queue


def render_previews(requests, results):
    import pymupdf
    while True:
        key = requests.get()
        if key is None:
            return
        try:
            with pymupdf.open(key[0]) as document:
                page = document[key[3] if len(key) > 3 else 0]
                if len(key) > 4:
                    page.set_rotation((page.rotation + key[4]) % 360)
                width, height = key[5:7] if len(key) > 6 else (224, 144)
                factor = min(width / page.rect.width, height / page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False,
                                      colorspace=pymupdf.csRGB)
                payload = (pix.width, pix.height, pix.samples)
            results.put((key, payload))
        except Exception:
            results.put((key, None))


class PreviewWorker:
    """One lazily started process; never wait for PDF work on the UI thread."""
    def __init__(self):
        self.process = None
        self.requests = None
        self.results = None
        self.failed = False

    def submit(self, key):
        if self.failed:
            return False
        if self.process is None:
            context = mp.get_context("spawn")
            self.requests = context.Queue()
            self.results = context.Queue(maxsize=4)
            self.process = context.Process(target=render_previews, args=(self.requests, self.results),
                                           name="PDF LoveR previews", daemon=True)
            try:
                self.process.start()
            except (OSError, RuntimeError):
                self.failed = True
                self.close()
                return False
        if not self.process.is_alive():
            self.failed = True
            return False
        self.requests.put_nowait(key)
        return True

    def get_nowait(self):
        if self.results is None:
            raise queue.Empty
        return self.results.get_nowait()

    def close(self):
        if self.process is not None and self.process.pid is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.2)
            if not self.process.is_alive():
                self.process.close()
        for channel in (self.requests, self.results):
            if channel is not None:
                channel.cancel_join_thread()
                channel.close()
        self.process = self.requests = self.results = None
