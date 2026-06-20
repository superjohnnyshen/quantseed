"""策略状态持久化：JSON 读写，用于崩溃恢复。

每个策略有自己的 state.json，独立管理。
写入时先写临时文件再原子替换，防止写入中断导致文件损坏。
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StateStore:
    """简单的 JSON 状态持久化，支持原子写入。"""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._cache = None
        self._mtime = 0

    def load(self, default=None):
        # 如果文件未修改，返回缓存
        if (
            self._cache is not None
            and self.state_path.exists()
            and self.state_path.stat().st_mtime == self._mtime
        ):
            return self._cache

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
        # 临时文件名 = 原文件名 + ".tmp"，确保与原文件同目录同后缀
        tmp = self.state_path.with_name(self.state_path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 原子替换。Windows 下 OneDrive/杀软可能短暂锁住目标文件，加重试。
        for attempt in range(5):
            try:
                tmp.replace(self.state_path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                import time
                time.sleep(0.05 * (attempt + 1))
        self._cache = data
        # 用文件实际 mtime，确保后续 load() 缓存命中
        self._mtime = self.state_path.stat().st_mtime

    def update(self, **kwargs):
        data = self.load()
        data.update(kwargs)
        self.save(data)
        return data

    def get(self, key, default=None):
        data = self.load()
        return data.get(key, default)