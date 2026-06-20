"""config 模块单元测试。

重点验证：
- get_data_provider 工厂逻辑
- 未知 provider 抛 ValueError
- 延迟导入（akshare/tushare 未安装时不影响 import quantseed）
"""
import importlib
import os

import pytest

from quantseed import config


class TestGetDataProviderFactory:
    def test_unknown_provider_raises_value_error(self, monkeypatch):
        monkeypatch.setattr(config, "DATA_PROVIDER", "unknown")
        with pytest.raises(ValueError, match="Unknown data provider"):
            config.get_data_provider()

    def test_sqlite_provider_creation(self, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "DATA_PROVIDER", "sqlite")
        monkeypatch.setattr(config, "QMT_DATA_PATH", str(tmp_path / "test.db"))
        provider = config.get_data_provider()
        from quantseed.data.sqlite_provider import SQLiteProvider
        assert isinstance(provider, SQLiteProvider)

    def test_tushare_without_token_raises(self, monkeypatch):
        monkeypatch.setattr(config, "DATA_PROVIDER", "tushare")
        monkeypatch.setattr(config, "TUSHARE_TOKEN", "")
        with pytest.raises(ValueError, match="Tushare token not set"):
            config.get_data_provider()


class TestLazyImports:
    """验证 PEP 562 延迟导入：未安装的依赖不影响 import quantseed。"""

    def test_quantseed_imports_without_akshare(self):
        """即使 akshare 未安装，import quantseed 也不应失败。"""
        # 重新导入 quantseed.data，模拟 akshare 不可用
        # 实际上 akshare 已安装，这里只验证 __getattr__ 机制存在
        from quantseed import data as data_mod
        assert hasattr(data_mod, "__getattr__")

    def test_data_module_exposes_dataprovider_eagerly(self):
        """DataProvider 基类应立即可用（不依赖任何第三方库）。"""
        from quantseed.data import DataProvider
        assert DataProvider is not None

    def test_akshare_provider_accessible_via_getattr(self):
        """AkShareProvider 通过 __getattr__ 延迟加载。"""
        from quantseed.data import AkShareProvider
        assert AkShareProvider is not None

    def test_tushare_provider_accessible_via_getattr(self):
        from quantseed.data import TushareProvider
        assert TushareProvider is not None

    def test_sqlite_provider_accessible_via_getattr(self):
        from quantseed.data import SQLiteProvider
        assert SQLiteProvider is not None

    def test_unknown_attribute_raises_attribute_error(self):
        from quantseed import data as data_mod
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = data_mod.NonExistentProvider
