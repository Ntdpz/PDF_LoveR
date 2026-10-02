"""The PDF LoveR tool directory. Planned entries never imply a working engine."""
from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True)
class Category:
    id: str
    title: str
    icon: str


@dataclass(frozen=True)
class Tool:
    id: str
    title: str
    category: str
    description: str
    icon: str
    keywords: str = ""
    ready: bool = False
    note: str = ""


CATEGORIES = (
    Category("organize", "จัดระเบียบ PDF", "pages"),
    Category("optimize", "เพิ่มประสิทธิภาพ", "compress"),
    Category("to-pdf", "แปลงเป็น PDF", "import"),
    Category("from-pdf", "แปลงจาก PDF", "export"),
    Category("edit", "แก้ไข PDF", "edit"),
    Category("security", "ความปลอดภัย", "lock"),
    Category("ai", "AI และข้อความ", "text"),
)

TOOLS = (
    Tool("pdf-png", "PDF เป็น PNG", "from-pdf", "แปลงทุกหน้าเป็นภาพ PNG เลือกความละเอียดและหลายไฟล์ได้", "image", "ภาพ รูป photo picture", True),
    Tool("merge", "รวม PDF", "organize", "รวมหลายเอกสารเป็นไฟล์เดียว ตามลำดับที่คุณเลือก", "pages", "merge combine รวมไฟล์", True),
    Tool("split", "แยก PDF", "organize", "แยกทุกหน้า ตามช่วง หรือทุก N หน้า พร้อมตรวจชื่อไฟล์ก่อนบันทึก", "split", "split แบ่ง ช่วงหน้า", True),
    Tool("delete-pages", "ลบหน้าออก", "organize", "เลือกหน้าที่ไม่ต้องการ แล้วบันทึกเอกสารที่เหลือ", "split", "delete remove ลบหน้า", True),
    Tool("extract-pages", "แยกหน้า", "organize", "เลือกเฉพาะหน้าที่ต้องการ แล้วสร้าง PDF ไฟล์ใหม่", "pages", "extract เลือกหน้า", True),
    Tool("organize", "จัดระเบียบ PDF", "organize", "เรียง ลบ และเพิ่มหน้า ให้เอกสารอยู่ในลำดับที่ต้องการ", "pages", "reorder sort จัดหน้า"),
    Tool("scan", "สแกนเป็น PDF", "organize", "นำภาพเอกสารที่สแกนมาจัดเป็น PDF", "image", "scan camera กล้อง มือถือ", note="การรับภาพจากมือถือยังต้องพัฒนาการเชื่อมต่อเพิ่มเติม"),
    Tool("compress", "บีบอัด PDF", "optimize", "ลดขนาดเอกสาร โดยเลือกระดับคุณภาพที่เหมาะกับงาน", "compress", "compress size ลดขนาด"),
    Tool("repair", "ซ่อม PDF", "optimize", "ตรวจและพยายามกู้เอกสารที่เปิดไม่ได้หรือมีโครงสร้างเสียหาย", "pages", "repair recover กู้", note="การกู้คืนขึ้นอยู่กับความเสียหายของไฟล์ ไม่รับประกันว่าจะกู้ได้ทุกไฟล์"),
    Tool("ocr", "OCR PDF", "optimize", "เพิ่มข้อความที่ค้นหาและเลือกได้ให้เอกสารสแกน", "text", "ocr searchable สแกน ข้อความ", note="ต้องเพิ่มระบบ OCR และทดสอบการรู้จำภาษาไทยก่อนเปิดใช้งาน"),
    Tool("jpg-pdf", "JPG เป็น PDF", "to-pdf", "รวมภาพเป็นเอกสาร พร้อมปรับแนวหน้าและระยะขอบ", "image", "jpeg image รูปภาพ"),
    Tool("word-pdf", "Word เป็น PDF", "to-pdf", "แปลง DOC และ DOCX เป็น PDF สำหรับอ่านและแชร์", "text", "doc docx word", note="ต้องเพิ่มระบบแปลงเอกสาร Office และตรวจความถูกต้องของรูปแบบ"),
    Tool("ppt-pdf", "PowerPoint เป็น PDF", "to-pdf", "แปลงสไลด์ PPT และ PPTX เป็นเอกสาร PDF", "slides", "ppt pptx powerpoint สไลด์", note="ต้องเพิ่มระบบแปลงเอกสาร Office และตรวจความถูกต้องของรูปแบบ"),
    Tool("excel-pdf", "Excel เป็น PDF", "to-pdf", "แปลงตาราง XLS และ XLSX เป็น PDF ที่จัดหน้าพร้อมอ่าน", "table", "xls xlsx excel ตาราง", note="ต้องเพิ่มระบบแปลงเอกสาร Office และตรวจความถูกต้องของรูปแบบ"),
    Tool("html-pdf", "HTML เป็น PDF", "to-pdf", "บันทึกหน้า HTML หรือหน้าเว็บเป็นเอกสาร PDF", "import", "html url web เว็บ", note="การเปิด URL ต้องใช้อินเทอร์เน็ตและระบบเรนเดอร์หน้าเว็บเพิ่มเติม"),
    Tool("pdf-jpg", "PDF เป็น JPG", "from-pdf", "แปลงหน้าเอกสารเป็น JPG หรือดึงภาพจาก PDF", "image", "jpeg image extract ภาพ"),
    Tool("pdf-word", "PDF เป็น Word", "from-pdf", "แปลงข้อความและรูปแบบเอกสารเป็น DOCX ที่แก้ไขได้", "text", "doc docx word", note="ความแม่นยำขึ้นอยู่กับโครงสร้าง ฟอนต์ และภาพสแกนของเอกสาร"),
    Tool("pdf-ppt", "PDF เป็น PowerPoint", "from-pdf", "แปลงหน้า PDF เป็นสไลด์สำหรับงานนำเสนอ", "slides", "ppt pptx powerpoint", note="การสร้างสไลด์ที่แก้ไขได้ต้องใช้ระบบแปลงเพิ่มเติมและทดสอบรูปแบบ"),
    Tool("pdf-excel", "PDF เป็น Excel", "from-pdf", "ดึงตารางจากเอกสารไปเป็นข้อมูลในไฟล์ Excel", "table", "xls xlsx excel ตาราง", note="ตารางในภาพสแกนต้องผ่าน OCR และตรวจความถูกต้องของข้อมูล"),
    Tool("pdf-a", "PDF เป็น PDF/A", "from-pdf", "เตรียมเอกสารสำหรับจัดเก็บระยะยาวในรูปแบบ PDF/A", "export", "archive pdfa จัดเก็บ", note="ต้องเพิ่มตัวแปลงและตัวตรวจมาตรฐาน PDF/A ก่อนเปิดใช้งาน"),
    Tool("rotate", "หมุน PDF", "edit", "ปรับทิศทางของหน้าที่เลือก หรือหมุนหลายไฟล์พร้อมกัน", "pages", "rotate orientation", True),
    Tool("page-numbers", "ใส่หมายเลขหน้า", "edit", "เพิ่มเลขหน้า พร้อมเลือกตำแหน่ง ขนาด และรูปแบบ", "text", "number pagination เลขหน้า"),
    Tool("watermark", "ใส่ลายน้ำ", "edit", "วางข้อความหรือรูปภาพ พร้อมปรับตำแหน่งและความโปร่งใส", "image", "watermark"),
    Tool("crop", "ครอบตัด PDF", "edit", "เลือกพื้นที่หน้าเอกสาร เพื่อตัดขอบที่ไม่ต้องการ", "crop", "crop margin ขอบ"),
    Tool("editor", "แก้ไข PDF", "edit", "เพิ่มข้อความ รูปภาพ รูปร่าง และหมายเหตุในเอกสาร", "edit", "edit annotation วาด"),
    Tool("forms", "แบบฟอร์ม PDF", "edit", "กรอกและจัดการช่องข้อมูลในแบบฟอร์ม PDF", "table", "form fill กรอก"),
    Tool("unlock", "ปลดล็อก PDF", "security", "นำการป้องกันออกจากเอกสารที่คุณมีสิทธิ์และรหัสผ่าน", "lock", "unlock password รหัสผ่าน", note="ใช้กับเอกสารที่คุณมีสิทธิ์จัดการ และต้องทราบรหัสผ่านที่เอกสารกำหนด"),
    Tool("protect", "ป้องกัน PDF", "security", "ตั้งรหัสผ่านและสิทธิ์การใช้งานของเอกสาร", "lock", "protect encrypt password รหัสผ่าน"),
    Tool("sign", "เซ็น PDF", "security", "วางลายเซ็นของคุณลงในเอกสาร", "edit", "sign signature ลายเซ็น", note="การขอลายเซ็นจากผู้อื่นและลายเซ็นดิจิทัลต้องมีระบบรองรับเพิ่มเติม"),
    Tool("redact", "ปิดบังข้อความ PDF", "security", "เลือกข้อมูลที่ต้องการลบออกจากเอกสารอย่างถาวร", "lock", "redact privacy ถมดำ", note="ต้องลบเนื้อหาจริงและตรวจผลลัพธ์ การวาดกล่องทับข้อความเพียงอย่างเดียวไม่เพียงพอ"),
    Tool("compare", "เปรียบเทียบ PDF", "security", "ดูเอกสารสองรุ่นเคียงกันและตรวจจุดที่เปลี่ยนแปลง", "split", "compare diff ต่าง"),
    Tool("summarize", "ตัวสรุป AI", "ai", "สรุปประเด็นจากเอกสาร พร้อมกลับไปตรวจต้นฉบับ", "text", "ai summary สรุป", note="ต้องเลือกและเชื่อมระบบ AI ก่อนใช้งาน การส่งข้อมูลจะต้องแจ้งให้ผู้ใช้ทราบ"),
    Tool("translate", "แปล PDF", "ai", "แปลเนื้อหาเอกสารเป็นภาษาที่คุณเลือก", "text", "ai translate language ภาษา", note="ต้องเชื่อมระบบแปลและตรวจการจัดหน้า รวมถึงแจ้งการส่งข้อมูลก่อนใช้งาน"),
    Tool("markdown", "PDF เป็น Markdown", "ai", "จัดข้อความ หัวเรื่อง รายการ และตารางเป็นไฟล์ Markdown", "text", "md markdown llm notes โน้ต", note="การคงตารางและลิงก์ขึ้นอยู่กับโครงสร้าง PDF และระบบแยกเนื้อหาที่จะเพิ่ม"),
)


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def find_tools(query="", category="all", ready_only=False):
    terms = normalize(query).split()
    categories = {item.id: item.title for item in CATEGORIES}
    return [tool for tool in TOOLS
            if (category == "all" or tool.category == category)
            and (not ready_only or tool.ready)
            and all(term in normalize(" ".join((tool.title, tool.description, tool.keywords, categories[tool.category]))) for term in terms)]
