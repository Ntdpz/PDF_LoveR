# Development

The downloadable Windows builds include their own Python runtime. The tools below
are needed only to work on the source or create a new distribution.

## Run from source

Use Python 3.10+ on Windows:

```powershell
git clone git@github.com:Ntdpz/PDF_LoveR.git
cd PDF_LoveR
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python pdf_to_png.py
```

No API keys, account, network service, database, or environment configuration is
required by the application.

## Source map

| File | Purpose |
| --- | --- |
| `pdf_to_png.py` | PDF rendering, file queue, native UI, worker events |
| `home_page.py` | Tool discovery, category filters, planned-tool details |
| `tool_catalog.py` | Single directory of tool names, search terms and readiness |
| `app_version.py` | Single version source for UI, filenames and Windows metadata |
| `pdf_preview.py` | Bounded thumbnail results from a dedicated process, away from Tk and merge workers |
| `merge_cards.py` | Responsive document cards, previews, drag ordering and edge scrolling |
| `merge_page.py` | Merge queue, file ordering, output selection and worker feedback |
| `pdf_merge.py` | Page concatenation, source validation and exclusive output publication |
| `ui_theme.py` | OKLCH color tokens, native fonts, spacing, portable CSS export |
| `app_self_test.py` | Hidden executable smoke check |
| `assets/pdf_to_png.ico` | Window and executable icon |
| `PDF_to_PNG_Modern.spec` | Complete folder distribution |
| `PDF_to_PNG_Portable.spec` | Standalone executable distribution |
| `packaging/PDF_to_PNG.iss` | Installer and uninstaller configuration |
| `packaging/build_release.ps1` | Build installer, standalone EXE, ZIP, and hashes |
| `packaging/verify_distribution.ps1` | Check real distributions and uninstall behavior |

The main thread owns all Tk widgets. A worker renders pages with PyMuPDF and sends
queue events back to the UI. Each PDF gets a new output folder; an existing folder
name receives a numeric suffix. The development app also concatenates PDFs with
the merge tool. It does not yet edit PDFs, run OCR, or export Office formats.

## Build for Windows

Install PyInstaller and Inno Setup 6.3+ (6.7.3 was used for version 1.0.0).

```powershell
python -m pip install pyinstaller
& .\packaging\build_release.ps1 -InnoCompiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

Distributions are written to `dist/PDF_LoveR_<VERSION>/`. Folder-build staging is separate
from `dist/PDF_to_PNG_Modern/` so an existing open app can keep running.
The single EXE extracts its packaged runtime into a temporary directory while
running; the ZIP contains the runtime alongside the application.

## Verify

```powershell
python .hallmark/verify_ui.py
python .hallmark/verify_home.py
python -m unittest discover -s tests -v
python .hallmark/verify_merge.py
python tests/verify_merge_cards.py
python tests/verify_drag_performance.py
```

This runs real PDF conversion and checks input validation, queue guards, corrupt
files, page order, DPI dimensions, repeat conversion, UI rendering and contrast.
The temporary PDF fixtures and converted files are created by the test.

The home check also verifies tool discovery, planned-feature safety, navigation,
retained settings, conversion through the home screen, and desktop scaling.
See [Superapp home](SUPERAPP.md) for the current development preview and roadmap.
The [merge tool](MERGE.md) check also compares output pages with originals using
Poppler. Its unit tests cover forms, annotations, links, bookmarks, source safety,
invalid documents, write failures and a file appearing during publication.

Run distribution verification with **PowerShell 7** after building:

```powershell
& .\packaging\verify_distribution.ps1
```

The script copies the standalone EXE to an isolated Thai-named path, extracts the
distributed ZIP, installs into a test directory, and runs each executable with
Python removed from PATH. It then uninstalls and checks that user-created output
survives. Logs are local and ignored by Git. A sanitized record of the verified
1.0.0 builds is available in [verification.json](verification.json).
The current 1.1.1 record is [distribution-1.1.1.json](distribution-1.1.1.json).

The original packaged tests passed on Windows 10 x64. A separate Windows 11
machine has not been used for verification. The Windows installers are unsigned.

Versioned filenames come from `app_version.py`: `PDF_LoveR_1.1.1.exe`,
`PDF_LoveR_1.1.1_Setup.exe`, and `PDF_LoveR_1.1.1_Portable.zip`.
`prepare_version.py` generates the matching EXE metadata and Inno definitions.

## Release files

Publish the files from `dist/PDF_LoveR_<VERSION>/` as GitHub Release assets, rather than
committing generated EXEs, DLLs, build tools or test logs to the repository.
Recompute `SHA256SUMS.txt` whenever an asset is rebuilt or renamed. The repository
README links to the release assets by their exact names.

## Drag responsiveness (1.1.1)

Pointer events are coalesced into one update per 16 ms. Drop hit testing uses a
cached row/column geometry rather than reading every card's Tk coordinates.
Only cards whose highlight changes are painted. Dropping only updates changed
positions and numbers; cached thumbnails and filenames are kept.

Thumbnail generation uses one lazily started spawned process with a bounded
results queue. Tk image application is limited to two previews per poll and is
paused while dragging. `freeze_support()` runs before GUI imports in packaged
apps. The hidden executable check waits for two actual thumbnail results.

This follows [PyMuPDF's concurrency guidance](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html)
and [PyInstaller's multiprocessing setup](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing).
The 100-card test checks repaint bounds, a native event-loop heartbeat, release
before a frame runs, preview resumption and cleanup. Timings in
[drag-performance-1.1.1.json](drag-performance-1.1.1.json) are measurements on the
test machine, not a guarantee for every computer or document.
