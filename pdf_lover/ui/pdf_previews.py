"""PDF thumbnails in a separate process, away from Tk and its Python GIL.

PyMuPDF explicitly does not support concurrent use from multiple threads.
Only small RGB thumbnails cross the bounded results queue.
"""
from collections import OrderedDict, deque
import multiprocessing as mp
import queue


def render_previews(requests, results):
    import pymupdf
    while True:
        request = requests.get()
        if request is None:
            return
        client, generation, key = request
        try:
            with pymupdf.open(key[0]) as document:
                page = document[key[3] if len(key) > 3 else 0]
                if len(key) > 4:
                    page.set_rotation((page.rotation + key[4]) % 360)
                if len(key) > 7 and key[7] == 'page-numbers':
                    from pdf_lover.features.page_numbers.service import stamp_page
                    stamp_page(page, key[8], key[9])
                width, height = key[5:7] if len(key) > 6 else (224, 144)
                factor = min(width / page.rect.width, height / page.rect.height)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(factor, factor), alpha=False,
                                      colorspace=pymupdf.csRGB)
                payload = (pix.width, pix.height, pix.samples)
                del pix
            results.put((client, generation, key, payload))
        except Exception:
            results.put((client, generation, key, None))


class PreviewCoordinator:
    """UI-thread broker with one bounded spawned renderer and client generations."""
    MAX_REQUESTS = 16

    def __init__(self):
        self.process = None
        self.requests = None
        self.results = None
        self.failed = False
        self.paused = False
        self.clients = {}
        self.outstanding = set()
        self.next_client = 0

    def register(self, client):
        self.next_client += 1
        self.clients[self.next_client] = client
        return self.next_client

    def submit(self, client, key):
        self.pump()
        request = (client.token, client.generation, key)
        if request in self.outstanding:
            return True
        retained = len(self.outstanding) + sum(len(owner.mailbox) for owner in self.clients.values())
        if self.failed or self.paused or not client.active or retained >= self.MAX_REQUESTS:
            return False
        if self.process is None:
            context = mp.get_context("spawn")
            self.requests = context.Queue(maxsize=self.MAX_REQUESTS)
            self.results = context.Queue(maxsize=4)
            self.process = context.Process(target=render_previews, args=(self.requests, self.results),
                                           name="PDF LoveR previews", daemon=True)
            try:
                self.process.start()
            except (OSError, RuntimeError):
                self.failed = True
                self.stop()
                return False
        try:
            self.requests.put_nowait(request)
        except queue.Full:
            return False
        self.outstanding.add(request)
        return True

    def pump(self):
        if self.process is not None and not self.process.is_alive():
            self.failed = True
            for token, generation, key in self.outstanding:
                client = self.clients.get(token)
                if client and client.active and generation == client.generation:
                    client.mailbox.append((key, None))
            self.stop(clear_mailboxes=False)
            return
        if self.results is None:
            return
        try:
            for _ in range(self.MAX_REQUESTS):
                token, generation, key, payload = self.results.get_nowait()
                self.outstanding.discard((token, generation, key))
                client = self.clients.get(token)
                if client and client.active and generation == client.generation and key in client.required:
                    client.mailbox.append((key, payload))
        except queue.Empty:
            pass

    def stop(self, *, clear_mailboxes=True):
        if self.process is not None and self.process.pid is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=0.1)
            if not self.process.is_alive():
                self.process.close()
            else:
                raise RuntimeError("Preview worker did not stop")
        for channel in (self.requests, self.results):
            if channel is not None:
                channel.cancel_join_thread()
                channel.close()
        self.process = self.requests = self.results = None
        self.outstanding.clear()
        if clear_mailboxes:
            for client in self.clients.values():
                client.mailbox.clear()

    def close(self):
        self.stop()


class PreviewWorker:
    """Per-widget facade; all app widgets share the coordinator's child."""
    def __init__(self, coordinator=None):
        self.coordinator = coordinator or PreviewCoordinator()
        self.token = self.coordinator.register(self)
        self.generation = 0
        self.required = frozenset()
        self.mailbox = deque(maxlen=self.coordinator.MAX_REQUESTS)
        self.active = True
        self.closed = False

    @property
    def process(self):
        return None if self.closed else self.coordinator.process

    @property
    def failed(self):
        return self.coordinator.failed

    @failed.setter
    def failed(self, value):
        self.coordinator.failed = value

    def set_required(self, keys):
        required = frozenset(keys)
        if required != self.required:
            self.generation += 1
            self.required = required
            self.mailbox.clear()
            return True
        return False

    def set_active(self, active):
        if self.closed and active:
            self.token = self.coordinator.register(self)
            self.closed = False
        self.active = active
        if active:
            self.coordinator.failed = False
        else:
            self.generation += 1
            self.required = frozenset()
            self.mailbox.clear()

    def submit(self, key):
        return False if self.closed else self.coordinator.submit(self, key)

    def get_nowait(self):
        self.coordinator.pump()
        if not self.mailbox:
            raise queue.Empty
        return self.mailbox.popleft()

    def close(self):
        self.set_active(False)
        self.closed = True
        self.coordinator.clients.pop(self.token, None)
        if not self.coordinator.clients:
            self.coordinator.stop()


class PreviewCache(OrderedDict):
    """Bound estimated raw/PIL/Tk copies as well as entry count."""
    def __init__(self, max_entries, max_bytes, on_evict):
        super().__init__()
        self.max_entries, self.max_bytes, self.on_evict = max_entries, max_bytes, on_evict
        self.costs = {}
        self.resident_bytes = 0

    def __setitem__(self, key, value):
        if key in self:
            self.pop(key)
        if value is None:
            cost = 64
        elif isinstance(value, tuple):
            cost = len(value[2]) * 4
        else:
            cost = value.width * value.height * 3 * 4
        super().__setitem__(key, value)
        self.costs[key] = cost
        self.resident_bytes += cost
        while len(self) > self.max_entries or self.resident_bytes > self.max_bytes:
            self.pop(next(iter(self)))

    def pop(self, key, default=None):
        if key not in self:
            return default
        value = super().pop(key)
        self.resident_bytes -= self.costs.pop(key)
        self.on_evict(key)
        return value

    def clear(self):
        for key in list(self):
            self.pop(key)
