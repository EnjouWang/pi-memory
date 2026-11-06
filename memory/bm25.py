"""BM25-lite：給每筆文件對查詢打相關度分數，回傳排序後的前 K 筆。記憶檢索的確定性核心。"""
from __future__ import annotations
import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    """小寫化後，取出英數字詞與單個 CJK 字元。不做 stemming。"""
    return _TOKEN_RE.findall(text.lower())


def bm25_search(
    query: str,
    docs: list[dict],
    k: int = 8,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict]:
    """
    標準 BM25 排序。
    docs = [{"id": str, "text": str}, ...]；回傳 [{"id", "score"}, ...]（高到低，前 k 筆）。

      score(q,d) = Σ_qi IDF(qi) * (tf*(k1+1)) / (tf + k1*(1 - b + b*|d|/avgdl))
      IDF(qi)    = ln( (N - n + 0.5)/(n + 0.5) + 1 )
      tf = qi 在 d 出現次數 | |d| = d 詞數 | avgdl = 平均詞數 | N = 文件數 | n = 含 qi 的文件數

    流程：
      1) 用 tokenize() 斷詞，記每篇長度，算 avgdl
      2) 算每個詞的 document frequency（df）
      3) 對每篇文件，加總查詢每個詞的 BM25 貢獻
      4) 依分數高到低排序（同分保持原始順序），回傳前 k 筆

    """
    n_docs = len(docs)
    if n_docs == 0:
        return []

    # 1) 斷詞、記每篇長度、算 avgdl
    doc_tokens = [tokenize(d["text"]) for d in docs]
    doc_lens = [len(toks) for toks in doc_tokens]
    avgdl = sum(doc_lens) / n_docs if n_docs else 0.0

    # 2) document frequency（df）：含某詞的文件數
    df: Counter[str] = Counter()
    for toks in doc_tokens:
        for term in set(toks):
            df[term] += 1

    # 預先算每個查詢詞的 IDF（同一詞只算一次）
    query_terms = tokenize(query)
    idf: dict[str, float] = {}
    for term in set(query_terms):
        n = df.get(term, 0)
        idf[term] = math.log((n_docs - n + 0.5) / (n + 0.5) + 1.0)

    # 3) 逐篇文件加總查詢每個詞的 BM25 貢獻
    results = []
    for doc, toks, dl in zip(docs, doc_tokens, doc_lens):
        tf = Counter(toks)
        score = 0.0
        for term in idf:  # 每個查詢詞（去重）只計一次
            f = tf.get(term, 0)
            if f == 0:
                continue
            denom = f + k1 * (1.0 - b + b * (dl / avgdl if avgdl else 0.0))
            score += idf[term] * (f * (k1 + 1.0)) / denom
        results.append({"id": doc["id"], "score": score})

    # 4) 依分數高到低排序；同分維持原始輸入順序（stable sort）
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k]
