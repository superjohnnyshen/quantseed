"""EquityTracker 单元测试。"""
import csv
from pathlib import Path

from quantseed.equity_tracker import EquityTracker


def _read_csv(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.reader(f))


class TestEquityTrackerInit:
    def test_creates_equity_csv_with_header(self, tmp_strategy_dir: Path):
        eq = tmp_strategy_dir / "equity.csv"
        tr = tmp_strategy_dir / "trades.csv"
        EquityTracker(eq, tr)
        assert eq.exists()
        rows = _read_csv(eq)
        assert rows[0] == [
            "date", "total_equity", "cash", "stock_value",
            "positions", "pnl_daily",
        ]

    def test_creates_trades_csv_with_header(self, tmp_strategy_dir: Path):
        eq = tmp_strategy_dir / "equity.csv"
        tr = tmp_strategy_dir / "trades.csv"
        EquityTracker(eq, tr)
        assert tr.exists()
        rows = _read_csv(tr)
        assert rows[0] == [
            "datetime", "code", "name", "action", "price",
            "qty", "amount", "strategy", "note",
        ]

    def test_does_not_overwrite_existing_files(self, tmp_strategy_dir: Path):
        eq = tmp_strategy_dir / "equity.csv"
        tr = tmp_strategy_dir / "trades.csv"
        # 预先写入数据
        eq.write_text("date,total_equity\n2024-01-01,100000\n", encoding="utf-8")
        EquityTracker(eq, tr)
        # 已有数据应保留
        rows = _read_csv(eq)
        assert len(rows) == 2
        assert rows[1] == ["2024-01-01", "100000"]


class TestRecordEquity:
    def test_appends_row_with_correct_fields(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        tracker.record_equity(
            total_equity=100000.0,
            cash=80000.0,
            stock_value=20000.0,
            positions=3,
            pnl_daily=500.0,
        )
        rows = _read_csv(tmp_strategy_dir / "equity.csv")
        assert len(rows) == 2  # 表头 + 1 行
        row = rows[1]
        assert row[1] == "100000.0"   # total_equity
        assert row[2] == "80000.0"    # cash
        assert row[3] == "20000.0"    # stock_value
        assert row[4] == "3"          # positions
        assert row[5] == "500.0"      # pnl_daily

    def test_pnl_daily_defaults_to_zero(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        tracker.record_equity(100000, 100000, 0, 0)
        rows = _read_csv(tmp_strategy_dir / "equity.csv")
        assert rows[1][5] == "0.0"

    def test_multiple_appends_preserve_order(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        for i in range(5):
            tracker.record_equity(100000 + i, 100000, 0, 0)
        rows = _read_csv(tmp_strategy_dir / "equity.csv")
        assert len(rows) == 6  # 表头 + 5 行


class TestRecordTrade:
    def test_appends_trade_with_correct_fields(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        tracker.record_trade(
            code="600519",
            name="贵州茅台",
            action="BUY",
            price=1800.5,
            qty=100,
            strategy="demo",
            note="测试买入",
        )
        rows = _read_csv(tmp_strategy_dir / "trades.csv")
        assert len(rows) == 2
        row = rows[1]
        assert row[1] == "600519"
        assert row[2] == "贵州茅台"
        assert row[3] == "BUY"
        assert row[4] == "1800.5"
        assert row[5] == "100"
        # amount = price * qty = 180050.0
        assert float(row[6]) == 180050.0
        assert row[7] == "demo"
        assert row[8] == "测试买入"

    def test_trade_amount_calculated_correctly(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        tracker.record_trade("000001", "平安银行", "SELL", 15.3, 200, "test")
        rows = _read_csv(tmp_strategy_dir / "trades.csv")
        assert float(rows[1][6]) == 15.3 * 200


class TestGetLastEquity:
    def test_returns_none_when_file_missing(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        # 删除 equity.csv 模拟文件不存在
        (tmp_strategy_dir / "equity.csv").unlink()
        assert tracker.get_last_equity() is None

    def test_returns_none_when_only_header(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        assert tracker.get_last_equity() is None

    def test_returns_last_row_as_dict(self, tmp_strategy_dir: Path):
        tracker = EquityTracker(
            tmp_strategy_dir / "equity.csv",
            tmp_strategy_dir / "trades.csv",
        )
        tracker.record_equity(100000, 100000, 0, 0, 0)
        tracker.record_equity(105000, 80000, 25000, 2, 5000)
        last = tracker.get_last_equity()
        assert last is not None
        # round(105000, 2) 在 Python 中返回 105000（整数 float），CSV 写入为 "105000"
        assert float(last["total_equity"]) == 105000.0
        assert last["positions"] == "2"
