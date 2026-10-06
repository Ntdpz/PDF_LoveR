# PDF LoveR 1.14.0 · ใส่ลายน้ำ PDF

เพิ่มเครื่องมือใส่ลายน้ำใหม่ ใช้งานออฟไลน์ รวมพร้อมใช้ 9 จาก 34 เครื่องมือ

- ข้อความไทย/อังกฤษ: Noto Sans Thai ที่ฝังใน PDF (SIL OFL) หรือ Serif พร้อม fallback ไทย ขนาด สี ความทึบ มุม และ 9 ตำแหน่ง
- ภาพ PNG/JPG รวม PNG alpha ปรับความกว้างเป็นเปอร์เซ็นต์ต่อหน้า รักษาสัดส่วน ไม่ลดคุณภาพเอง ตรวจภาพไม่เกิน 20 MiB / 16 ล้านพิกเซล ก่อนเริ่ม
- ทุกหน้าหรือหน้าที่เลือก พิกัดอิงพื้นที่ CropBox ที่มองเห็นหลังหมุน 0/90/180/270° ขอบ 12 pt; ข้อความใช้ pt คงที่ ภาพใช้ % ความกว้างก่อนหมุน ไม่พอดีจะแจ้งให้ปรับ
- Preview/export ใช้ขั้นตอนวางเดียวกัน Preview อ่านกลับเฉพาะหน้าเพื่อให้PNG alphaตรงไฟล์จริง รักษาเนื้อหา PDFเดิมโดยไม่ rasterizeทุกหน้า
- เก็บ text/vector/images, links/bookmarks/annotations และ forms ที่แก้ไขได้ บันทึกใหม่ไม่ทับต้นฉบับ/ไฟล์เดิม พร้อม loader/progress/cancel และ cleanup
- ใช้ worker/coordinator/cache ร่วม คิวมีขอบเขต; reuse overlays ไม่เกิน 8 ข้อความ / 2 ภาพ ไม่มี dependencyหนักใหม่

คู่มือ: [ใส่ลายน้ำ](https://github.com/Ntdpz/PDF_LoveR/blob/main/docs/WATERMARK.md)

การตรวจรุ่นนี้: 119 unit tests และ 20 ชุด native UI รันตามลำดับ รวมหน้าต่างจริง 920×700 ที่ 100%/125%, keyboard, cancel/retry/error cleanup, fidelity/forms, previewเทียบ PDF และ Poppler อ่าน/เรนเดอร์อิสระ ตรวจ EXE / Portable ZIP / Installer รวมติดตั้ง/ถอนติดตั้งรักษาไฟล์ผู้ใช้ และตรวจ SHA256 ดาวน์โหลดกลับจาก Release

วัด synthetic 1000 หน้าที่ CPU affinity 2: reuse overlays ลด 112.62→13.11 วินาที, peak working set 393.66→49.79 MiB ใน single before/after run โดย output bytes เท่าเดิม ค่านี้เฉพาะ workloadบนเครื่องพัฒนา ไม่ใช่การรับรองสเปกต่ำ

ข้อจำกัด: ผลบน Windows 10 เครื่องพัฒนา; ยังไม่ทดสอบเครื่องจริง 4 GB/HDD, Windows 11หรืออีกเครื่องจริง CPU affinity 2 ไม่แทนฮาร์ดแวร์จริง ยังไม่วัด large scans/ภาพสูงสุด/cold HDD EXE/Installer unsigned และrepo Private ต้องบัญชีที่มีสิทธิ์ ไม่รับรองลายเซ็นดิจิทัลและ PDF scripts; PDF ต้องไม่ใช้รหัสผ่าน ลายน้ำหนึ่งบรรทัดไม่เกิน 500 ตัวอักษร เป็น overlay ใหม่ ไม่ใช่ลบลายน้ำ/redaction/ป้องกันคัดลอก widget/annotationอาจวาดเหนือ overlay; การอ่านข้อความที่เอียงอาจแยกหลายส่วน; Thai shaping อาจคืนสระเป็น Unicode แยกและวรรณยุกต์ไม่ครบใน text extraction แม้แสดงผลถูกต้อง จึงไม่รับรอง copy/search ลายน้ำไทยตรงทุกตัวอักษร ยกเลิกรอ native call ปัจจุบันเสร็จก่อน cleanup

ไฟล์ดาวน์โหลด: EXEเปิดไฟล์เดียว, Portable ZIPแตกทั้งโฟลเดอร์, Installerติดตั้งต่อผู้ใช้ พร้อมคู่มือและSHA256SUMS.txt
