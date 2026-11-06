"""持久層：把記憶存成 JSON 檔，重啟後讀得回來，並用 id 去重。"""
from __future__ import annotations
import json
import os


class JsonStore:
    def __init__(self, path: str):
        self.path = path
        self.items: list[dict] = []
        self.load()

    def load(self) -> None:
        """從硬碟讀回 self.items。
        檔案不存在、解析失敗、或內容不是 list（例如 {}）都一律視為空 list。"""
        if not os.path.exists(self.path):
            self.items = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            self.items = []
            return
        self.items = data if isinstance(data, list) else []

    def _persist(self) -> None:
        """把 self.items 寫回硬碟（JSON）。"""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)

    def add(self, obs: dict) -> bool:
        """新增一筆；id 已存在則跳過（去重），回傳是否真的新增。新增後 _persist()。"""
        if any(o["id"] == obs["id"] for o in self.items):
            return False
        self.items.append(obs)
        self._persist()
        return True

    def delete(self, obs_id: str) -> bool:
        """依 id 刪除一筆（供 /forget）；有刪到回 True 並 _persist()。"""
        n = len(self.items)
        self.items = [o for o in self.items if o["id"] != obs_id]
        if len(self.items) != n:
            self._persist()
            return True
        return False

    def delete_where(self, pred) -> int:
        """刪除所有符合 pred(obs) 的記憶（供 /forget --query）；回傳刪除筆數。"""
        n = len(self.items)
        self.items = [o for o in self.items if not pred(o)]
        removed = n - len(self.items)
        if removed:
            self._persist()
        return removed

    def all(self) -> list[dict]:
        return list(self.items)

    def clear(self) -> None:
        self.items = []
        self._persist()
