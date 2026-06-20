"""净值曲线追踪器：统一 CSV 格式，每日写入净值。

每个策略有独立的 equity.csv 和 trades.csv。
"""
import csv
import datetime
import os
from pathlib import Path


class EquityTracker:
    """简单的净值/交易日志记录器。"""

    def __init__(self, equity_path: Path, trades_path: Path):
        self.equity_path = Path(equity_path)
        self.trades_path = Path(trades_path)
        self._ensure_headers()

    def _ensure_headers(self):
        if not self.equity_path.exists():
            with open(self.equity_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([
                    "date", "total_equity", "cash", "stock_value",
                    "positions", "pnl_daily",
                ])
        if not self.trades_path.exists():
            with open(self.trades_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([
                    "datetime", "code", "name", "action", "price",
                    "qty", "amount", "strategy", "note",
                ])

    def record_equity(self, total_equity, cash, stock_value, positions, pnl_daily=0.0, date=None):
        """记录当日净值。

        Args:
            date: 可选日期。实盘默认今天，回测应传入当日的 date/datetime。
                  接受 datetime.date / datetime.datetime / 'YYYY-MM-DD' 字符串。
        """
        if date is None:
            date_str = datetime.date.today().strftime("%Y-%m-%d")
        elif isinstance(date, str):
            date_str = date
        elif isinstance(date, datetime.datetime):
            date_str = date.strftime("%Y-%m-%d")
        else:  # datetime.date
            date_str = date.strftime("%Y-%m-%d")
        self._append_csv(self.equity_path, [
            date_str, round(total_equity, 2), round(cash, 2),
            round(stock_value, 2), positions, round(pnl_daily, 2),
        ])

    def record_trade(self, code, name, action, price, qty, strategy, note="", dt=None):
        """记录一笔交易。

        Args:
            dt: 可选时间戳。实盘默认现在，回测应传入当时的 datetime。
                接受 datetime.datetime / 'YYYY-MM-DD HH:MM:SS' 字符串。
        """
        if dt is None:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(dt, str):
            now = dt
        else:  # datetime.datetime
            now = dt.strftime("%Y-%m-%d %H:%M:%S")
        amount = price * qty
        self._append_csv(self.trades_path, [
            now, code, name, action, price, qty, amount, strategy, note,
        ])

    @staticmethod
    def _append_csv(filepath: Path, row: list):
        """安全追加一行 CSV，使用 csv.writer 正确处理引号和逗号。"""
        # 追加模式写入，O(1) 复杂度
        with open(filepath, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

    def get_last_equity(self):
        if not self.equity_path.exists():
            return None
        with open(self.equity_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows:
            return None
        return rows[-1]