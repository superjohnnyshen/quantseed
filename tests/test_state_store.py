"""StateStore 单元测试。"""
import json
import time
from pathlib import Path

from quantseed.state_store import StateStore


class TestStateStoreLoad:
    def test_returns_default_when_file_missing(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        assert store.load() == {}
        assert store.load(default={"x": 1}) == {"x": 1}

    def test_loads_existing_json(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text('{"name": "demo", "count": 42}', encoding="utf-8")
        store = StateStore(path)
        data = store.load()
        assert data == {"name": "demo", "count": 42}

    def test_returns_default_on_corrupt_json(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text("not a json", encoding="utf-8")
        store = StateStore(path)
        # 损坏文件应返回默认值，不抛异常
        assert store.load(default={}) == {}

    def test_caches_result_when_file_unchanged(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text('{"v": 1}', encoding="utf-8")
        store = StateStore(path)
        first = store.load()
        # 第二次应命中缓存（不重新读文件）
        second = store.load()
        assert first is second  # 同一对象引用，说明用了缓存


class TestStateStoreSave:
    def test_writes_json_to_file(self, tmp_path: Path):
        path = tmp_path / "state.json"
        store = StateStore(path)
        store.save({"name": "test", "values": [1, 2, 3]})
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"name": "test", "values": [1, 2, 3]}

    def test_preserves_chinese_chars(self, tmp_path: Path):
        path = tmp_path / "state.json"
        store = StateStore(path)
        store.save({"name": "演示策略", "desc": "中文测试"})
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "演示策略"

    def test_overwrites_existing_content(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text('{"old": true}', encoding="utf-8")
        store = StateStore(path)
        store.save({"new": True})
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == {"new": True}
        assert "old" not in data

    def test_does_not_leave_temp_file(self, tmp_path: Path):
        path = tmp_path / "state.json"
        store = StateStore(path)
        store.save({"x": 1})
        # 临时文件应已被原子替换，不应残留
        assert not (tmp_path / "state.json.tmp").exists()

    def test_temp_file_uses_correct_name(self, tmp_path: Path):
        """临时文件名 = 原文件名 + .tmp（不能用 with_suffix，会破坏非 .json 后缀）。"""
        path = tmp_path / "state.dat"  # 非 .json 后缀
        store = StateStore(path)
        store.save({"x": 1})
        assert path.exists()
        assert not (tmp_path / "state.dat.tmp").exists()


class TestStateStoreCache:
    def test_cache_invalidates_on_file_change(self, tmp_path: Path):
        path = tmp_path / "state.json"
        path.write_text('{"v": 1}', encoding="utf-8")
        store = StateStore(path)
        first = store.load()
        # 修改文件 mtime（需要足够大的时间差，Windows 文件系统精度有限）
        time.sleep(0.1)
        path.write_text('{"v": 2}', encoding="utf-8")
        second = store.load()
        assert first is not second  # 缓存失效，重新读取
        assert second["v"] == 2


class TestStateStoreUpdate:
    def test_update_merges_keys(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        store.save({"a": 1, "b": 2})
        result = store.update(b=3, c=4)
        assert result == {"a": 1, "b": 3, "c": 4}
        # 持久化到文件
        data = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        assert data == {"a": 1, "b": 3, "c": 4}

    def test_update_on_empty_state(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        result = store.update(name="demo")
        assert result == {"name": "demo"}


class TestStateStoreGet:
    def test_get_existing_key(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        store.save({"name": "demo", "count": 10})
        assert store.get("name") == "demo"
        assert store.get("count") == 10

    def test_get_missing_key_returns_none(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        store.save({"name": "demo"})
        assert store.get("missing") is None

    def test_get_missing_key_with_default(self, tmp_path: Path):
        store = StateStore(tmp_path / "state.json")
        store.save({"name": "demo"})
        assert store.get("missing", "default") == "default"
