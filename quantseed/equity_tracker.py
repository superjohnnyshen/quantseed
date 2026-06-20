"""净值曲线追踪器：统一 CSV 格式，每日写入净值。

每个策略有独立的 equity.csv 和 trades.csv。
"""
import csv
import datetime
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

    def record_equity(self, total_equity, cash, stock_value, positions, pnl_daily=0.0):
        today = datetime.date.today().strftime("%Y-%m-%d")
        with open(self.equity_path, "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                today, round(total_equity, 2), round(cash, 2),
                round(stock_value, 2), positions, round(pnl_daily, 2),
            ])

    def record_trade(self, code, name, action, price, qty, strategy, note=""):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        amount = price * qty
        with open(self.trades_path, "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                now, code, name, action, price, qty, amount, strategy, note,
            ])

    def get_last_equity(self):
        if not self.equity_path.exists():
            return None
        with open(self.equity_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) < 2:
            return None
        return lines[-1].strip().split(",")