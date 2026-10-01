# PDF LoveR development

- Production code lives in `pdf_lover/`. `main.py` only launches the package.
- Keep PDF operations in each feature's `service.py`; engines must import without Tk.
- Keep feature queues, settings and widgets in the feature page. The shell owns navigation, the shared busy state and event polling.
- New pages implement `ToolPage` and register in `features/registry.py`. Mark catalogue tools ready only when their registered page and engine work.
- Shared controls, icons and tokens belong in `ui/`. Windows integration belongs in `platform/`.
- Tk widgets run on the main thread. Workers report through queues. Thumbnail rendering stays in a separate spawned process.
- Read `docs/ARCHITECTURE.md` and `CONTRIBUTING.md` before extending the application.
- Run `python scripts/check.py` for a feature or structural change. UI checks run sequentially on Windows.
- Change the version only in `pdf_lover/version.py`. Build with `packaging/build_release.ps1` and verify with `packaging/verify_distribution.ps1`.
- Generated builds, local logs and build tools stay out of Git. Preserve original documents and existing output when changing PDF operations.
