"""Hybrid retrieval = BM25（lexical）+ 本地 embedding（semantic）。

設計重點：
  - 不動 `bm25.py::bm25_search()`，純 BM25 路徑保持標準、確定性，可被單元測試驗證。
  - 本檔僅在以環境變數 `PI_MEMORY_HYBRID=1` 啟用時，由 `core.retrieve()` 呼叫。
  - embedding 由本地 `sentence-transformers` 模型產生，**僅本地推論、不呼叫雲端 API**；
    模型於第一次執行時自 Hugging Face 下載並快取，之後可離線使用。
  - 融合方式：對候選集內的 BM25 分數與 cosine 相似度各自做 min-max 正規化，
    再以 alpha 加權（score = alpha*lexical + (1-alpha)*semantic），確定性地排序。

為何能修好純 BM25 接不到的題：embedding 把語義相近（package manager↔pnpm）與
跨語言（英文查詢↔中文記憶）的字面落差，轉成向量空間中的距離，補上 lexical 的天花板。
"""
from __future__ import annotations
import os

from .bm25 import bm25_search

# 預設多語言模型：同時支援中英文，才能處理 benchmark 的跨語言題。
_DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None
_embed_cache: dict[str, "list[float]"] = {}


def _get_model():
    """延遲載入模型（只有啟用 hybrid 時才付出載入成本）。"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        name = os.environ.get("PI_MEMORY_EMBED_MODEL", _DEFAULT_MODEL)
        _model = SentenceTransformer(name)
    return _model


def _minmax(scores: list[float]) -> list[float]:
    """把一組分數線性壓到 [0,1]；全部相同時回傳全 0（避免除以零）。"""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-12:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _encode_docs(model, docs: list[dict]):
    """編碼文件文字，已算過的以 (id+text) 為 key 快取，避免 benchmark 重複編碼。"""
    import numpy as np
    need_idx, need_text = [], []
    for i, d in enumerate(docs):
        key = f"{d['id']}\x00{d['text']}"
        if key not in _embed_cache:
            need_idx.append(i)
            need_text.append(d["text"])
    if need_text:
        vecs = model.encode(need_text, normalize_embeddings=True)
        for j, i in enumerate(need_idx):
            d = docs[i]
            _embed_cache[f"{d['id']}\x00{d['text']}"] = vecs[j]
    return np.array([_embed_cache[f"{d['id']}\x00{d['text']}"] for d in docs])


def hybrid_search(
    query: str,
    docs: list[dict],
    k: int = 8,
    alpha: float = 0.2,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict]:
    """BM25 + embedding 融合排序。docs = [{"id","text"}]；回傳 [{"id","score"}]（前 k）。

    alpha：lexical 權重（0=純語義、1=純 BM25），可用 PI_MEMORY_ALPHA 覆寫。
    預設 0.2 由大語料 benchmark 掃描而得（語義主導、BM25 輔助消歧效果最佳）。
    """
    if not docs:
        return []

    alpha = float(os.environ.get("PI_MEMORY_ALPHA", alpha))

    # 1) 取得全體文件的 BM25 分數（要全部，不只前 k，才能與語義融合）
    bm = {d["id"]: 0.0 for d in docs}
    for r in bm25_search(query, docs, len(docs), k1=k1, b=b):
        bm[r["id"]] = r["score"]
    bm_scores = [bm[d["id"]] for d in docs]

    # 2) 語義 cosine 相似度（向量已 normalize，內積即 cosine）
    import numpy as np
    model = _get_model()
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    d_embs = _encode_docs(model, docs)
    sem_scores = [float(np.dot(q_emb, de)) for de in d_embs]

    # 3) 各自 min-max 正規化後加權融合，確定性排序（同分維持原始順序）
    bm_n = _minmax(bm_scores)
    sem_n = _minmax(sem_scores)
    results = [
        {"id": d["id"], "score": alpha * bn + (1.0 - alpha) * sn}
        for d, bn, sn in zip(docs, bm_n, sem_n)
    ]
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k]
