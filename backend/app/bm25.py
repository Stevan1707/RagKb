"""BM25 关键词检索：本地实现，不引第三方依赖。

为什么需要它：向量检索擅长「换个说法也能找到」，但对「第三十五条」
「HY2024-07」这类精确编号、人名、型号不敏感——它们被压进一个向量后，
字面信息基本丢了。BM25 靠字面匹配补这一路。

分词策略：
- 英文 / 数字：按词
- 中文：按字 bigram（「第三十五条」→ 第三 / 三十 / 十五 / 五条）
  没用 jieba，是为了少一个依赖；bigram 在中文 BM25 里是够用的基线。
  单个汉字（比如「法」）保留原字，避免查一个字时完全匹配不到。

打分公式（标准 BM25，参数 k1=1.5、b=0.75）：

    score = Σ IDF(词) × tf × (k1+1) / (tf + k1 × (1 - b + b × 文档长度/平均长度))

IDF 让罕见词主导，k1 让词频饱和，b 惩罚长文档。
"""

import math
import re
from collections import Counter, defaultdict

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """中英文混合分词：英文按词，中文按 bigram。"""
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer((text or "").lower()):
        chunk = match.group(0)
        if chunk[0].isascii():
            tokens.append(chunk)
        elif len(chunk) == 1:
            tokens.append(chunk)
        else:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return tokens


class BM25Index:
    """内存索引：chunk_id → 分词结果，支持全量重建与按词查倒排。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.ids: list[int] = []
        self.doc_len: list[int] = []
        self.avgdl: float = 0.0
        self.idf: dict[str, float] = {}
        self.inverted: dict[str, list[tuple[int, int]]] = defaultdict(list)

    def __len__(self) -> int:
        return len(self.ids)

    def build(self, rows: list[tuple[int, str]]) -> None:
        """全量重建。rows 是 [(chunk_id, content)]。"""
        self.ids = [row[0] for row in rows]
        tfs = [Counter(tokenize(row[1])) for row in rows]
        self.doc_len = [sum(tf.values()) for tf in tfs]
        total = sum(self.doc_len)
        self.avgdl = total / len(self.doc_len) if self.doc_len else 0.0

        df: Counter = Counter()
        for tf in tfs:
            df.update(tf.keys())

        n = len(self.ids)
        self.idf = {
            term: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

        self.inverted = defaultdict(list)
        for index, tf in enumerate(tfs):
            for term, freq in tf.items():
                self.inverted[term].append((index, freq))

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """返回 [(chunk_id, score)]，按分数降序。"""
        if not self.ids or top_k <= 0:
            return []

        scores: dict[int, float] = defaultdict(float)
        # 同一个词在查询里出现多次只算一次
        for term in dict.fromkeys(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for index, freq in self.inverted[term]:
                dl = self.doc_len[index]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[index] += idf * freq * (self.k1 + 1) / denom

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [(self.ids[index], score) for index, score in ranked[:top_k]]
