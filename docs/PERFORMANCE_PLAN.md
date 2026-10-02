# แผน Optimize PDF LoveR สำหรับ PC หลายระดับ

สถานะ: **ดำเนินการชุดแรกใน 1.5.2 แล้ว** ฐานก่อนปรับคือรุ่น 1.5.1, commit `fb51da245641bdf75086b3a5176a996224e2eff6` ณ 2 ตุลาคม 2026
เครื่องมือพร้อมใช้ยังเป็น 6/34 รายการ แนะนำทำชุดนี้ก่อนจัดระเบียบ PDF เพื่อให้ฟีเจอร์ถัดไปใช้ระบบภาพตัวอย่างที่ประหยัดทรัพยากรร่วมกัน

เป้าหมายเบื้องต้นคือ PC CPU 2 คอร์, RAM 4 GB, HDD และเครื่อง RAM 8 GB, SSD บน Windows 10/11
ยังไม่มีผลทดสอบบนเครื่องสเปกต่ำจริง จึงเป็นเป้าหมายสำหรับวัดและปรับ ไม่ใช่การรับรอง minimum requirements
ผู้ใช้ควรใช้ได้โดยไม่ต้องตั้งค่า thread, cache หรือ memory เอง

## ข้อมูลที่ตรวจพบจากรุ่นปัจจุบัน

ตรวจ `AGENTS.md`, `TASKS.md`, `CONTRIBUTING.md`, architecture/diagrams และโค้ดจริงก่อนวางแผน
ผลสำรวจหน่วยความจำอยู่ใน [baseline JSON](performance-baseline-1.5.1.json)

| จุดที่ตรวจ | พฤติกรรมปัจจุบัน | ผลต่อการใช้งาน |
|---|---|---|
| `app.py`, `ui/pdf_previews.py` | เก็บ page หลังเปลี่ยนเครื่องมือ; ซ่อนด้วย `grid_remove()` แต่ preview process ปิดเมื่อ destroy | กลับหน้าแรกแล้วยังถือ RAM ของหลายเครื่องมือ |
| `ui/pdf_previews.py` | request queue ไม่จำกัด; result queue จำกัด 4; เปิด PDF ใหม่ต่อภาพ | งานเก่าค้างได้เมื่อเลื่อนเร็ว และอ่านไฟล์ซ้ำ |
| selector / comparison / merge cards | cache แยก 32 / 12 / 128 ภาพ และมี PIL/Tk image references | จำนวนภาพจำกัดแล้ว แต่ยังไม่มีงบ RAM ร่วมทั้งแอป |
| `app.py` และ merge cards | poll ทุก 80 ms รวมหน้าที่ซ่อนไว้ | timer ทำงานแม้ผู้ใช้ไม่ได้ใช้หน้านั้น |
| selector / selection page / rotate page | แก้ข้อความแล้ว parse/render/ตรวจแผนทันที; บางส่วนตรวจหลายไฟล์และปลายทาง | พิมพ์ช่วงหน้าหรือเปลี่ยนค่าบ่อยมีโอกาสกระตุกเมื่อ batch ใหญ่/ดิสก์ช้า |
| `features/png/service.py` | render ครั้งละหน้า สูงสุด 600 DPI | ภาพ A4 RGB ที่ 600 DPI ใช้ข้อมูลดิบประมาณ 100 MiB ต่อหน้า ยังไม่รวม codec/engine |
| `features/registry.py` | สร้าง widget เมื่อใช้ แต่ import page/service ตั้งแต่เริ่ม | โหลด dependency ล่วงหน้า; โตตามจำนวนเครื่องมือในอนาคต |

การวัดแบบสำรวจหนึ่งครั้งบน i7-11800H, RAM 39.6 GiB, Windows 10 เป็น **source app** ใช้ PDF ข้อความสังเคราะห์ 240 หน้า:

