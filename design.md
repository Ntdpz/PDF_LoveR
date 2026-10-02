# Design — PDF LoveR

Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4.

## Intent and native adaptation

This Windows document workspace prioritizes page inspection over decoration.
Genre: modern-minimal. Theme: Cobalt document desk with graphite masthead. Home is a full-width task desk with all six ready tasks visible at minimum size;
tools use a Workbench with a document viewport, review/settings rail and persistent
save actions at the bottom right. Native Tk layout replaces web CSS grid, ARIA,
mobile breakpoints and browser navigation patterns. Desktop scope is 920×700 and
larger at 100%/125%; no mobile-support claim. No added animation or dependency.

## Typography and tokens

Runtime source: `pdf_lover/ui/theme.py`; portable export: `tokens.css`.
Segoe UI is the Latin wordmark; Leelawadee UI is Thai body/headings, installed with
Windows. Body 18 logical px; helper/status 16; bold section 20; tool title 25.
Roman headings, left aligned Thai text, no light-weight text. Spacing uses named
4/8/12/16/24/32/40 px tokens. Controls and adjacent inputs are 44 logical px high.
Borders maintain their thickness during focus/error. Instant visible focus and
keyboard Return/Space activation use the existing shared controls.

## Layout and behavior

- Home replaces the category sidebar and large catalogue cards with compact task rows, a document start area, search and category dropdown. It initially shows only the six registered tools. The explicit catalogue toggle
  exposes planned tools with “ยังไม่พร้อมใช้” and a details action; no runnable CTA.
  Remove the duplicate PNG spotlight so other ready tools appear sooner.
- Split/extract/delete: responsive vertical page grid at left. Form options scroll
  independently at right while output names/page mapping and pagination stay visible.
  Shared `ui/workbench.py` composes existing ToolPage widgets and callbacks.
- Rotate: left page grid; right scrollable review rail with quarter-turn icon commands,
  large original/result tabs, filenames, suffix and destination. At narrow widths show
  one actual image at a time; wide comparison widgets can show both. No fake preview.
- PNG: document queue, DPI/output form and predictable naming remain together.
  Merge: larger first-page cards; remove duplicate reorder footer and put queue actions
  beside “เพิ่ม PDF”. Preserve the virtual Canvas and drag behavior.
- Status explains invalid/loading/error/success states using text as well as color.
  Save remains unavailable for known invalid plans; completed output can be opened.

## Resources and safety

Selector renders 180×200 fit previews only for viewport cards (at most 24), with
32 entries/6 MiB estimated cache. Comparison requests 320×400 fit, pending at most
two and cache 12 entries/6 MiB. Merge reuses its existing render keys and 48-entry/
16 MiB cache. App owns one renderer, request cap 16/result cap 4. Hidden previews
release images/timers while retaining documents and choices. PDF services, DPI,
publication/no-overwrite and worker/Tk boundaries stay intact. These preview sizes
describe navigation/review images, not export resolution or a zoom viewer.

## Validation

Native geometry and screenshots at 920×700, 1080×780 and 1440×900 at both scales,
plus engine fidelity, keyboard/gestures, resource/drag and distribution checks.
Hallmark web-only gates are inapplicable to the native app; do not report 58/58 web
compliance. Existing color contrast is measured by `verify_png.py`.
Physical 2-core/4-GiB/HDD support remains unverified.

## Full rebuild 1.7.0

User rejected 1.6.0 as too similar. Replace page chrome with one graphite masthead and direct ready-tool switcher on all six pages. Full-width home compact task rows show all six tasks at 920×700; category discovery moves into dropdown. Document canvas is a graphite desk with white sheets and selected footer labels. No new runtime dependency or preview worker. Existing ownership/engines unchanged.
