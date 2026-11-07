"""多路检索结果的融合：RRF（Reciprocal Rank Fusion）。

为什么不直接把两路分数相加：余弦相似度是 0～1，BM25 无上界，
而且同一条检索在不同查询下的分数分布差别很大，归一化 + 加权
既要调参数又容易被异常高分带偏。

RRF 只取名次：

    score(d) = Σ 1 / (k + rank_i(d))        k 默认 60

名次天然把所有检索器拉到同一尺度；k 用来削弱头部差距，避免某一路的
第一名过度主导。代价是丢掉了分数幅度信息。
"""

from collections import defaultdict


def rrf(rankings: dict[str, list[int]], k: int = 60) -> list[dict]:
    """把多路排名融合成一个有序列表。

    rankings: {"vector": [chunk_id, ...], "bm25": [chunk_id, ...]}，按名次排好
    返回: [{"chunk_id", "score", "sources"}, ...]，按融合分降序
    """
    scores: dict[int, float] = defaultdict(float)
    sources: dict[int, list[str]] = defaultdict(list)

    for name, ids in rankings.items():
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
            sources[chunk_id].append(name)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {"chunk_id": chunk_id, "score": score, "sources": sources[chunk_id]}
        for chunk_id, score in ordered
    ]