| สถานะ | preview process ที่ยังทำงาน | Private memory รวม main + preview |
|---|---:|---:|
| หน้าแรกตอนเริ่ม | 0 | 57.26 MiB |
| หลังเปิดรวม PDF | 1 | 101.81 MiB |
| หลังเปิดครบ 6 เครื่องมือ | 6 | 316.26 MiB |
| กลับหน้าแรก | 6 | 316.26 MiB |

Private memory อ่านจาก Windows `PROCESS_MEMORY_COUNTERS_EX.PrivateUsage` เพื่อไม่บวก shared working set ซ้ำ
นี่เป็นตัวอย่าง ณ จุดวัด ไม่ใช่ peak RAM, idle CPU, cold-start ของ EXE หรือผลของเอกสารสแกนใหญ่
ปิดแอปแล้ว preview workers ทั้งหมดถูกปิด และไม่มี Tk callback error

กลไกการลากเดิมมีข้อมูลจาก [drag-performance-1.5.1.json](drag-performance-1.5.1.json):
100 การ์ด, 1,000 pointer events, เวลา paint เฉลี่ย 1.38 ms/เฟรม สูงสุด 2.63 ms และ heartbeat gap สูงสุด 24.93 ms
จึงรักษา Canvas ที่วาดเฉพาะ viewport, การรวม pointer เป็นเฟรม 16 ms, edge scroll, keyboard และ reduced motion
ค่าดังกล่าวยังไม่ได้วัดขณะ export หรือบน PC 4 GB

## ลำดับงานและเกณฑ์ปิดแต่ละชุด

### P0 — สร้าง benchmark ที่เทียบก่อน–หลังได้

- ทำ harness แยกจากตัวแอป เก็บเวลาเปิดจนใช้งานได้, UI heartbeat, จำนวน process, CPU, Private Bytes และ peak working set ของ process tree
- เริ่มจาก source และชุดแจก 1.5.1 ที่ตรวจแล้ว จากนั้นใช้ workload เดิมกับรุ่นที่ปรับ
- วัด home, เปิดแต่ละเครื่องมือ, เปิดครบแล้วกลับ home, เลื่อน/ลาก/หมุนซ้ำ, export และปิดแอป
- แยก idle, preview และ export; แยก cold/warm launch; เก็บอย่างน้อย 5 รอบและรายงาน median/ช่วงค่า
- CPU ของแอปรวมลูกทุกตัวหารด้วยจำนวน logical processors เพื่อระบุเปอร์เซ็นต์ของ CPU ทั้งเครื่องให้ชัด
- เก็บ fixture/hash, CPU/RAM/ชนิดดิสก์, Windows, scaling, รูปแบบชุดแจก และ raw samples; ห้ามนำผลเครื่องปัจจุบันไปแทนเครื่อง 4 GB

**ปิดงานเมื่อ:** มี baseline ทำซ้ำได้, ตรวจ worker cleanup ได้ และรู้ว่าจุดหน่วงเกิดที่ Tk, PDF engine, disk หรือ process startup

### P1 — ลด RAM ของภาพตัวอย่างก่อน

- เพิ่ม lifecycle สำหรับหน้า active/hidden ผ่านสัญญาร่วมของ ToolPage; เก็บรายการเอกสาร การเลือกหน้า และค่าที่ผู้ใช้ตั้ง
- ใช้ preview coordinator ร่วม: **ไม่เกิน 1 spawned preview process ทั้งแอป** รองรับ merge, PageSelector และ PagePreview
- ให้ภาพใน viewport ของหน้าปัจจุบันมาก่อน; deduplicate และทิ้งงานจาก viewport/มุมหมุนเก่า โดยใช้ request generation และ source signature
- จำกัด request ที่รอ เช่น 8–16 งานรวม โดย enqueue แบบไม่รอจน Tk ค้าง; จำกัดทั้ง payload และผลลัพธ์
- ตอนซ่อนหน้าให้หยุดส่งงาน/ใช้ timer; ตอน home idle 30–60 วินาทีปิด preview process และคืนภาพที่ไม่ต้องใช้
- ใช้งบ cache รวมเริ่มที่ **16–32 MiB** นับ pixels/payload/PIL/Tk โดยประมาณพร้อมวัด Private Bytes จริง; เก็บภาพที่ยังแสดงอยู่จนเปลี่ยนสำเร็จ
- ทดลองเก็บ PDF เปิดไว้ใน worker เพียง 1–2 เอกสารและมี idle timeout หลังวัดผลแล้ว; invalidation ต้องตรง path/signature และปิด handles เมื่อเปลี่ยน/ปิดไฟล์
- หาก reuse document ต้องคืนค่า page rotation เดิมหลัง render เพื่อไม่ให้มุมสะสม; cache DisplayList ใช้เฉพาะเมื่อผลวัดคุ้มกับ RAM

