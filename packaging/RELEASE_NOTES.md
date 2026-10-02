# PDF LoveR 1.7.0 — full document desk redesign

2026-10-02. Full-width task home replaces category sidebar and tall catalogue cards.
All six ready tasks visible at minimum size. Graphite masthead with direct tool switcher
across all six pages; document desk with white sheets and selected footer labels.
Existing services, PDF/DPI, selection, drop and safe publication preserved.
Private local distribution only; no GitHub Release.

# PDF LoveR 1.6.0 — document workbench

2026-10-02 (Asia/Bangkok). Thai text and shared controls enlarged; ready-only home,
document-first workbench, larger page/merge previews and original/result rotation tabs.
Six tools; export fidelity, DPI and no-overwrite behavior retained. Distribution under
`dist/PDF_LoveR_1.6.0/`: EXE, Portable ZIP, Setup and SHA256. No GitHub Release published.
Native Windows 10 development-host evidence does not certify a physical 4-GiB/HDD PC.

# PDF to PNG 1.0.0 — distribution

Build date: 2026-10-01 (Asia/Bangkok).

Shipped files under `dist/Release`:

- `PDF_to_PNG_Portable_1.0.0.exe`: self-contained PyInstaller one-file build.
- `PDF_to_PNG_Portable_Folder_1.0.0.zip`: complete folder build and Thai guide.
- `PDF_to_PNG_Setup_1.0.0.exe`: Inno Setup installer, current-user installation,
  optional desktop shortcut, Start Menu shortcut, and uninstaller.
- `README_เริ่มใช้งาน.txt`: instructions to accompany the distributed files.
- `SHA256SUMS.txt`: hashes of all executable/archive release files.

The installer permits x64-compatible Windows 10 or newer, requests no elevation,
uses the user's local application directory, and does not register a default PDF
handler. The uninstaller tracks installed files and does not recursively delete
the application directory or converted/user-created files.

Build definitions: PDF_to_PNG_Modern.spec, PDF_to_PNG_Portable.spec,
packaging/version_info.txt, and packaging/PDF_to_PNG.iss. Application logic and
design are identical in all three distributions. The folder build uses a staging
directory to avoid replacing the user's running executable.

Compiler: Inno Setup 6.7.3 from the publisher's linked GitHub release. The compiler
download's Authenticode signature validated as Pyrsys B.V. Compiler tooling is
stored under `.build-tools/InnoSetup`, separate from distributed application files.
References: https://jrsoftware.org/isdl.php,
https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm,
https://jrsoftware.org/ishelp/topic_setup_architecturesallowed.htm.

Verification completed on Windows 10 x64:

1. Copied only the standalone EXE to a path containing spaces and Thai characters.
2. Launched it without PYTHONHOME/PYTHONPATH and with a system-only PATH.
3. Constructed the real UI and converted two Thai-named PDF pages to PNG at 150 DPI.
4. Extracted the distributed ZIP and repeated the conversion on its executable.
5. Installed the actual Setup into an isolated directory and repeated the check.
6. Created a simulated user result, uninstalled, and confirmed the executable was
   removed while the user result survived.

All checks passed; details and test log location are in distribution-check.json.
No separate physical Windows 11 machine was available for verification.
