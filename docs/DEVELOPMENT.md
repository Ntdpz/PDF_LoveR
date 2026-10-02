# Development

The Windows distributions include their own runtime. These instructions are for
maintaining the source and producing builds.

## Set up and run

Use Python 3.10+ on Windows:

```powershell
git clone git@github.com:Ntdpz/PDF_LoveR.git
cd PDF_LoveR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pdf_lover
```

`python main.py` and the installed `pdf-lover` command use the same entrypoint.
`requirements.txt` remains an editable-install convenience; runtime dependencies
are declared once in `pyproject.toml`. No API keys or network services are needed
to run the application.

## Find the code

Read [Architecture](ARCHITECTURE.md) for the folder map, ownership and runtime
flow, and [Contributing](../CONTRIBUTING.md) before adding a feature.

- `pdf_lover/app.py`: navigation, shared busy state and event dispatch.
- `pdf_lover/features/`: one folder per tool, containing its page and PDF engine.
- `pdf_lover/ui/`: home, shared controls, icons and theme tokens.
- `pdf_lover/platform/`: Documents lookup and native Explorer drops.
- `pdf_lover/catalog.py` and `features/registry.py`: tool descriptions and executable pages.
- `pdf_lover/diagnostics/`: hidden packaged smoke check.
- `tests/unit/` and `tests/ui/`: engine and native interaction checks.
- `packaging/`: specs, metadata, installer, build and distribution verification.

## Verify source changes

```powershell
python scripts/check.py
```

This runs unit tests followed by Windows UI checks sequentially. Use
`python scripts/check.py --unit-only` for engine-only checks or a host without
Windows UI. The native merge fidelity check requires Poppler `pdftoppm` in PATH.

Individual checks can be run directly:

```powershell
python -m unittest discover -s tests/unit -v
python tests/ui/verify_png.py
python tests/ui/verify_home.py
python tests/ui/verify_merge.py
python tests/ui/verify_merge_cards.py
python tests/ui/verify_file_drop.py
python tests/ui/verify_drag_performance.py
python tests/ui/verify_split.py
python tests/ui/verify_page_tools.py
python tests/ui/verify_rotate.py
python tests/ui/verify_resources.py
python tests/ui/verify_selector.py
```

Fixtures and output use temporary directories. Native checks cover real PNG
conversion, page order, forms, links, annotations, source/output safety, corrupt
files, queue and navigation guards, file drops, desktop scaling and drag load.
Architecture checks protect ready-tool registration and verify that PDF engines
can import without loading Tk. PNG engine checks also preserve existing output
on repeat conversion.

Reports are stored in `docs/`; local UI captures and scratch work go into
`build-verification/`. UI checks drive Windows TkDnD adapter callbacks rather
than automating Explorer's physical mouse gesture.

## Build and verify distributions

Install the optional build dependencies and Inno Setup:

```powershell
python -m pip install -e '.[build]'
& .\packaging\build_release.ps1 -InnoCompiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
& .\packaging\verify_distribution.ps1
```

Use PowerShell 7 for distribution verification. `packaging/spec_common.py`
provides the shared analysis options; `folder.spec` and `portable.spec` select
folder and standalone packaging. The assets are packaged under `pdf_lover/assets/`.
TkDnD's native files are included in both builds.

The single EXE extracts its runtime into a temporary directory. The ZIP contains
the runtime alongside the executable. Inno Setup packages the folder build.
All final files go into `dist/PDF_LoveR_<VERSION>/`; staging uses `build-release*`
and `build-portable*` separately.

Verification copies the EXE into an isolated Thai-named path, extracts the exact
ZIP and installs into a test directory. Each executable runs without Python in
PATH and performs native file drops, conversion, merging, splitting, extraction, deletion, rotation and shared thumbnail rendering.
It then uninstalls and verifies that user-created output survives. Local logs
are ignored; sanitized records are kept in `docs/`.

Current record: [distribution-1.7.0.json](distribution-1.7.0.json). Tests run on
Windows 10 x64; a separate Windows 11 machine has not been used. Installers are
unsigned.

## Version and assets

Edit only `pdf_lover/version.py`. Package metadata, UI and Windows filenames read
that source. `prepare_version.py` generates the Windows metadata and Inno
version definitions. Current outputs are `PDF_LoveR_1.7.0.exe`,
`PDF_LoveR_1.7.0_Setup.exe` and `PDF_LoveR_1.7.0_Portable.zip`.

Keep binaries, build tools and local logs outside Git. Recompute hashes when
rebuilding an asset. GitHub Release 1.0.0 remains the older PNG application;
current development builds are local until a new Release is explicitly published.

## Responsiveness

The merge page uses one virtualized Canvas, coalesces pointer motion into 16 ms
frames and updates only affected highlights during drag. Thumbnails come from
one lazily started child process; image application pauses during dragging.
Lift and insertion-marker animations follow Windows' reduced-animation setting.
The 100-file load check covers rapid pointer events, edge scrolling, Tk heartbeat,
preview pause/resume and worker cleanup. See
[drag-performance-1.7.0.json](drag-performance-1.7.0.json). Timings describe the
test machine rather than every document or PC.

Split evidence: [split-verification.json](split-verification.json). The suite now has 79 unit tests and thirteen sequential native UI checks.

Low-spec policy and the staged evidence guard are documented in AGENTS.md and
[Contributing](../CONTRIBUTING.md). Reproduce source memory measurements with
`python scripts/benchmark_resources.py --runs 5 --report <path.json>` and PNG
peak comparison with `python scripts/benchmark_png_memory.py --runs 5 --report <path.json>`.
Review hardware/workload limitations before interpreting results; no physical
4-GiB/HDD PC or Windows 11 machine has been certified by these source checks.
