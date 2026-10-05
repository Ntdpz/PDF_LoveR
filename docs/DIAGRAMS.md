# แผนภาพการทำงานของ PDF LoveR

เปิด HTML โดยตรงในเบราว์เซอร์ ไม่ต้องติดตั้ง Archify เพื่ออ่าน สามารถค้นหา
ซูม เลือกองค์ประกอบ ดูเส้นทาง และสลับธีมได้ เนื้อหาเป็นภาษาไทย;
เมนูของ viewer และ `<html lang>` ใช้ภาษาอังกฤษตามความสามารถของ Archify รุ่นนี้

| แผนภาพ | อธิบาย |
|---|---|
| [โครงสร้างโปรแกรม](diagrams/application.html) | launcher, App, home, registry, หน้าฟีเจอร์, UI ร่วม, Windows, services, cards และ process ภาพตัวอย่าง |
| [จากเอกสารถึงผลลัพธ์](diagrams/processing.html) | รับไฟล์, ตรวจข้อมูล, busy guard, worker, queue, การบันทึก, ข้อผิดพลาด และคืนสถานะหน้าจอ |
| [พัฒนาและสร้างชุดแจก](diagrams/maintenance.html) | เพิ่มฟีเจอร์, อัปเดตเอกสาร, hook, การทดสอบ, version, EXE, ZIP และ installer |

## รายละเอียดที่ต้องรักษาเมื่อพัฒนา

- เริ่มผ่าน `__main__.py` ซึ่งเรียก `multiprocessing.freeze_support()` ก่อนโหลด Tk;
  home แสดงเครื่องมือใน `catalog.py` แต่มี PDF to Image รวม PDF แยก PDF แยกหน้า ลบหน้าออก และหมุน PDF ที่พร้อมใช้
- `registry.py` ตรวจ ready IDs; App สร้าง page เมื่อเปิดครั้งแรกและเก็บไว้
  การนำทางและเปลี่ยนรายการถูกป้องกันระหว่าง busy; ปิดโปรแกรมต้องรอจบงาน
- เลือกไฟล์หรือรับ native TkDnD ผ่าน `accept_paths()`; drop บน home เปิดรวม PDF,
  Ctrl+O บน home เปิด PDF to Image; ปลายทางเริ่มที่ Windows Documents
- รวม PDF ใช้ Canvas แสดงเฉพาะแถวใกล้ viewport, รวม pointer input เป็นเฟรม 16 ms,
  มี edge scroll, keyboard และ Esc; พักการอัปเดต thumbnail ระหว่างลาก
- App เป็นเจ้าของ spawned preview process ร่วมหนึ่งตัว; request จำกัด 16 และ result จำกัด 4
  ใช้ client/generation เพื่อทิ้งภาพเก่า; ซ่อนหน้าแล้วคืน cache/timer แต่เก็บเอกสาร/ค่าผู้ใช้
  home ปิด process ทันที; merge/selector/comparison จำกัดจำนวนภาพและงบสำเนาภาพโดยประมาณ
- เครื่องมือพร้อมใช้ทั้ง 6 มี worker thread และ event queue ของตนเอง แต่ใช้ busy ของ App ร่วมกัน;
  shell poll เฉพาะหน้าปัจจุบันทุก 80 ms และ home 300 ms, page อ่านไม่เกิน 100 events ต่อรอบ; worker ไม่แตะ Tk
- แยกหน้า/ลบหน้าใช้ SelectionPage ร่วม, preview เลขหน้าใหม่/เดิมและชื่อไฟล์;
  core/document ตรวจต้นฉบับ, core/pdf_output ตรวจชุดชั่วคราวและคืนไฟล์ของงานเมื่อผิดพลาด
- หมุนใช้ไอคอนซ้าย/ขวาสะสมทีละ 90° เริ่ม 0° และตัวเลือกหน้าต่อเอกสาร, PagePreview ก่อน–หลัง และ staged batch publication;
  render key เพิ่มมุม/ขนาดเฉพาะภาพเปรียบเทียบ โดยคง key ของ merge/selector เดิม
- PNG ใช้ DPI 36–600, ชื่อภาพเรียงตามหน้า, โฟลเดอร์ชื่อซ้ำเติมเลข;
  บางไฟล์ล้มเหลวยังทำไฟล์อื่นต่อและแสดงรายการผิดพลาด
- รวม PDF ตรวจต้นฉบับ/รหัสผ่าน/จำนวนหน้า, รักษา links, annotations, forms และ bookmarks;
  เขียนไฟล์ชั่วคราวแล้วเปิดตรวจจำนวนหน้า ก่อนเผยแพร่โดยไม่ทับไฟล์เดิม
- แยก PDF ใช้ core ช่วงหน้าและ PageSelector ร่วม; ตารางหน้า 1–4 คอลัมน์เลื่อนแนวตั้ง วาดเฉพาะที่มองเห็นไม่เกิน 24 การ์ด
  คิวภาพร่วมไม่เกิน 16; cache 32/6 MiB โดยประมาณ; กลุ่มผลลัพธ์ยังทีละ 25 รายการ
  Shift/Ctrl เลือกช่วง/เพิ่มหน้า; ลากครอบวาดเฉพาะ viewport และยืนยันแผนตอนปล่อยเมาส์; Esc ยกเลิก
  อ่านข้อมูลด้วย worker, เก็บ snapshot ต้นฉบับ, ตรวจทุกไฟล์ชั่วคราวก่อนเผยแพร่แบบไม่ทับเดิม
  ชื่อชนหรือบันทึกล้มเหลวคืนเฉพาะไฟล์ที่งานนี้สร้าง และแจ้งชื่อที่คืนไม่ได้
