"""任務二：隱私過濾。capture 寫入硬碟前，以 regex 遮除常見密鑰／密碼。

設計重點：純函式、確定性、可單元測試——同樣輸入永遠得到同樣的遮罩結果，
不呼叫任何模型。於 `core.make_observation()` 內套用，連 SHA-256 id 也以遮罩後
文字計算，確保 secrets 不會以任何形式落到 memory.json。
"""
from __future__ import annotations
import re

_PLACEHOLDER = "[REDACTED]"

# key=value / key: value 形式（保留 key 名，只遮值）
_KV_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|api[_-]?key|secret|access[_-]?token|token)(\s*[=:]\s*)(\S+)"
)
# 具體密鑰格式（遮整段）
_TOKEN_RES = [
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}"),  # Authorization: Bearer ...
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}"),             # OpenAI / Stripe 私鑰
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),         # GitHub token
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                 # AWS access key id
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),       # Slack token
]


def redact(text: str) -> str:
    """回傳遮除密鑰後的文字。無敏感內容時原樣返回。"""
    if not text:
        return text
    out = _KV_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_PLACEHOLDER}", text)
    for rx in _TOKEN_RES:
        out = rx.sub(_PLACEHOLDER, out)
    return out
