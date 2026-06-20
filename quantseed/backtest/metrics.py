"""回测绩效指标计算。

所有函数接收 equity DataFrame（列：date, total_equity, pnl_daily），
返回纯数值或字典，不依赖任何 I/O。
"""
import math
from typing import Dict

import pandas as pd


def total_return(equity_df: pd.DataFrame, initial_capital: float) -> float:
    """总收益率。返回小数，如 0.088 表示 +8.8%。"""
    if equity_df.empty or "total_equity" not in equity_df.columns:
        return 0.0
    final = float(equity_df.iloc[-1]["total_equity"])
    if initial_capital <= 0:
        return 0.0
    return (final - initial_capital) / initial_capital


def annual_return(total_ret: float, num_trading_days: int) -> float:
    """年化收益率。按 252 个交易日年化。"""
    if num_trading_days <= 0:
        return 0.0
    # (1 + r)^(252/n) - 1
    return (1 + total_ret) ** (252 / num_trading_days) - 1


def max_drawdown(equity_df: pd.DataFrame):
    """最大回撤。返回 (绝对值, 百分比) 元组，百分比如 -0.12 表示 -12%。"""
    if equity_df.empty or "total_equity" not in equity_df.columns:
        return 0.0, 0.0
    equities = equity_df["total_equity"].astype(float).values
    peak = equities[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for v in equities:
        if v > peak:
            peak = v
        dd = peak - v
        dd_pct = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = -dd_pct  # 返回负数
    return float(max_dd), float(max_dd_pct)


def sharpe_ratio(equity_df: pd.DataFrame, annualization: int = 252) -> float:
    """夏普比率（简化版，无风险利率=0）。

    = mean(daily_return) / std(daily_return) * sqrt(252)
    """
    if equity_df.empty or "total_equity" not in equity_df.columns or len(equity_df) < 2:
        return 0.0
    equities = equity_df["total_equity"].astype(float).values
    # 日收益率序列
    daily_returns = []
    for i in range(1, len(equities)):
        prev = equities[i - 1]
        if prev > 0:
            daily_returns.append((equities[i] - prev) / prev)
        else:
            daily_returns.append(0.0)
    if not daily_returns:
        return 0.0
    mean_r = sum(daily_returns) / len(daily_returns)
    var_r = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
    std_r = math.sqrt(var_r)
    if std_r == 0:
        return 0.0
    return mean_r / std_r * math.sqrt(annualization)


def compute_metrics(
    equity_df: pd.DataFrame,
    initial_capital: float,
    num_trading_days: int,
    num_trades: int = 0,
) -> Dict[str, float]:
    """一次性计算全部指标，返回字典。"""
    ret = total_return(equity_df, initial_capital)
    dd_abs, dd_pct = max_drawdown(equity_df)
    final_eq = float(equity_df.iloc[-1]["total_equity"]) if (not equity_df.empty and "total_equity" in equity_df.columns) else float(initial_capital)
    return {
        "initial_capital": float(initial_capital),
        "final_equity": final_eq,
        "total_return": ret,
        "annual_return": annual_return(ret, num_trading_days),
        "max_drawdown": dd_abs,
        "max_drawdown_pct": dd_pct,
        "sharpe": sharpe_ratio(equity_df),
        "num_trades": int(num_trades),
        "num_trading_days": int(num_trading_days),
    }
