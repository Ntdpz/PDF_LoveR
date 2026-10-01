# Adding and maintaining tools

Set up the source environment and verification tools as described in
[Development](docs/DEVELOPMENT.md). The application structure is documented in
[Architecture](docs/ARCHITECTURE.md).

## Add a feature

1. Create `pdf_lover/features/<feature>/` with `__init__.py`, `service.py` and `page.py`.
2. Put PDF operations in `service.py`. Accept paths and explicit settings; return results or report progress. Do not import Tk, a page or the application shell.
3. Implement a page derived from `ToolPage`. It must provide `add_files()`, `add_paths(paths)`, `start()` and `process_events()`, plus a `status` variable and an `add_button` for keyboard focus.
4. Keep the page's queue and settings on that page. Use `self.busy` for the shell's shared processing guard. Disable controls during work and restore them on success and failure.
5. Register the page factory in `pdf_lover/features/registry.py` and update the corresponding catalogue entry in `pdf_lover/catalog.py`. Registry validation rejects missing pages, duplicate IDs and ready-state mismatches.
6. Add engine checks under `tests/unit/` and native interaction checks under `tests/ui/`. Check output fidelity, invalid inputs, existing-file safety and cancellation where relevant.
7. Run `python scripts/check.py`, update user-facing capability/limitation documentation, and verify the packaged EXE, ZIP and installer after building.

The shell dispatches keyboard shortcuts, file drops and queued events through
the registered page. Pages are created on first use and retained. Avoid loading
large optional backends when importing a page module. Feature-specific UI belongs on the page; adding a normal
tool should not require new branches in navigation or the drop handler.

## Shared changes

Use `ui/controls.py`, `ui/icons.py` and `ui/theme.py` for reusable UI behavior.
Follow the existing named colors, fonts and spacing. Windows path lookup and
Explorer integration live in `platform/`.

Keep Tk updates on the main thread. PDF work can run in the feature's worker;
report progress and completion using its queue. PyMuPDF thumbnail rendering uses
a separate process, with small bounded results. Preserve the launcher's early
`multiprocessing.freeze_support()` call when changing entrypoints.

## Releases

Update `pdf_lover/version.py`; the package metadata, UI and Windows filenames
read that single source. Run the build and distribution verification scripts,
then record sanitized results in `docs/`. Keep binary distributions in
`dist/PDF_LoveR_<VERSION>/` and outside Git.
