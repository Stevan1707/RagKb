"""PDF 文本抽取：逐页读取，保留页码。"""

from pathlib import Path

import pymupdf


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
