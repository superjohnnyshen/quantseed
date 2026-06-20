"""QuantSeed - 量化策略从零到一启动包。

三件套：SOP 方法论 + 多策略框架 + 数据管道。

用法:
    from quantseed import BaseStrategy, Scheduler, DataProvider
"""
__version__ = "0.1.3"

from .strategy_base import BaseStrategy
from .scheduler import Scheduler
from .equity_tracker import EquityTracker
from .state_store import StateStore
from .trading import TradingAPI
from .data import DataProvider, AkShareProvider, TushareProvider, SQLiteProvider
from .config import get_data_provider, DATA_PROVIDER

__all__ = [
    'BaseStrategy', 'Scheduler', 'EquityTracker', 'StateStore',
    'TradingAPI', 'DataProvider', 'AkShareProvider',
    'TushareProvider', 'SQLiteProvider', 'get_data_provider', 'DATA_PROVIDER'
]