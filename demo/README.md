# Demo — 跨 session 記憶生效

本檔是錄製腳本。目標：展示 agent 在**關掉重開後仍記得**上一個 session 教它的慣例，並順帶展示進階功能（隱私過濾、/recall、/forget、hybrid retrieval）。

> 影片連結：[https://youtu.be/YbtzJhaWpM8]

---

## 0. 錄製前準備

```bash
cd <此 repo 根目錄>
source env/bin/activate
pip install -r requirements.txt          # 已裝可略
cp models.json.example ~/.pi/agent/models.json   # 改成本地 model id
```

- 本地 OpenAI-compatible 後端（LM Studio / Ollama / llama-server）先啟動好。
- 錄製前先清掉舊記憶：`rm -f ~/.pi-memory.json`
- 腳本 A 走**預設純 BM25**（不需設環境變數）。hybrid 的優勢用**腳本 B4 的 benchmark** 呈現；該處指令已自帶 `PI_MEMORY_HYBRID=1`，不必先在 shell 設。
- `PI_MEMORY_HYBRID=1` 只在「想讓某次執行走 hybrid」時設，且**必須在啟動該行程之前** export（pi 透過子行程繼承環境變數；pi 已開著才設不會生效）。
- 建議錄製時加掛 permission-gate，agent 跑每條 bash 前先問你 Yes/No，避免本地小模型亂下指令：`PYTHONPATH=. pi -e ./pi-bridge/extension.ts -e ./pi-bridge/permission-gate.ts`（需 Node >= 20）。

---

## 腳本 A：Pi 實機 demo

> 在 Session A 教**兩項**慣例（一英一中），Session B 用不同問題**分別驗證**——兩例已足夠展示跨 session 記憶。
> 重點是 **Retrieve**：注入用「你當下的問題」當查詢，不同問題取回不同記憶。
> 腳本走**預設純 BM25**（不需設 `PI_MEMORY_HYBRID`；hybrid 的優勢改用 **B4 benchmark** 呈現）。

### Session A — 教 agent 兩項慣例（Capture）
```bash
PYTHONPATH=. pi -e ./pi-bridge/extension.ts -e ./pi-bridge/permission-gate.ts
```
**逐則**對 agent 說（每則確認模型有呼叫 `remember` 工具再講下一則）：

> 1.（英）「Remember: this project uses **pnpm**, not npm. Run tests with `pnpm test`.」
> 2.（中）「記住：**commit message 一律用繁體中文**，送 PR 前要先跑 `make lint`。」

每則模型應呼叫 **`remember` 工具** → bridge 觸發 `capture` → 寫入 `~/.pi-memory.json`。
（這就是 **Capture + Store**，每筆以 summary 的 SHA-256 當 id 去重後落盤。）

教完後用 `/quit` **關閉** agent（session 結束、context 清空）。

### Session B — 重開全新 session，分別驗證它記得（Retrieve + Inject）
```bash
PYTHONPATH=. pi -e ./pi-bridge/extension.ts -e ./pi-bridge/permission-gate.ts
```
**用兩個不同問題分別提問**，每題都應取回對應記憶、直接照慣例回答而不反問：

| 問（語言） | 期望 agent 已「記得」 | 命中的記憶 |
|---|---|---|
| （英）「How do I run the tests?」 | 用 `pnpm test` | 第 1 則（英）|
| （中英混）「幫我把這次修改 commit 起來」 | commit message 用繁體中文、先跑 `make lint` | 第 2 則（中）|

每次 agent 開工前，bridge 的 `before_agent_start` 會用**這句問題**當查詢呼叫 `inject`，注入最相關的記憶，因此 agent 直接照慣例回答。
（這就是跨 session 的 **Retrieve + Inject**——上個 session 關掉後知識仍在硬碟。）

> 💡 觀察重點：
> - **依問題挑選**：問「run tests」取回 pnpm 那筆、問「commit」取回中文那筆，不是全部倒回去——這正是 token 預算下的取捨。
> - 第 2 題是**中英混問句命中中文記憶**，靠共享的英文關鍵字 `commit` 接到，**純 BM25 即可**（不需 hybrid）。
>
> ⚠️ **小記憶集不要展示 hybrid**：筆數少時 embedding 排序不穩，hybrid 可能把正解擠掉。hybrid 勝過 BM25 的**可重現證據**請看 **B4 的 benchmark**（100 筆語料、刻意設計詞彙/跨語言落差，Recall@5 0.838→0.988）。

> 對照：Pi 內建的 `/compact` 只壓縮**單一 session** 內的對話，關掉就忘；本系統把知識寫進硬碟，**下個 session 才取回**，兩者互補。

---

## 腳本 B：進階功能

先指定一個乾淨記憶檔：
```bash
export PI_MEMORY_PATH=$(mktemp --suffix=.json)
```

### B1. 隱私過濾（capture 前遮除密鑰）
```bash
PYTHONPATH=. python -m memory.cli capture --summary "deploy key api_key=sk-ABCDEFGH1234567890abcd"
PYTHONPATH=. python -m memory.cli recall  --query "deploy key" --k 3
grep -o "sk-[A-Za-z0-9]*\|REDACTED" "$PI_MEMORY_PATH"   # 只會看到 REDACTED
```
密鑰在**寫入硬碟前**就被遮成 `[REDACTED]`，連 id 都以遮罩後文字計算。

### B2. `/recall`（人類可讀取回）
```bash
PYTHONPATH=. python -m memory.cli capture --summary "this project uses pnpm test"
PYTHONPATH=. python -m memory.cli recall --query "how do I run tests" --k 3
```
依當前問句檢索最相關記憶並列出。

### B3. `/forget`（遺忘）
```bash
PYTHONPATH=. python -m memory.cli forget --query "deploy key"   # 依子字串刪除
PYTHONPATH=. python -m memory.cli recall --query "deploy key" --k 3
```
可依 `--query` 子字串或 `--id` 精確刪除，刪除後立即 persist。

### B4.（選）Hybrid 修好純 BM25 接不到的題
```bash
# 純 BM25：跨語言 / 同義詞題接不到
PYTHONPATH=. python benchmark/run_benchmark.py --corpus corpus_large.jsonl --queries queries_large.jsonl --k 5
# Hybrid：Recall@5 0.838 → 0.988
PYTHONPATH=. PI_MEMORY_HYBRID=1 python benchmark/run_benchmark.py --corpus corpus_large.jsonl --queries queries_large.jsonl --k 5
```
embedding 把「package manager↔pnpm」「英文查詢↔中文記憶」的字面落差補起來。

```bash
rm -f "$PI_MEMORY_PATH"   # 收尾
```