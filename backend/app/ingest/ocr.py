"""扫描件 / 图片 OCR：本地 RapidOCR（ONNX 模型），不联网、不需要 API Key。

RapidOCR 是 PaddleOCR 模型的 ONNX 版本，首次调用加载模型（约几十 MB），
之后常驻内存；CPU 上大约每页 1～3 秒，所以只对「没有文字层」的页才用。

注意：rapidocr-onnxruntime 只支持 Python < 3.13，
所以本项目统一运行在 Python 3.11 / 3.12 上。

没装依赖时 is_available() 返回 False，loader 会给出明确提示，
其他格式的文档完全不受影响。
"""

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _get_engine():
    """第一次真正调用时才 import + 加载模型；装不上就返回 None。"""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return None
    return RapidOCR()


def is_available() -> bool:
    return _get_engine() is not None


def batch_image_bytes_to_text(images: list[bytes]) -> list[str]:
    """一次处理多张图，返回一一对应的文字列表。

    模型只加载一次，所以整份文档的扫描页最好一起送进来。
    识别失败或置信度低于 OCR_MIN_SCORE 的行会被丢弃。
    """
    if not images:
        return []

    engine = _get_engine()
    if engine is None:
        return [""] * len(images)

    texts: list[str] = []
    for image in images:
        try:
            result, _ = engine(image)
        except Exception:  # noqa: BLE001 - 单张失败按空页处理
            result = None

        if not result:
            texts.append("")
            continue

        # RapidOCR 每行返回 [框坐标, 文本, 置信度]；低置信度的当噪声丢掉
        texts.append(
            "\n".join(
                item[1].strip()
                for item in result
                if len(item) > 2
                and item[1]
                and float(item[2]) >= settings.ocr_min_score
            )
        )
    return texts


def image_bytes_to_text(image: bytes) -> str:
    return batch_image_bytes_to_text([image])[0]
