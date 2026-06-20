"""回测引擎 + 绩效指标的单元测试。"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from quantseed.backtest import Backtester, BacktestConfig, BacktestResult
from quantseed.backtest.metrics import (
    total_return,
    annual_return,
    max_drawdown,
    sharpe_ratio,
    compute_metrics,
)


# ========== metrics 测试 ==========

def _eq_df(equities):
    """构造 equity DataFrame。"""
    dates = [f"2024-01-{i+1:02d}" for i in range(len(equities))]
    return pd.DataFrame({
        "date": dates,
        "total_equity": equities,
        "cash": equities,
        "stock_value": [0] * len(equities),
        "positions": [0] * len(equities),
        "pnl_daily": [0] * len(equities),
    })


class TestTotalReturn:
    def test_positive_return(self):
        df = _eq_df([100000, 105000, 108000])
        assert total_return(df, 100000) == pytest.approx(0.08)

    def test_negative_return(self):
        df = _eq_df([100000, 95000, 90000])
        assert total_return(df, 100000) == pytest.approx(-0.10)

    def test_zero_return(self):
        df = _eq_df([100000, 100000])
        assert total_return(df, 100000) == 0.0

    def test_empty_df(self):
        assert total_return(pd.DataFrame(), 100000) == 0.0

    def test_missing_column(self):
        df = pd.DataFrame({"date": ["2024-01-01"]})
        assert total_return(df, 100000) == 0.0

    def test_zero_initial_capital(self):
        df = _eq_df([0, 100])
        assert total_return(df, 0) == 0.0


class TestAnnualReturn:
    def test_zero_days(self):
        assert annual_return(0.1, 0) == 0.0

    def test_one_year(self):
        # 252 个交易日，总收益 10% → 年化 10%
        assert annual_return(0.10, 252) == pytest.approx(0.10)

    def test_half_year(self):
        # 126 个交易日，总收益 5% → 年化约 10.25%
        ret = annual_return(0.05, 126)
        assert ret == pytest.approx(0.1025, rel=0.01)


class TestMaxDrawdown:
    def test_no_drawdown(self):
        df = _eq_df([100, 110, 120])
        dd_abs, dd_pct = max_drawdown(df)
        assert dd_abs == 0.0
        assert dd_pct == 0.0

    def test_simple_drawdown(self):
        df = _eq_df([100, 90, 80])
        dd_abs, dd_pct = max_drawdown(df)
        assert dd_abs == 20.0
        assert dd_pct == pytest.approx(-0.20)

    def test_recovery_then_new_low(self):
        df = _eq_df([100, 80, 90, 70])
        dd_abs, dd_pct = max_drawdown(df)
        assert dd_abs == 30.0
        assert dd_pct == pytest.approx(-0.30)

    def test_peak_updates(self):
        # 100 → 120 → 100 → 110：最大回撤从 120 到 100 = -20/120
        df = _eq_df([100, 120, 100, 110])
        dd_abs, dd_pct = max_drawdown(df)
        assert dd_abs == 20.0
        assert dd_pct == pytest.approx(-20/120)

    def test_empty_df(self):
        assert max_drawdown(pd.DataFrame()) == (0.0, 0.0)


class TestSharpeRatio:
    def test_empty_df(self):
        assert sharpe_ratio(pd.DataFrame()) == 0.0

    def test_single_row(self):
        df = _eq_df([100000])
        assert sharpe_ratio(df) == 0.0

    def test_constant_equity(self):
        # 无波动 → std=0 → 返回 0
        df = _eq_df([100000, 100000, 100000])
        assert sharpe_ratio(df) == 0.0

    def test_positive_trend(self):
        # 持续上涨 → 正夏普
        df = _eq_df([100000, 101000, 102000, 103000])
        assert sharpe_ratio(df) > 0

    def test_volatile_negative(self):
        # 大幅波动且下跌 → 负夏普
        df = _eq_df([100000, 90000, 105000, 85000])
        assert sharpe_ratio(df) < 0


class TestComputeMetrics:
    def test_full_dict(self):
        df = _eq_df([100000, 105000, 102000, 108000])
        m = compute_metrics(df, 100000, 4, num_trades=2)
        assert m["initial_capital"] == 100000
        assert m["final_equity"] == 108000
        assert m["total_return"] == pytest.approx(0.08)
        assert m["num_trades"] == 2
        assert m["num_trading_days"] == 4
        assert "annual_return" in m
        assert "max_drawdown" in m
        assert "max_drawdown_pct" in m
        assert "sharpe" in m

    def test_empty_equity(self):
        m = compute_metrics(pd.DataFrame(), 100000, 0)
        assert m["total_return"] == 0.0
        assert m["final_equity"] == 100000
        assert m["sharpe"] == 0.0


# ========== Backtester 测试 ==========

class _MockStrategy:
    """最小化的 mock 策略，记录每次钩子调用。"""

    def __init__(self, strategy_dir):
        self.strategy_dir = Path(strategy_dir)
        self.strategy_dir.mkdir(parents=True, exist_ok=True)
        self.data = None
        self.state = MagicMock()
        self.state.get = lambda key, default=None: {
            "cash": 100000.0,
            "positions": {},
        }.get(key, default)
        self.calls = []

    def on_open(self, now):
        self.calls.append(("on_open", now))

    def on_close(self, now):
        self.calls.append(("on_close", now))

    def on_eod(self, now):
        self.calls.append(("on_eod", now))


class _MockData:
    """最小化的 mock 数据源。"""

    def get_trade_calendar(self, start, end):
        # 返回 5 个连续工作日
        return [
            "2024-01-02", "2024-01-03", "2024-01-04",
            "2024-01-05", "2024-01-08",
        ]


class TestBacktester:
    def test_run_calls_hooks_in_order(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = _MockData()
        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-01-10",
            warmup_days=0,
            progress=False,
        )
        bt = Backtester(strategy, data, config)
        result = bt.run()

        # 5 个交易日 × 3 个钩子 = 15 次调用
        assert len(strategy.calls) == 15
        # 验证每天的调用顺序：on_open → on_close → on_eod
        for day_idx in range(5):
            base = day_idx * 3
            assert strategy.calls[base][0] == "on_open"
            assert strategy.calls[base + 1][0] == "on_close"
            assert strategy.calls[base + 2][0] == "on_eod"
        # 验证时间正确
        assert strategy.calls[0][1].hour == 9
        assert strategy.calls[0][1].minute == 25
        assert strategy.calls[1][1].hour == 14
        assert strategy.calls[1][1].minute == 45
        assert strategy.calls[2][1].hour == 15
        assert strategy.calls[2][1].minute == 5

    def test_warmup_skips_days(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = _MockData()
        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-01-10",
            warmup_days=2,
            progress=False,
        )
        bt = Backtester(strategy, data, config)
        result = bt.run()

        # 5 - 2 = 3 个交易日
        assert len(strategy.calls) == 9
        assert len(result.trading_days) == 3
        assert result.trading_days[0] == "2024-01-04"

    def test_empty_calendar_raises(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = MagicMock()
        data.get_trade_calendar.return_value = []
        config = BacktestConfig(
            start_date="2024-01-01", end_date="2024-01-10", progress=False
        )
        bt = Backtester(strategy, data, config)
        with pytest.raises(RuntimeError, match="交易日历为空"):
            bt.run()

    def test_too_much_warmup_raises(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = _MockData()
        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-01-10",
            warmup_days=10,  # 比总天数 5 还多
            progress=False,
        )
        bt = Backtester(strategy, data, config)
        with pytest.raises(RuntimeError, match="回测天数不足"):
            bt.run()

    def test_injects_data(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = _MockData()
        config = BacktestConfig(
            start_date="2024-01-01", end_date="2024-01-10", progress=False
        )
        bt = Backtester(strategy, data, config)
        bt.run()
        assert strategy.data is data

    def test_clean_artifacts_removes_files(self, tmp_path):
        d = tmp_path / "strat"
        d.mkdir()
        for name in ("state.json", "equity.csv", "trades.csv"):
            (d / name).write_text("dummy", encoding="utf-8")
        Backtester.clean_artifacts(d)
        for name in ("state.json", "equity.csv", "trades.csv"):
            assert not (d / name).exists()

    def test_clean_artifacts_missing_dir_ok(self, tmp_path):
        # 不存在的文件不应报错
        d = tmp_path / "nonexistent"
        d.mkdir()
        Backtester.clean_artifacts(d)  # 不应抛异常

    def test_result_summary_format(self, tmp_path):
        strategy = _MockStrategy(tmp_path / "strat")
        data = _MockData()
        config = BacktestConfig(
            start_date="2024-01-01", end_date="2024-01-10", progress=False
        )
        bt = Backtester(strategy, data, config)
        result = bt.run()
        summary = result.summary()
        assert "回测结果" in summary
        assert "总收益率" in summary
        assert "夏普比率" in summary
