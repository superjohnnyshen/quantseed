from .interface import DataProvider

__all__ = ['DataProvider', 'AkShareProvider', 'TushareProvider', 'SQLiteProvider']


def __getattr__(name):
    """PEP 562 延迟导入：仅在实际访问时才加载对应 Provider，
    避免强制用户安装所有数据源依赖。"""
    if name == 'AkShareProvider':
        from .akshare_provider import AkShareProvider
        return AkShareProvider
    if name == 'TushareProvider':
        from .tushare_provider import TushareProvider
        return TushareProvider
    if name == 'SQLiteProvider':
        from .sqlite_provider import SQLiteProvider
        return SQLiteProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
