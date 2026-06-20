"""策略状态持久化：JSON 读写，用于崩溃恢复。

每个策略有自己的 state.json，独立管理。
写入时先写临时文件再原子替换，防止写入中断导致文件损坏。
"""
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class StateStore:
    """简单的 JSON 状态持久化，支持原子写入。"""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._cache = None
        self._mtime = 0

    def load(self, default=None):
        if not self.state_path.exists():
            return default if default is not None else {}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
            self._mtime = self.state_path.stat().st_mtime
            return self._cache
        except Exception as e:
            logger.warning("加载状态文件失败: %s - %s", self.state_path, e)
            return default if default is not None else {}

    def save(self, data):
        tmp = self.state_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.state_path)  # 原子替换
        self._cache = data
        self._mtime = time.time()

    def update(self, **kwargs):
        data = self.load()
        data.update(kwargs)
        self.save(data)
        return data

    def get(self, key, default=None):
        data = self.load()
        return data.get(key, default)