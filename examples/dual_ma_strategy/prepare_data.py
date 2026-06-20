"""准备双均线策略示例的测试数据。

生成一个 SQLite 数据库，包含 5 只股票 × 60 个交易日的日线数据。
价格用几何布朗运动模拟，让 MA5/MA20 交叉信号能自然产生。

用法:
    python examples/dual_ma_strategy/prepare_data.py
    # 生成 examples/dual_ma_strategy/data/demo.db
"""
import sqlite3
import datetime
from pathlib import Path
import numpy as np


def gen_price_series(start_price: float, days: int, seed: int) -> list:
    """生成模拟价格序列（几何布朗运动）。"""
    rng = np.random.default_rng(seed)
    # 日波动率 2%，漂移 0.05%
    returns = rng.normal(0.0005, 0.02, days)
    prices = [start_price]
    for r in returns:
        prices.append(prices[-1] * (1 + r))
    return prices[1:]


def gen_trade_calendar(start_date: datetime.date, days: int) -> list:
    """生成交易日历（跳过周末）。"""
    dates = []
    d = start_date
    while len(dates) < days:
        if d.weekday() < 5:  # 周一到周五
            dates.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)
    return dates


def main():
    db_path = Path(__file__).parent / "data" / "demo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 建表
    cur.execute("""
        CREATE TABLE daily_prices (
            trade_date TEXT, code TEXT,
            open REAL, close REAL, high REAL, low REAL,
            volume REAL, amount REAL, change_pct REAL, turnover_rate REAL
        )
    """)
    cur.execute("""
        CREATE TABLE stock_basic (
            code TEXT, name TEXT, list_date TEXT, delist_date TEXT
        )
    """)
    cur.execute("CREATE TABLE trade_calendar (trade_date TEXT)")

    # 5 只股票
    stocks = [
        ("600519", "贵州茅台", 1800.0, 42),
        ("000001", "平安银行", 15.0, 7),
        ("300750", "宁德时代", 200.0, 99),
        ("000858", "五粮液", 180.0, 13),
        ("601318", "中国平安", 50.0, 17),
    ]

    # 生成 60 个交易日
    start_date = datetime.date(2024, 1, 2)
    dates = gen_trade_calendar(start_date, 60)

    # 写入交易日历
    cur.executemany("INSERT INTO trade_calendar VALUES (?)", [(d,) for d in dates])

    # 写入 stock_basic
    cur.executemany(
        "INSERT INTO stock_basic VALUES (?,?,?,?)",
        [(code, name, "2020-01-01", "") for code, name, *_ in stocks],
    )

    # 写入日线数据
    for code, name, start_price, seed in stocks:
        prices = gen_price_series(start_price, len(dates), seed)
        rows = []
        for i, (date, close) in enumerate(zip(dates, prices)):
            open_ = close * (1 + np.random.default_rng(seed + i).normal(0, 0.005))
            high = max(open_, close) * 1.005
            low = min(open_, close) * 0.995
            volume = 1_000_000 + np.random.default_rng(seed + i + 100).integers(0, 500_000)
            amount = volume * (open_ + close) / 2
            change_pct = (close - open_) / open_ * 100
            turnover = volume / 100_000_000 * 100  # 模拟换手率
            rows.append((
                date, code, round(open_, 2), round(close, 2),
                round(high, 2), round(low, 2),
                float(volume), float(amount),
                round(change_pct, 4), round(turnover, 4),
            ))
        cur.executemany("INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    conn.commit()
    conn.close()

    print(f"测试数据已生成: {db_path}")
    print(f"  股票数: {len(stocks)}")
    print(f"  交易日数: {len(dates)}")
    print(f"  日期范围: {dates[0]} ~ {dates[-1]}")


if __name__ == "__main__":
    main()
