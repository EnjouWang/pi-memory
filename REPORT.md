# Evaluation Report

> 中文版：[`REPORT.zh-TW.md`](REPORT.zh-TW.md)

This report covers how retrieval quality was measured, where pure BM25 fails, how hybrid retrieval fixes those failures, and the main design trade-offs.

## 1. Methodology

All corpus entries are captured into a temporary memory store. Each benchmark query is then run through `retrieve()`, and the ranked results are compared with hand-labelled relevant IDs (`benchmark/run_benchmark.py`).

| Metric | What it measures |
|---|---|
| **Recall@k** | Did the relevant memories make it into the top k? (can it be found at all) |
| **MRR** | How high is the first relevant memory ranked? |
| **nDCG@k** | Overall ranking quality with multiple relevant answers and position discount |

Two datasets are used:

| Dataset | Size | Purpose |
|---|---|---|
| `corpus.jsonl` / `queries.jsonl` | 30 docs / 21 queries | Baseline |
| `corpus_large.jsonl` / `queries_large.jsonl` | 100 docs / 40 queries | Many same-topic distractors, synonym and English ↔ Chinese queries |

**Why the numbers are trustworthy.** `bm25_search()` and `retrieve()` are deterministic: no model calls, no randomness, stable tie-breaking. Corpus and labels are fixed external data, so anyone can reproduce the same numbers in a clean environment, and hard-coding answers for known queries would fail immediately on a different dataset with the same format.

## 2. Results

Pure BM25 (k1 = 1.5, b = 0.75) vs. hybrid retrieval (α = 0.2), k = 5:

| Metric | Base: BM25 → Hybrid | Large: BM25 → Hybrid |
|---|---|---|
| Recall@5 | 0.810 → **1.000** | 0.838 → **0.988** |
| MRR | 0.810 → **0.976** | 0.826 → **0.958** |
| nDCG@5 | 0.802 → **0.982** | 0.795 → **0.953** |

The pure-BM25 numbers match the reference values for standard BM25 on both datasets, which confirms the implementation is correct. Hybrid is never worse than BM25 on either dataset.

## 3. Where pure BM25 fails

On the large corpus, **3 queries get Recall = 0** and **7 get Recall = 0.5**. Every failure comes from a limit of lexical matching.

### Failure 1 — Vocabulary mismatch (synonyms, hypernyms, no stemming)

| Query | Relevant memory | Why BM25 scores 0 |
|---|---|---|
| what **package manager** should I use? | L001 *uses pnpm, not npm* | The query uses a hypernym; the memory only names the concrete tool |
| what **payment provider** do we use? | L077 *Payments are processed by Stripe* | "provider" never appears; `payment` ≠ `Payments` without stemming |
| how big can an uploaded **picture** be? | L048 *Image uploads … maximum size 10MB* | "picture" ↔ "image", "how big" ↔ "size": no shared tokens |

### Failure 2 — Cross-lingual queries

Several topics have both an English and a Chinese memory as correct answers. CJK characters and Latin words share no tokens, so BM25 only finds the version in the query's language (Recall = 0.5):

| Query (language) | Found | Missed (other language) |
|---|---|---|
| roll out features gradually (EN) | L044 | L090 (ZH) feature flags |
| error tracking (EN) | L068 | L095 (ZH) Sentry |
| architecture decisions (EN) | L064 | L087 (ZH) ADR |
| 正式環境的密碼金鑰放哪？ (ZH) | L085 | L034 (EN) secrets in Vault |
| 怎麼確認程式碼風格符合規範？ (ZH) | L091 | L027 (EN) ruff and black |
| 登入的 token 多久過期？ (ZH) | L097 | L035 (EN) JWT, 24-hour expiry |
| 新功能慢慢開放給部分使用者 (ZH) | L090 | L044 (EN) LaunchDarkly |

### Failure 3 — Distractor dilution (hurts MRR / nDCG, not Recall)