- services ไม่พึ่ง GUI; package assets/TkDnD และ version metadata อยู่ในระบบ build;
  ชุดแจกมี standalone EXE, Portable ZIP, Setup และ SHA256

## อัปเดตแผนภาพเมื่อแก้โค้ด

1. อ่านโค้ดที่เปลี่ยนและแก้ความหมายใน `docs/diagrams/*.json` ให้ตรงกับผลสุดท้าย
   อัปเดต `ARCHITECTURE.md` และคู่มือฟีเจอร์เมื่อจำเป็น
2. ใช้ Node และ Archify skill ในเครื่องผู้พัฒนา ถ้าอยู่ตำแหน่งอื่นให้กำหนด
   `ARCHIFY_HOME` หรือใช้ `--archify-home <path>` ไม่ต้องใส่ absolute path ของเครื่องลง Git
3. เรียก `python scripts/update_diagrams.py --visual-check`:
   validate ทุก source ก่อน, deliver แบบ atomic ต่อแผนภาพ, เก็บ receipt/hash,
   ตรวจ browser ที่ 1440×900, 1600×1000, 1920×1080 และ 2048×1320
4. ตรวจภาพ light/dark จริง ถ้าต้องแก้ ให้แก้ JSON แล้ว validate/deliver ใหม่;
   ห้ามแก้ HTML ที่สร้างแล้วด้วยมือ
5. รัน `python scripts/check.py` และ stage source, JSON, HTML, receipts, manifest พร้อมกัน
6. `python scripts/update_diagrams.py --check --staged` ต้องผ่านก่อน commit

`--check` ใช้ Python อย่างเดียวและอ่านอย่างเดียว ตรวจชื่อ/เนื้อหา source รวมไฟล์ใหม่
และ JSON/HTML เทียบ manifest; ปรับ CRLF/LF ให้เหมือน Git เพื่อใช้ได้บน Windows
hook ตรวจ `docs/low-spec-review.json` เพิ่มด้วย ต้องพิจารณา CPU 2 คอร์ / RAM 4 GiB / HDD
และผูกหลักฐานที่ผ่านกับ source ใน staged index; ไม่รับรองเครื่องที่ยังไม่ได้ทดสอบจริง
hook ไม่ได้แปลความหมายจากโค้ดให้เอง: agent เป็นผู้ทบทวนและแก้ JSON ส่วน checker
ป้องกันการลืมอัปเดตหลักฐาน หากแก้โค้ดที่ไม่เปลี่ยนแผนภาพก็ยังต้องทบทวนและ refresh

## ติดตั้ง Git hook

เรียก `python scripts/install_hooks.py` หนึ่งครั้งต่อ checkout จะติดตั้ง pre-commit
โดยไม่ทับ hook อื่น Git hook ตรวจ **staged index** จึงจับกรณีที่แก้แผนภาพแล้วลืม stage ได้
กติกาสำหรับ agent อยู่ใน `AGENTS.md`; fresh clone ต้องติดตั้ง hook ใหม่

## หลักฐานและไฟล์ชั่วคราว

- `*.delivery.json` เก็บ 9 artifact checks, composition และ SHA256 ของ source/HTML
- `manifest.json` ผูกแผนภาพกับ snapshot โค้ด; ห้ามแก้เองเพื่อข้าม freshness check
- `*.visual-check.json`, contact sheet และ PNG เป็นหลักฐาน browser ล่าสุดในเครื่อง (ignored)
- ตรวจด้านความสวยงามด้วยการอ่านภาพจริงแยกจาก browser measurements;
  receipt ของ visual-check จะยังระบุ `visualReview: pending` ตามสัญญาของ Archify
- ล้าง cache และ build ชั่วคราวด้วย `python scripts/clean_workspace.py` (dry run)
  แล้ว `--apply`; ไม่ลบชุดแจกใน `dist/` หรือเครื่องมือ Inno Setup

รุ่น 1.6.0: Workbench ร่วมใน ui/workbench.py; หน้าแรกเริ่มเฉพาะพร้อมใช้
ตารางหน้า 180×200 fit, ภาพหมุน 320×400 fit แบบแท็บ; งบ cache/คิว/process เท่าเดิม
ตรวจ geometry และภาพจริงทั้ง 6 เครื่องมือที่ 920/1080/1440 logical px และ 100%/125%

1.7.0 replaces home sidebar with task desk and adds shared masthead/tool navigation; review App routing and busy lock against ui/navigation.py. Engines and preview topology unchanged.

## การแปลงภาพ · 1.8.0

PDF to Image ใช้ route `pdf-png` เดิม แต่รองรับ PNG/JPG/WebP/TIFF, พิกเซลหรือ DPI,
เพดานไฟล์ต่อภาพเป็นคำเตือน และ CSV ขนาดจริง ไม่ลดพิกเซล/คุณภาพเพื่อให้ผ่านเพดาน
ประมวลผลทีละหน้า คิว events ≤32 รายการ คำเตือนรายละเอียดบนหน้าจอ ≤50
PNG/WebP/TIFF เป็น Lossless; JPG เป็น Lossy; ภาพเกิน 40 ล้านพิกเซลถูกปฏิเสธอย่างชัดเจน

1.8.1 adds a shared masthead activity ring/elapsed badge on all six pages.
App.busy controls its lifecycle; the existing 80-ms shell poll advances it.
Idle/hidden badges do no animation work; Windows reduced motion retains static status.
No additional worker/timer or export quality change.

1.9.0 reuses PageSelector for the image tool's per-document modal dialog. Async
inspection and export use its existing queue/busy guard; Apply commits a snapshot,
close cancels draft edits, hiding/destroying releases previews. Image output names
keep original page numbers; progress/CSV cover only selected pages.
