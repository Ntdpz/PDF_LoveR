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

## Architecture update hook (required for agents)

- Before changing code, read `docs/DIAGRAMS.md` and inspect the three JSON sources in `docs/diagrams/`.
- After adding or changing functions, feature readiness, routing, threads/queues, file handling, dependencies, tests or packaging, review the diagrams against the resulting code. Update the affected JSON nodes, relationships and explanatory cards, and `docs/ARCHITECTURE.md` as needed. Never show planned catalogue tools as implemented.
- Run `python scripts/update_diagrams.py --visual-check`. Archify must pass 9/9 showcase checks with zero composition errors/warnings. Inspect the generated light/dark screenshots; browser evidence is not perceptual approval.
- Even when a change does not alter topology, review it and refresh the manifest. Hash freshness proves a review checkpoint, not semantic correctness. Never hand-edit the manifest or just refresh hashes to hide a stale explanation.
- Run `python scripts/check.py`, then stage code, JSON, generated HTML, delivery receipts and manifest together. Before committing run `python scripts/update_diagrams.py --check --staged`.
- Install the staged-content guard on a new checkout with `python scripts/install_hooks.py`. Preserve other hooks. This is a repository workflow hook, not an undocumented Codex event API.
- Generated caches/build work can be cleaned with `python scripts/clean_workspace.py --apply`; inspect its dry run first. Keep `dist/`, `.build-tools/`, editable package metadata, original documents and verified documentation.

## Low-spec PC review hook (required for every update)

- Before any update, consider CPU 2 cores, RAM 4 GiB and HDD as the design target. Read `docs/PERFORMANCE_PLAN.md`; keep hardware assumptions distinct from measured support.
- Review RAM/worker/cache/queue limits, CPU and Tk responsiveness, disk/startup cost, added dependencies, and output quality. Keep export concurrency at one by default, reuse the app's single preview coordinator, and release hidden preview resources while preserving user settings/documents.
- Never load/render all pages in advance, add unbounded queues/caches, block Tk with PDF work, or silently reduce the user's DPI/quality to meet a budget. Preserve drag virtualization, worker cleanup and original/output-file safety.
- For runtime/structural/test/dependency/packaging changes, run relevant resource and interaction checks before final acceptance. Record hardware, workloads, before/after results and limitations; CPU affinity tests do not certify a physical 4 GiB/HDD machine.
- Maintain `docs/low-spec-review.json`: describe each impact category, reference passed JSON evidence with canonical SHA256, and bind `source_files` to the resulting source snapshot from `scripts.update_diagrams.snapshot()`. This is a reviewed record, not an automatic declaration of low-spec compatibility. Refresh it only after reviewing and checking the actual change.
- `python scripts/check_low_spec.py` checks working evidence. Before committing, stage the review and its evidence together and run `python scripts/check_low_spec.py --staged`. The pre-commit hook checks both this record and diagram freshness against the staged index; it cannot prove human thought or untested hardware support.
- Documentation-only changes outside the watched source may retain the current source review; still describe new requirements truthfully. AGENTS/architecture and code/packaging/test changes require renewed source review. Update the existing managed hook using `scripts/install_hooks.py`; preserve unrelated custom hooks.