Relevant memories reach the top 5 but get pushed below noise that shares common words. For example, for *"what python version…"* the answer L005 ranks second behind L029 (type checking), which also contains "python". As the corpus grows, common words (project, test, api…) appear in many documents and dilute the ranking.

Failures 1 and 2 are semantic and cross-lingual gaps that no amount of k1/b tuning can fix. They motivated adding embeddings.

## 4. How hybrid retrieval fixes them

**Method** (`memory/hybrid.py`):

1. Compute BM25 scores for **all** candidates, not only the top k.
2. Compute cosine similarity with a local multilingual model, `paraphrase-multilingual-MiniLM-L12-v2`. Document vectors are cached by (id, text).
3. Min-max normalise both score lists separately, then fuse: `score = α · lexical + (1 − α) · semantic`.

**Effect on the large corpus:**

- **Vocabulary mismatch fixed:** *package manager* → L001 (pnpm) and *payment provider* → L077 (Stripe) go from Recall 0 to 1.
- **Cross-lingual fixed:** *uploaded picture* now finds both L048 (EN) and L089 (ZH), going from 0 to 1. The English ↔ Chinese pairs go from 0.5 to 1.
- **Distractors reduced:** MRR goes from 0.826 to 0.958 and nDCG from 0.795 to 0.953.
- **One query left at Recall 0.5:** *merge policy for pull requests*. L024 is found, but the near-duplicate L025 falls just outside the top 5. This is a fine-grained ranking issue, not a semantic gap.

**Choosing α:** I swept α from 0.5 down to 0.2, and 0.2 was best overall. Semantics should lead, with BM25 helping to break ties between similar candidates.

## 5. Design trade-offs

### Deterministic shell, probabilistic core

| Deterministic, unit-tested | Probabilistic |
|---|---|
| `tokenize()`, `bm25_search()`, `JsonStore` (load / persist / SHA-256 dedup / delete), budget truncation in `build_injection()`, `privacy.redact()`, `forget()`, benchmark scoring | Embedding similarity in hybrid mode; deciding *what* is worth remembering (done by the agent through the `remember` tool) |

Verifiable logic stays deterministic, so tests, benchmarks and debugging each have a single correct answer. Only the semantic matching that cannot be written as rules goes to a model. `bm25_search()` is never mixed with embeddings: hybrid is a separate function enabled by `PI_MEMORY_HYBRID=1`, so the core path stays reproducible.

### Token budget for injection

The default budget is **2000 tokens**, estimated as `len(text) / 4`. Memories are added in score order until the budget is used up.

- **Too large:** it crowds the limited context of a small local model, dilutes the current task, adds latency, and lets stale or irrelevant memories distract the model.
- **Too small:** relevant memories get cut off, so the agent behaves as if it never remembered them.

The principle is to inject a few high-scoring memories rather than everything.

### Privacy filter

Redaction runs inside `make_observation()`, before the content hash ID is computed, so secrets never reach `memory.json` in any form, not even as part of a hash input. It is regex-based: deterministic and free, but best-effort. Unusual secret formats may slip through, and some benign strings may be over-masked.

### Relation to `/compact` and hand-written notes

- **`/compact`:** it compresses history *within* one session. This system persists knowledge *across* sessions. They work together rather than compete.
- **A hand-written `PROGRESS.md`:** it is better for a small number of high-value, stable decisions such as architecture choices or team rules. Automatic memory is better for frequent, changing conventions that are picked up during work.

## 6. Environment

| Item | Version |
|---|---|
| Python | 3.10.12 (core uses the standard library only) |
| pytest | 9.0.3 |
| Hybrid dependencies | sentence-transformers 5.5.1, torch 2.12.0, numpy 2.2.6 |
| Embedding model | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, local CPU inference |
| Demo LLM | `qwen3:14b`, 32k context, Ollama, TITAN RTX 24 GB |
| Pi | `@earendil-works/pi-coding-agent` 0.74.2, Node.js ≥ 20 |