**ปิดงานเมื่อ:** เปิดครบ 6 เครื่องมือแล้วเหลือ preview process ไม่เกิน 1; home idle ปิด process ได้; กลับหน้าเดิมข้อมูลยังอยู่; ภาพก่อน–หลังไม่สลับผิดหน้า/ผิดมุม

ภาพตัวอย่างคงอยู่ใน process แยก ตามข้อจำกัดของ [PyMuPDF multiprocessing](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html)
หากจะ reuse [DisplayList](https://pymupdf.readthedocs.io/en/latest/displaylist.html) ให้ตรวจต้นทุนและ eviction ก่อนเพิ่ม cache อีกชั้น

### P2 — ลดงานบน Tk และทำให้ batch ใหญ่ตอบสนองเร็ว

- debounce การพิมพ์ช่วงหน้า/ชื่อไฟล์/ปลายทางประมาณ 120–200 ms; การกดหมุนและเลือกการ์ดแสดงผลทันที
- cache ผล parse/metadata และไม่คำนวณ selection ชุดเดิมซ้ำทุก render; พิจารณา interval model หาก benchmark หลายพันหน้าชี้ว่าจำเป็น
- ย้าย filesystem preflight ที่ช้าออกจาก Tk; ตอบกลับด้วย generation ID เพื่อไม่แสดงชื่อ/ผลตรวจที่ล้าสมัย
- ก่อนเริ่ม export ใช้ immutable plan และตรวจ source/target อีกครั้งก่อนเผยแพร่; ต้องป้องกันต้นฉบับ/ชื่อชน/ไฟล์ที่ถูกแก้ระหว่างงานครบเหมือนเดิม
- รวมการ poll ที่ซ้ำ และใช้เวลาอ่านผลต่อรอบประมาณ 4–8 ms; active เริ่มที่ 80 ms, idle 250–500 ms โดยวัดความไวในการตอบสนองประกอบ
- รวม progress เหลือประมาณ 10–15 ครั้ง/วินาที; completion/error/status รายไฟล์ยังส่งครบ
- ระหว่างลากพักการใช้ผล preview และลดงาน render ที่ล้าสมัย; รักษา drag state, animation และ keyboard เดิม

**ปิดงานเมื่อ:** input และการลากผ่าน heartbeat budget ใน batch ใหญ่; ไม่มี stale validation; ไม่มี callback หลัง destroy และ worker ไม่แตะ Tk

### P3 — คุม RAM/CPU ระหว่าง export และเปิดโปรแกรม

- PNG: คืน Pixmap ของแต่ละหน้าอย่างชัดเจนก่อน render หน้าถัดไป และวัด peak ก่อน–หลัง
- ประเมิน RAM จากขนาดหน้า × DPI × bytes/pixel ก่อนงานใหญ่; preview ลดภาระหรือพักระหว่าง export หนัก
- ใช้ export ครั้งละ **1 งาน** เป็นค่าเริ่มต้น; จำนวนคอร์มากไม่ได้แปลว่าควร render หลายหน้าพร้อมกัน
- เก็บ DPI/คุณภาพที่ผู้ใช้เลือก; หากขนาดหน้าเกินงบให้แจ้งประมาณทรัพยากรและตัวเลือกที่เข้าใจง่าย โดยไม่ลดคุณภาพไฟล์ให้อัตโนมัติ
- วัด GIL/UI heartbeat ของ engine ปัจจุบันก่อนตัดสินใจย้าย export ไป process แยก; หากย้ายให้แชร์ staged publication/rollback เดิมและเพิ่มเฉพาะขอบเขต worker
- lazy-load page/service factory ผ่าน registry และคง validation ของ catalogue; engine/OCR/Office ในอนาคตโหลดเมื่อใช้
- เปรียบเทียบ startup และขนาดแจก; สำหรับใช้งานประจำแนะนำ installer/Portable แบบ folder build เพราะ [PyInstaller one-file](https://pyinstaller.org/en/stable/operating-mode.html) ต้องแตก runtime ลงที่ชั่วคราวตอนเริ่ม
- ทดสอบด้วย antivirus ตามปกติ; ตัด dependency หรือ assets เฉพาะเมื่อพิสูจน์ว่าไม่ใช้และชุดแจกทั้งสามแบบยังทำงานครบ

**ปิดงานเมื่อ:** export เอกสารชุดเดิมเสร็จด้วยผลเทียบเท่าเดิม, peak RAM/เวลา/heartbeat มีหลักฐาน, เริ่มโปรแกรมเร็วขึ้นตาม benchmark โดยไม่ทำเครื่องมือหาย

### P4 — ตรวจบน PC เป้าหมายและส่งรุ่น

- ตรวจอย่างน้อยเครื่อง 2 คอร์/4 GB/HDD, 8 GB/SSD และเครื่องพัฒนาที่แรงกว่า บน Windows 10/11 ตามเครื่องที่หาได้
- การจำกัด CPU บนเครื่องพัฒนาใช้ค้นหา regression ได้ แต่ไม่แทนการทดสอบ RAM 4 GB, paging และ HDD จริง
- ใช้ EXE, ZIP และ installer ด้วยบัญชีผู้ใช้ทั่วไปบนเครื่องไม่มี Python; ตรวจชื่อไทย/ช่องว่าง/125% scaling
- รัน `python scripts/check.py`, engine/native UI, benchmark, output fidelity และชุดแจกหลัง build
- ตรวจ PDF page order/count/rotation, links/forms/annotations/bookmarks ตามความสามารถแต่ละเครื่องมือ; PNG เปรียบเทียบ dimensions/pixels ด้วย DPI เดิม
- ตรวจ source hash, no-overwrite, publication race, failure/rollback, worker crash, rapid navigation และ close cleanup
- อัปเดต architecture, Archify JSON/HTML/หลักฐานตาม AGENTS; ตั้ง version เมื่อส่งรุ่นที่ปรับจริง เก็บใน `dist/PDF_LoveR_<VERSION>/`
- ซิงก์ Program โดยตรวจไฟล์ที่แก้แยกไว้, commit/push main; repository คง Private และการสร้าง GitHub Release รอคำสั่งแยก

**ปิดงานเมื่อ:** มีรายงานก่อน–หลังแยกตามเครื่อง/ชุดแจก และระบุ workload ที่ยังเกินงบตามจริง

## งบประสิทธิภาพเริ่มต้นสำหรับ P0

ค่าด้านล่างเป็น **เกณฑ์ที่เสนอ** ต้องยืนยันหรือปรับด้วย baseline ของ PC เป้าหมายก่อนใช้ตัดสิน release

| ตัวชี้วัด | เป้าหมายเริ่มต้น | วิธีวัด |
|---|---|---|
| preview processes | active ≤1, home idle 60 s =0 | นับ process tree และตรวจไม่มี orphan หลังปิด |
| Private memory รวมเมื่อ home idle | ≤120 MiB หลังเปิดครบทุกเครื่องมือ | รวม main/children ที่ยังอยู่ หลัง cleanup |
| Private memory ขณะเลือก/preview ปกติ | ≤200 MiB ใน fixture ข้อความ/ภาพมาตรฐาน | peak ของ process tree; แยกจาก export |
| thumbnail cache | 16–32 MiB รวม | accounting ภาพ + เทียบ Private Bytes จริง |
| memory หลังสลับเครื่องมือ 20 รอบ | เพิ่ม ≤20 MiB จากรอบที่อุ่นแล้ว | กลับสถานะและเวลารอเดียวกันก่อนเทียบ |
| idle CPU | เฉลี่ย ≤1% ของ CPU ทั้งเครื่องใน 60 s | main + children; ไม่มี export/preview ใหม่ |
| UI heartbeat lateness | P95 ≤50 ms, P99 ≤100 ms; ไม่มีช่วง >200 ms ใน interaction workload | heartbeat 20 ms เทียบกำหนดเวลาจริง; watchdog ภายนอกตรวจค้าง |
| drag paint | P95 ≤16 ms | 100 การ์ด/1,000 pointer events และตรวจลำดับสุดท้าย |
| ภาพที่มองเห็นชุดแรก | P95 ≤2 s ใน fixture มาตรฐาน | จากเปลี่ยนหน้า/viewport จนภาพตรง request ครบ |
| เปิด folder build จนใช้งานได้ | warm ≤3 s บน SSD / ≤5 s บน HDD | แยก cold start และเก็บอย่างน้อย 5 รอบ |

ยังไม่ตั้งเพดาน RAM เดียวครอบทุก PDF/ทุก DPI: ขนาดหน้า ภาพฝัง และ codec ทำให้ใช้หน่วยความจำต่างกันมาก
สำหรับ PNG ให้บันทึก peak แยก 150/300/600 DPI รวมเอกสารหน้าขนาดใหญ่ก่อนกำหนดเกณฑ์ export
Throughput ต้องเทียบ workload/เครื่องเดียวกัน; หาก RAM ลดแต่เวลางานเพิ่ม ให้รายงานทั้งสองค่าและเลือกงบสำหรับเครื่องสเปกต่ำ

## Workload ที่ต้องเก็บ

1. PDF ข้อความ 240 และ 1,000 หน้า; เลือกช่วงยาว/ผิด, หมุนซ้ำเร็วและสลับ 6 เครื่องมือ 20 รอบ
2. รวม 100 ไฟล์; drag/scroll/edge scroll ทั้งขณะ cache เย็นและหลังเห็นภาพแล้ว
3. PDF สแกน/ภาพ 200–500 MB ที่รู้จำนวนหน้าและความละเอียด; render 150/300/600 DPI และขนาดหน้าที่ใหญ่กว่า A4
4. PDF มีไทย/อังกฤษ, font ฝัง, forms, links, annotations, bookmarks และ rotation เดิม
5. ไฟล์เสีย/ใส่รหัสผ่าน, ต้นฉบับเปลี่ยน, ชื่อผลลัพธ์ชน, read-only, พื้นที่ไม่พอ และปลายทางดิสก์ช้า
6. ทิ้ง idle 60 s, เปิดหน้าที่เคยซ่อน, ปิดแอปหลัง preview; ตรวจ worker/handles/timers และไฟล์ชั่วคราว

เก็บเอกสารตัวอย่างสังเคราะห์หรือที่มีสิทธิ์ใช้ ไม่ลงเนื้อหาเอกสารของผู้ใช้ในรายงาน
เมื่อเริ่มทำให้แบ่ง commit ตาม P0 → P1 → P2 → P3 → P4; งานนี้ยังไม่เพิ่มจำนวนเครื่องมือหรือเปลี่ยน `ready=True`

## ผลชุดแรก · 1.5.2

- ทำ benchmark source app ด้วย fresh interpreter 5 รอบก่อน/หลัง: [ก่อน](performance-before-1.5.2.json) / [หลัง](performance-after-1.5.2.json)
- ค่ากลาง Private memory หลังเปิดครบ 6 เครื่องมือแล้วกลับ home: 321.62 → 69.75 MiB; หลัง idle: 321.68 → 69.75 MiB ลดประมาณ 78%
- PreviewCoordinator ร่วมจำกัดหนึ่ง process, request 16/result 4; client/generation ทิ้งผลเก่า; home ปิด process ทันที
- คืนภาพ/timer ของหน้าที่ซ่อน โดยรักษาเอกสาร/การเลือกหน้า; cache มีทั้งจำนวนและงบสำเนาภาพโดยประมาณ; [ตรวจสลับเร็ว 20 รอบ](resource-verification-1.5.2.json) ผ่าน
- Poll เฉพาะหน้าปัจจุบัน 80 ms, home 300 ms; cache parse selection และ lazy import factories
- PNG คืน Pixmap ก่อนหน้าก่อน render หน้าถัดไป แต่ [วัด peak ที่ 600 DPI](png-memory-1.5.2.json) ยังประมาณ 241 MiB ทั้งก่อนและหลัง: **ยังไม่มีหลักฐานว่าลด peak RAM ของ PNG**; hash ของภาพผลลัพธ์ตรงกันทุกหน้า
- AGENTS และ staged pre-commit hook บังคับ low-spec impact review + source/evidence hashes ร่วมกับ diagram freshness

ยังไม่ปิด P0/P2/P3/P4 ทั้งชุด: debounce/async filesystem preflight, codec/PNG peak budget, document reuse,
cold-start/frozen resource benchmark, เอกสารสแกนใหญ่ และการทดสอบ PC 4 GiB/HDD/Windows 11 จริง ยังเป็นงานถัดไป
ผลวัดบนเครื่องพัฒนาไม่รับรอง minimum requirements; DPI/คุณภาพไฟล์และจำนวนเครื่องมือยังคงเดิม

## ตัวเลือกหน้าแนวตั้ง · 1.5.3

ตาราง PageSelector ใช้พื้นที่แนวตั้งที่เหลือ วาดเฉพาะ viewport ไม่เกิน 24 การ์ด พร้อมคิวร่วม 16 คำขอและ cache 32/6 MiB โดยประมาณ
[ตรวจ 1,000 หน้าและการเลื่อน/คีย์บอร์ด](selector-verification-1.5.3.json) ผ่านทั้ง 4 เครื่องมือที่ใช้ตัวเลือกนี้
วัด source benchmark เดิม 5 รอบ: home idle Private Bytes ค่ากลาง 69.75 → 68.50 MiB; ยังประมาณ 70 MiB ไม่อ้างว่าลดลงอย่างมีนัยสำคัญ
หลักฐาน [หลังปรับ](performance-after-1.5.3.json); ขอบเขตเครื่อง/workload และงาน Optimize ที่เหลือยังเหมือนชุดก่อน

## เลือกหลายหน้า · 1.5.4

Shift/Ctrl และลากครอบใช้ PageSelector ร่วม ไม่เพิ่ม worker/dependency; live marquee ตรวจเฉพาะ 24 การ์ดที่มองเห็น
รวม pointer เป็นเฟรม 16 ms, edge scroll 60 ms และคำนวณแผน PDF ตอนปล่อยเมาส์ครั้งเดียว; Esc/focus/hide/resize/เปลี่ยนเอกสารคืน grab และ timer
[ตรวจ 1,000 หน้าและ 1,000 pointer events](page-gestures-verification-1.5.4.json) ผ่าน พร้อม export ตามหน้าที่เลือกและตรวจ hash ต้นฉบับ
วัด workload source เดิม 5 รอบ: home idle Private Bytes ค่ากลาง 68.50 → 68.78 MiB; ยังใกล้ 70 MiB ไม่อ้างว่าลดลงอย่างมีนัยสำคัญ
หลักฐาน [หลังเพิ่ม](performance-after-1.5.4.json); ยังไม่ทดสอบ PC 4 GiB/HDD จริง งาน async preflight/PNG peak/cold-start/scanned PDFs ยังอยู่ในแผน
