"""回测引擎：在历史交易日上逐日驱动策略执行。

设计原则：
1. 镜像 scheduler 的实盘流程：on_open → on_close → on_eod
2. 不修改策略状态结构，只注入数据源 + 用历史时间触发
3. 回测结束后从 equity.csv 读取净值曲线并计算绩效指标

用法:
    from quantseed.backtest import Backtester, BacktestConfig

    config = BacktestConfig(
        start_date="2024-01-01",
        end_date="2024-12-31",
        warmup_days=25,  # 跳过前 25 天（均线预热）
    )
    bt = Backtester(strategy, data, config)
    result = bt.run()
    print(result.summary())
"""
import csv
import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import pandas as pd

from quantseed.backtest.metrics import compute_metrics

if TYPE_CHECKING:
    from quantseed.strategy_base import BaseStrategy
    from quantseed.data.interface import DataProvider


@dataclass
class BacktestConfig:
    """回测参数。"""
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    warmup_days: int = 0  # 跳过前 N 个交易日（指标预热）
    progress: bool = True  # 打印进度


@dataclass
class BacktestResult:
    """回测结果。"""
    metrics: dict
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    trading_days: list

    def summary(self) -> str:
        """生成文本摘要。"""
        m = self.metrics
        return (
            f"=== 回测结果 ===\n"
            f"  回测区间:     {self.trading_days[0]} ~ {self.trading_days[-1]} "
            f"({m['num_trading_days']} 个交易日)\n"
            f"  初始资金:     {m['initial_capital']:.2f}\n"
            f"  最终净值:     {m['final_equity']:.2f}\n"
            f"  总收益率:     {m['total_return']:+.2%}\n"
            f"  年化收益率:   {m['annual_return']:+.2%}\n"
            f"  最大回撤:     {m['max_drawdown']:.2f} ({m['max_drawdown_pct']:+.2%})\n"
            f"  夏普比率:     {m['sharpe']:.3f}\n"
            f"  交易次数:     {m['num_trades']}\n"
        )


class Backtester:
    """回测引擎。

    Args:
        strategy: 策略实例（已初始化，strategy_dir 指向可写目录）
        data: 数据源（DataProvider 实例）
        config: 回测参数
    """

    def __init__(
        self,
        strategy: "BaseStrategy",
        data: "DataProvider",
        config: BacktestConfig,
    ):
        self.strategy = strategy
        self.data = data
        self.config = config

    def run(self) -> BacktestResult:
        """执行回测，返回结果。

        注意：调用方应保证 strategy_dir 下没有上一次回测的 state/equity/trades，
        否则状态会延续。推荐在构造策略前清理这些文件。
        """
        # 1. 注入数据源
        self.strategy.data = self.data

        # 2. 获取交易日历
        calendar = self.data.get_trade_calendar(
            self.config.start_date, self.config.end_date
        )
        if not calendar:
            raise RuntimeError(
                f"交易日历为空: {self.config.start_date} ~ {self.config.end_date}"
            )

        # 3. 跳过预热天数
        warmup = min(self.config.warmup_days, len(calendar) - 1)
        trading_days = calendar[warmup:]
        if len(trading_days) < 2:
            raise RuntimeError(
                f"回测天数不足: warmup={warmup}, 总天数={len(calendar)}"
            )

        if self.config.progress:
            print(f"=== 回测开始 ===")
            print(f"  区间: {trading_days[0]} ~ {trading_days[-1]} "
                  f"({len(trading_days)} 个交易日, 预热 {warmup} 天)")

        # 4. 逐日驱动
        for i, date_str in enumerate(trading_days, 1):
            dt_open = self._make_dt(date_str, 9, 25)
            dt_close = self._make_dt(date_str, 14, 45)
            dt_eod = self._make_dt(date_str, 15, 5)

            try:
                self.strategy.on_open(dt_open)
                self.strategy.on_close(dt_close)
                self.strategy.on_eod(dt_eod)
            except Exception as e:
                print(f"[backtest] 第 {i} 天 {date_str} 异常: {e}")
                raise

            if self.config.progress and (i % 10 == 0 or i == len(trading_days)):
                cash = self.strategy.state.get("cash", 0.0)
                positions = self.strategy.state.get("positions", {})
                print(f"  [{i}/{len(trading_days)}] {date_str} "
                      f"持仓 {len(positions)} 只, 现金 {cash:.2f}")

        # 5. 读取结果
        equity_curve = self._read_equity_csv()
        trades = self._read_trades_csv()
        num_trades = len(trades)

        metrics = compute_metrics(
            equity_df=equity_curve,
            initial_capital=self.config.initial_capital,
            num_trading_days=len(trading_days),
            num_trades=num_trades,
        )

        if self.config.progress:
            print(BacktestResult(metrics, equity_curve, trades, trading_days).summary())

        return BacktestResult(metrics, equity_curve, trades, trading_days)

    # ========== 内部工具 ==========

    @staticmethod
    def clean_artifacts(strategy_dir) -> None:
        """清理 strategy_dir 下的 state/equity/trades 文件。

        应在构造策略前调用，保证回测从干净状态开始。
        """
        from pathlib import Path
        d = Path(strategy_dir)
        for name in ("state.json", "equity.csv", "trades.csv"):
            p = d / name
            if p.exists():
                try:
                    p.unlink()
                except PermissionError:
                    import time
                    time.sleep(0.1)
                    try:
                        p.unlink()
                    except PermissionError:
                        pass

    @staticmethod
    def _make_dt(date_str: str, hour: int, minute: int) -> datetime.datetime:
        """把 'YYYY-MM-DD' 字符串转为指定时分 的 datetime。"""
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=hour, minute=minute, second=0
        )

    def _read_equity_csv(self) -> pd.DataFrame:
        path = self.strategy.strategy_dir / "equity.csv"
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _read_trades_csv(self) -> pd.DataFrame:
        path = self.strategy.strategy_dir / "trades.csv"
        if not path.exists():
            return pd.DataFrame()
        try:
            # code/name 保持字符串，避免 '000001' 被推断成 1
            return pd.read_csv(path, dtype={"code": str, "name": str})
        except Exception:
            return pd.DataFrame()
