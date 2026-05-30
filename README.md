[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/uuH2W7ZW)
# AIASE2026 HW4 — Pi Memory（Python）

> 為本地 coding agent 做一個跨 session 的記憶機制：capture → store → retrieve → inject。
> **核心、benchmark、評分皆為 Python**；Pi 端只用我們寫好的薄 TS bridge（你不需修改）。

## 最短路徑

```bash
pip install -r requirements.txt
pytest -q                         # 起點：你會看到部分測試失敗（紅燈正常）
```

要完成的兩個 TODO 核心：
- `memory/bm25.py` 的 `bm25_search()`（主戰場；`tokenize()` 已給）
- `memory/store.py` 的 `load()` / `_persist()` / `add()`

完成後 `pytest -q` 應全綠。`memory/core.py`、`memory/cli.py` 已幫你接好，不用改。

## Benchmark（study tool，建議邊做邊用）

```bash
python benchmark/run_benchmark.py --k 5 --per-query
```

它把一個 30 筆的「專案記憶」語料全部存進你的系統，對 21 個 query（含中英文、含同義詞/跨語言難題）跑你的 `retrieve()`，算出 **Recall@k / MRR / nDCG@k**，並印出「純 BM25 參考目標」。

- 你的純 BM25 應接近參考值（Recall@5 ≈ 0.81）。
- 有幾題是**語義/跨語言落差**，純 lexical BM25 接不到——這是 benchmark 故意設計的，用來讓你觀察 BM25 的天花板。
- 若你做任務二的 **hybrid retrieval（BM25 + 本地 embedding）**，回來跑這支，看 Recall/MRR 有沒有提升。這就是你 report 裡「我的改進有效」的客觀證據。

## 接到 Pi 跑 demo

```bash
cp models.json.example ~/.pi/agent/models.json    # 改成你的實際 model id（見 patloeber 文章）
PYTHONPATH=. pi -e ./pi-bridge/extension.ts           # bridge 會呼叫 python -m memory.cli
```

## 環境（請填）

- Python 版本：`______`（需 >= 3.10）
- 本地模型 / 量化：`______`  ｜ context size：`______`  ｜ 後端：`______`  ｜ VRAM：`______`

## Demo（必繳）

≤3 分鐘影片或截圖，放 `demo/` 或貼連結：session A 告訴 agent「這專案用 pnpm」→ 關閉 → session B 問相關問題，agent 透過注入「記得」了。

Demo 連結：`______`
