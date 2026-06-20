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

    def record_equity(self, total_equity, cash, stock_value, positions, pnl_daily=0.0):
        today = datetime.date.today().strftime("%Y-%m-%d")
        self._append_csv(self.equity_path, [
            today, round(total_equity, 2), round(cash, 2),
            round(stock_value, 2), positions, round(pnl_daily, 2),
        ])

    def record_trade(self, code, name, action, price, qty, strategy, note=""):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        amount = price * qty
        self._append_csv(self.trades_path, [
            now, code, name, action, price, qty, amount, strategy, note,
        ])

    @staticmethod
    def _append_csv(filepath: Path, row: list):
        """原子追加一行：先写临时文件，再 replace 确保写入不损坏原文件。"""
        # 读取已有内容
        content = []
        try:
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.readlines()
        except Exception:
            pass

        # 追加新行到内存
        output = "".join(content)
        output += ",".join(str(v) for v in row) + "\n"

        # 原子写入
        tmp = filepath.with_suffix(filepath.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(output)
        os.replace(tmp, filepath)

    def get_last_equity(self):
        if not self.equity_path.exists():
            return None
        with open(self.equity_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) < 2:
            return None
        return lines[-1].strip().split(",")