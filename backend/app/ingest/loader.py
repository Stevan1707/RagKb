"""文档文本抽取：PDF / Word / 纯文本，统一成 [{"page": 1, "text": "..."}]。

统一契约是按「页」分组，因为切块、编码、入库都只认这个结构，不关心文件格式：

    [{"page": 1, "text": "第一页内容"}, {"page": 2, "text": "..."}]

- PDF：有真实页码，逐页抽取
- txt / md：整篇当一个「页」
- docx：整篇当一个「页」

docx 不依赖 python-docx：.docx 本质是个 zip，正文在 word/document.xml 里，
用标准库解析足够（代价是丢表格样式，但文字顺序是对的，且少一个依赖）。
"""

import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pymupdf

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}

# WordprocessingML 的命名空间，取 w:p（段落）和 w:t（文本节点）时要用
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def load_pdf(path: str | Path) -> list[dict]:
    """返回 [{"page": 1, "text": "..."}]，跳过没有文字层的页。"""
    pages: list[dict] = []
    with pymupdf.open(path) as doc:
        for page_no, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if not text:
                continue
            pages.append({"page": page_no, "text": text})
    return pages


def load_text(path: str | Path) -> list[dict]:
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
    return [{"page": 1, "text": text}] if text else []


def load_docx(path: str | Path) -> list[dict]:
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
    return [{"page": 1, "text": text}] if text else []


def load_document(path: str | Path) -> list[dict]:
    """按扩展名分派。不支持的格式直接报错，让调用方拿到明确原因。"""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in (".txt", ".md"):
        return load_text(path)
    if suffix == ".docx":
        return load_docx(path)

    raise ValueError(
        f"不支持的文件类型：{suffix or '(无扩展名)'}，"
        f"目前支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )
