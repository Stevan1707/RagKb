"""文档文本抽取：PDF / Word / 纯文本 / 图片，统一成 [{"page": 1, "text": "..."}]。

统一契约是按「页」分组，因为切块、编码、入库都只认这个结构，不关心文件格式：

    [{"page": 1, "text": "第一页内容"}, {"page": 2, "text": "..."}]

- PDF：有真实页码，逐页抽取；**没有文字层的页会用 OCR 兜底**
- txt / md：整篇当一个「页」
- docx：整篇当一个「页」
- png / jpg / jpeg：直接走 OCR

除了文字本身，还返回 ocr_pages：这份文档有多少页是靠文字识别得到的，
入库时写进 document 表，列表里就能提示「OCR 识别 N 页」。

docx 不依赖 python-docx：.docx 本质是个 zip，正文在 word/document.xml 里，
用标准库解析足够（代价是丢表格样式，但文字顺序是对的，且少一个依赖）。
OCR 依赖是可选的，没装时只影响扫描件和图片，不影响其他格式。
"""

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

import pymupdf

from app.config import settings
from app.ingest import ocr

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".png", ".jpg", ".jpeg"}

# WordprocessingML 的命名空间，取 w:p（段落）和 w:t（文本节点）时要用
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_OCR_HINT = (
    "扫描件/图片需要 OCR 支持：请用 Python 3.11/3.12 并安装 "
    "rapidocr-onnxruntime（pip install -r requirements.txt）"
)


@dataclass
class LoadResult:
    """一次解析的产物：文字页 + 其中多少页用了 OCR。"""

    pages: list[dict] = field(default_factory=list)
    ocr_pages: int = 0
    total_pages: int = 0


def load_pdf(path: str | Path) -> LoadResult:
    """逐页抽文字；没有文字层的页统一交给 OCR 批量识别。

    为什么要「批量」而不是逐页调：OCR 模型加载一次要几秒，
    逐页调用会把时间全花在反复加载模型上。
    """
    ocr_candidates: list[int] = []

    with pymupdf.open(path) as doc:
        page_numbers: list[int] = []
        texts: list[str] = []

        for page_no, page in enumerate(doc, start=1):
            page_numbers.append(page_no)
            texts.append(page.get_text().strip())

        ocr_candidates = [i for i, text in enumerate(texts) if not text]
        use_ocr = settings.ocr_enabled and ocr.is_available()
        ocr_pages = 0

        if ocr_candidates and use_ocr:
            if len(ocr_candidates) > settings.ocr_max_pages:
                raise ValueError(
                    f"扫描页超过 {settings.ocr_max_pages} 页，"
                    "请调大 OCR_MAX_PAGES 或先转成文字版 PDF"
                )

            images = [
                doc[page_numbers[index] - 1]
                .get_pixmap(dpi=settings.ocr_dpi)
                .tobytes("png")
                for index in ocr_candidates
            ]
            for index, text in zip(
                ocr_candidates, ocr.batch_image_bytes_to_text(images)
            ):
                texts[index] = text.strip()
                if texts[index]:
                    ocr_pages += 1

    pages = [
        {"page": page_no, "text": text}
        for page_no, text in zip(page_numbers, texts)
        if text
    ]

    if not pages and ocr_candidates and settings.ocr_enabled and not ocr.is_available():
        raise ValueError(_OCR_HINT)

    return LoadResult(pages=pages, ocr_pages=ocr_pages, total_pages=len(page_numbers))


def load_text(path: str | Path) -> LoadResult:
    """txt / md：整篇读成一个块。

    编码按 utf-8-sig → utf-8 → gbk 依次尝试：Windows 上记事本存的 txt
    默认可能是 GBK，直接按 utf-8 读会抛 UnicodeDecodeError。
    """
    path = Path(path)
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = path.read_text(encoding="utf-8", errors="ignore")

    text = text.strip()
    pages = [{"page": 1, "text": text}] if text else []
    return LoadResult(pages=pages, ocr_pages=0, total_pages=1 if text else 0)


def load_docx(path: str | Path) -> LoadResult:
    """docx：从 zip 里取 word/document.xml，按段落拼回文字。

    遍历顺序就是文档顺序，表格单元格里的段落也会被包含进来
    （它们在 XML 里同样是 w:p / w:t）。
    """
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(xml)
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{_W}p"):
        pieces = [node.text or "" for node in paragraph.iter(f"{_W}t")]
        line = "".join(pieces).strip()
        if line:
            paragraphs.append(line)

    text = "\n".join(paragraphs).strip()
    pages = [{"page": 1, "text": text}] if text else []
    return LoadResult(pages=pages, ocr_pages=0, total_pages=1 if text else 0)


def load_image(path: str | Path) -> LoadResult:
    """png / jpg / jpeg：整张图走 OCR。"""
    if not settings.ocr_enabled:
        raise ValueError("图片必须经过 OCR，但 OCR 已被禁用（OCR_ENABLED=false）")
    if not ocr.is_available():
        raise ValueError(_OCR_HINT)

    text = ocr.image_bytes_to_text(Path(path).read_bytes()).strip()
    pages = [{"page": 1, "text": text}] if text else []
    return LoadResult(pages=pages, ocr_pages=1 if text else 0, total_pages=1)


def load_document(path: str | Path) -> LoadResult:
    """按扩展名分派。不支持的格式直接报错，让调用方拿到明确原因。"""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in (".txt", ".md"):
        return load_text(path)
    if suffix == ".docx":
        return load_docx(path)
    if suffix in (".png", ".jpg", ".jpeg"):
        return load_image(path)

    raise ValueError(
        f"不支持的文件类型：{suffix or '(无扩展名)'}，"
        f"目前支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )
