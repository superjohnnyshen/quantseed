"""回测引擎模块。

用法:
    from quantseed.backtest import Backtester, BacktestConfig, BacktestResult
"""
from quantseed.backtest.engine import Backtester, BacktestConfig, BacktestResult
from quantseed.backtest.metrics import compute_metrics

__all__ = ["Backtester", "BacktestConfig", "BacktestResult", "compute_metrics"]
