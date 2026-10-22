"""切块：把每页文本切成带重叠的块，保留页码。"""

def split_pages(pages: list[dict], chunk_size: int, overlap: int) -> list[dict]:
    """
    切块：把每页文本切成带重叠的块，保留页码。
    :param pages: 输入的文本列表，每个元素是一个字典，包含页码和文本内容。
    :param chunk_size: 每个块的大小。
    :param overlap: 每个块之间的重叠大小， 用于调节滑动窗口
    :return: 切分后的块列表，每个元素是一个字典，包含页码、块序号和块内容。
    """
    result = []
    seq = 0
    for p in pages:
        text = p["text"]
        start = 0
        while start < len(text):
            # 按照chunk_size的大小进行切块
            piece = text[start: start + chunk_size]

            # 如果去掉空格之后非空，则将切出来的块，序号，页码以字典的形式添加到列表中
            if piece.strip():
                result.append({"page": p["page"], "seq": seq, "text": piece})
                seq += 1
            if start + chunk_size >= len(text):
               break
            start += chunk_size - overlap
    return result


#
# if __name__ == "__main__":
#
#     pages = [
#         {"page": 1, "text": "甲" * 1200},
#         {"page": 2, "text": "乙" * 300},
#     ]
#     blocks = split_pages(pages, chunk_size=500, overlap=80)
#
#     assert [len(b["text"]) for b in blocks] == [500, 500, 360, 300], [len(b["text"]) for b in blocks]
#     assert [b["seq"] for b in blocks] == [0, 1, 2, 3], [b["seq"] for b in blocks]
#     assert [b["page"] for b in blocks] == [1, 1, 1, 2], [b["page"] for b in blocks]
#     # 相邻块共享 80 字符的重叠区
#     assert blocks[0]["text"][-80:] == blocks[1]["text"][:80]
#     assert blocks[1]["text"][-80:] == blocks[2]["text"][:80]
#     print("splitter 自测通过：", [len(b["text"]) for b in blocks])
