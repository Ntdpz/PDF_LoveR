"""Repeatable Windows source-app resource audit; no extra runtime dependencies."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


class Counters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
        "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def counters(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    handle = kernel.OpenProcess(0x0410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        data = Counters(); data.cb = ctypes.sizeof(data)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(data), data.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            raise ctypes.WinError(ctypes.get_last_error())
        cpu = sum((t.dwHighDateTime << 32) + t.dwLowDateTime for t in times[2:]) / 10_000_000
        return {"private_mib": data.PrivateUsage / 1048576,
                "working_set_mib": data.WorkingSetSize / 1048576,
                "peak_working_set_mib": data.PeakWorkingSetSize / 1048576,
                "cpu_seconds": cpu}
    finally:
        kernel.CloseHandle(handle)


def once(idle_seconds):
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    import customtkinter as ctk
    from pdf_lover.app import App
    from pdf_lover.version import VERSION
    root = ctk.CTk(); errors = []
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    app = App(root); stages = []; gaps = []; timer = None
    def heartbeat(previous=None):
        nonlocal timer
        now = time.perf_counter()
        if previous is not None:
            gaps.append(max(0, (now - previous - 0.02) * 1000))
        timer = root.after(20, lambda: heartbeat(now))
    heartbeat()
    def pump(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update(); time.sleep(0.005)
    def processes():
        found = {}
        for page in app.views.values():
            for attr in ("cards", "selector", "preview"):
                worker = getattr(getattr(page, attr, None), "worker", None)
                process = getattr(worker, "process", None)
                if process is not None and process.is_alive():
                    found[process.pid] = process
        return found
    def sample(label):
        children = processes()
        parts = [counters(os.getpid())] + [counters(pid) for pid in children]
        stages.append({"stage": label, "live_preview_processes": len(children),
                       "total_private_mib": round(sum(p["private_mib"] for p in parts), 2),
                       "parent_private_mib": round(parts[0]["private_mib"], 2),
                       "total_working_set_mib": round(sum(p["working_set_mib"] for p in parts), 2)})
    pump(0.2); startup = (time.perf_counter() - started) * 1000; sample("home")
    import pymupdf
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.pdf"
        with pymupdf.open() as doc:
            for i in range(240):
                doc.new_page().insert_text((72, 72), f"Page {i + 1}")
            doc.save(path)
        for tool in ("pdf-png", "merge", "split", "extract-pages", "delete-pages", "rotate", "organize"):
            app.show_tool(tool); app.active_page.add_paths([path])
            end = time.monotonic() + 20
            while app.busy and time.monotonic() < end:
                pump(0.1)
            assert not app.busy
            pump(2.5); sample(tool)
        app.show_home(); pump(2); sample("home_after_all_tools")
        pids = [os.getpid(), *processes()]
        before = sum(counters(pid)["cpu_seconds"] for pid in pids); cpu_start = time.perf_counter()
        pump(idle_seconds)
        # Workers may intentionally expire while idle; only unchanged process sets qualify.
        current = [os.getpid(), *processes()]
        idle_cpu = None
        if set(pids) == set(current):
            after = sum(counters(pid)["cpu_seconds"] for pid in current)
            idle_cpu = (after - before) / (time.perf_counter() - cpu_start) / os.cpu_count() * 100
        sample("home_idle")
        workers = list(processes().values())
        root.after_cancel(timer); app.close()
        assert not errors, errors
        # App.close closes process objects; retained workers must expose no live process.
        assert not processes()
    gaps.sort()
    return {"version": VERSION, "source_start_including_imports_ms": round(startup, 2),
            "stages": stages, "idle_cpu_percent_of_machine": round(idle_cpu, 3) if idle_cpu is not None else None,
            "heartbeat_lateness_p95_ms": round(gaps[min(len(gaps)-1, int(len(gaps)*.95))], 2),
            "heartbeat_lateness_max_ms": round(max(gaps), 2), "cleanup_passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--idle-seconds", type=float, default=5)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32" or args.runs < 1 or args.idle_seconds <= 0:
        parser.error("Windows, positive runs and idle-seconds required")
    if args.once:
        print(json.dumps(once(args.idle_seconds))); return
    if args.report is None:
        parser.error("--report required")
    runs = []
    for i in range(args.runs):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--once",
                                 "--idle-seconds", str(args.idle_seconds)], cwd=ROOT,
                                capture_output=True, text=True, timeout=120 + args.idle_seconds, check=True)
        runs.append(json.loads(result.stdout.strip().splitlines()[-1]))
        print(f"Resource run {i+1}/{args.runs} complete", flush=True)
    summary = {stage["stage"]: statistics.median(r["stages"][index]["total_private_mib"] for r in runs)
               for index, stage in enumerate(runs[0]["stages"])}
    report = {"schema_version": 1, "passed": True, "scope": "Windows source app, 240-page synthetic text PDF, fresh interpreter per run; cache state uncontrolled",
              "memory_counter": "PrivateUsage; main plus distinct live preview processes",
              "host": {"logical_processors": os.cpu_count(), "platform": sys.getwindowsversion().build},
              "limitations": ["No physical low-spec PC tested", "Source app, not frozen/cold-start proof",
                               "Idle CPU includes 5-ms harness pump; not unattended idle baseline", "No export or large scan fixture"],
              "idle_seconds": args.idle_seconds, "median_private_mib_by_stage": summary, "runs": runs}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
