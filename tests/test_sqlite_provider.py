"""SQLiteProvider 单元测试。

重点验证：
- codes 自动 zfill(6)
- 分块查询逻辑（>500 个 codes 不报错）
- 空列表边界
- 参数上限规避
"""
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from quantseed.data.sqlite_provider import SQLiteProvider, _MAX_PARAMS


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    """构造一个临时 SQLite 数据库，包含 daily_prices / stock_basic / fundamentals 表。"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # daily_prices 表
    cur.execute("""
        CREATE TABLE daily_prices (
            trade_date TEXT,
            code TEXT,
            open REAL, close REAL, high REAL, low REAL,
            volume REAL, amount REAL, change_pct REAL, turnover_rate REAL
        )
    """)
    # 插入测试数据：3 只股票 × 2 天
    # 注意：code 在数据库里统一存 6 位，zfill 后应能匹配
    rows = [
        ("2024-01-01", "000001", 10, 11, 12, 9, 1000, 11000, 10.0, 1.5),
        ("2024-01-02", "000001", 11, 12, 13, 10, 1200, 14400, 9.0, 1.8),
        ("2024-01-01", "600519", 1800, 1810, 1820, 1790, 500, 905000, 0.5, 0.1),
        ("2024-01-02", "600519", 1810, 1820, 1830, 1800, 600, 1092000, 0.6, 0.2),
        ("2024-01-01", "300750", 200, 205, 208, 198, 5000, 1025000, 2.5, 1.0),
        ("2024-01-02", "300750", 205, 210, 212, 203, 4800, 1008000, 2.4, 0.9),
    ]
    cur.executemany(
        "INSERT INTO daily_prices VALUES (?,?,?,?,?,?,?,?,?,?)", rows
    )

    # stock_basic 表
    cur.execute("""
        CREATE TABLE stock_basic (
            code TEXT, name TEXT, list_date TEXT, delist_date TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO stock_basic VALUES (?,?,?,?)",
        [
            ("000001", "测试股票A", "2020-01-01", ""),
            ("600519", "贵州茅台", "2001-08-27", ""),
            ("300750", "宁德时代", "2018-06-11", ""),
        ],
    )

    # fundamentals 表
    cur.execute("""
        CREATE TABLE fundamentals (
            code TEXT, report_date TEXT, revenue REAL, net_profit REAL
        )
    """)
    cur.executemany(
        "INSERT INTO fundamentals VALUES (?,?,?,?)",
        [
            ("000001", "2024-03-31", 1e8, 1e7),
            ("600519", "2024-03-31", 4e10, 2e10),
            ("300750", "2024-03-31", 1e11, 3e10),
        ],
    )

    # trade_calendar 表
    cur.execute("CREATE TABLE trade_calendar (trade_date TEXT)")
    cur.executemany(
        "INSERT INTO trade_calendar VALUES (?)",
        [("2024-01-01",), ("2024-01-02",), ("2024-01-03",)],
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def provider(sqlite_db: Path) -> SQLiteProvider:
    return SQLiteProvider(str(sqlite_db))


class TestNormalizeCodes:
    def test_zfills_short_codes(self):
        assert SQLiteProvider._normalize_codes(["1", "600519"]) == ["000001", "600519"]

    def test_preserves_full_length_codes(self):
        assert SQLiteProvider._normalize_codes(["000001", "600519"]) == ["000001", "600519"]

    def test_handles_int_input(self):
        assert SQLiteProvider._normalize_codes([1, 600519]) == ["000001", "600519"]

    def test_handles_empty_list(self):
        assert SQLiteProvider._normalize_codes([]) == []


class TestChunked:
    def test_yields_chunks_of_specified_size(self):
        items = list(range(10))
        chunks = list(SQLiteProvider._chunked(items, size=3))
        assert chunks == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

    def test_single_chunk_when_under_size(self):
        items = [1, 2, 3]
        chunks = list(SQLiteProvider._chunked(items, size=10))
        assert chunks == [[1, 2, 3]]

    def test_empty_list_yields_nothing(self):
        assert list(SQLiteProvider._chunked([], size=5)) == []


class TestGetDailyPrices:
    def test_empty_codes_returns_empty_df(self, provider: SQLiteProvider):
        df = provider.get_daily_prices([], "2024-01-01", "2024-01-02")
        assert df.empty

    def test_zfills_short_code(self, provider: SQLiteProvider):
        """传入 '1' 应 zfill 为 '000001'，能查到 code='000001' 的数据。"""
        df = provider.get_daily_prices(["1"], "2024-01-01", "2024-01-02")
        assert not df.empty
        assert len(df) == 2
        assert df.iloc[0]["code"] == "000001"

    def test_full_code_returns_data(self, provider: SQLiteProvider):
        df = provider.get_daily_prices(["600519"], "2024-01-01", "2024-01-02")
        assert not df.empty
        assert len(df) == 2
        assert "close" in df.columns

    def test_multiple_codes(self, provider: SQLiteProvider):
        df = provider.get_daily_prices(["600519", "300750"], "2024-01-01", "2024-01-02")
        assert len(df) == 4  # 2 只 × 2 天

    def test_date_range_filter(self, provider: SQLiteProvider):
        df = provider.get_daily_prices(["600519"], "2024-01-02", "2024-01-03")
        assert len(df) == 1
        assert df.iloc[0]["trade_date"] == "2024-01-02"

    def test_large_code_list_does_not_hit_param_limit(self, provider: SQLiteProvider):
        """构造 >_MAX_PARAMS 个 codes，验证不触发 SQLite 参数上限。"""
        # 生成大量不存在的 code + 2 个真实存在的
        codes = ["600519", "300750"] + [f"{i:06d}" for i in range(1000, 2200)]
        # 不应抛 sqlite3.OperationalError: too many SQL variables
        df = provider.get_daily_prices(codes, "2024-01-01", "2024-01-02")
        assert not df.empty
        # 应只查到 2 只真实存在的股票 × 2 天 = 4 行
        assert len(df) == 4


class TestGetStockBasic:
    def test_returns_all_stocks(self, provider: SQLiteProvider):
        df = provider.get_stock_basic()
        assert len(df) == 3
        assert "code" in df.columns
        assert "name" in df.columns

    def test_zfills_codes(self, provider: SQLiteProvider):
        df = provider.get_stock_basic()
        # code='1' 应被 zfill 为 '000001'
        assert "000001" in df["code"].tolist()

    def test_filter_by_codes(self, provider: SQLiteProvider):
        df = provider.get_stock_basic(["600519"])
        assert len(df) == 1
        assert df.iloc[0]["name"] == "贵州茅台"

    def test_filter_by_short_code_zfills(self, provider: SQLiteProvider):
        """传入 '1' 应 zfill 为 '000001'，匹配到 code='000001' 的行。"""
        df = provider.get_stock_basic(["1"])
        assert len(df) == 1
        assert df.iloc[0]["code"] == "000001"
        assert df.iloc[0]["name"] == "测试股票A"

    def test_caches_result(self, provider: SQLiteProvider):
        """第二次调用应命中缓存。"""
        df1 = provider.get_stock_basic()
        df2 = provider.get_stock_basic()
        # 同一对象引用说明用了缓存
        assert df1 is df2


class TestGetFundamentals:
    def test_empty_codes_returns_empty_df(self, provider: SQLiteProvider):
        df = provider.get_fundamentals([], "2024-03-31")
        assert df.empty

    def test_returns_data_for_existing_code(self, provider: SQLiteProvider):
        df = provider.get_fundamentals(["600519"], "2024-03-31")
        assert len(df) == 1
        assert df.iloc[0]["revenue"] == 4e10

    def test_large_code_list_does_not_hit_param_limit(self, provider: SQLiteProvider):
        # 包含 3 个真实 code + 大量不存在 code，总计 >_MAX_PARAMS
        codes = ["000001", "600519", "300750"] + [f"{i:06d}" for i in range(2000, 4000)]
        df = provider.get_fundamentals(codes, "2024-03-31")
        # 库里 3 条 fundamentals，都应被查到
        assert len(df) == 3


class TestGetTradeCalendar:
    def test_returns_dates_in_range(self, provider: SQLiteProvider):
        cal = provider.get_trade_calendar("2024-01-01", "2024-01-02")
        assert cal == ["2024-01-01", "2024-01-02"]

    def test_empty_range(self, provider: SQLiteProvider):
        cal = provider.get_trade_calendar("2025-01-01", "2025-01-31")
        assert cal == []


class TestGetLatestPrice:
    def test_returns_latest_close(self, provider: SQLiteProvider):
        # 600519 最新一条是 2024-01-02 close=1820
        price = provider.get_latest_price("600519")
        assert price == 1820.0

    def test_returns_zero_for_missing_code(self, provider: SQLiteProvider):
        price = provider.get_latest_price("999999")
        assert price == 0.0

    def test_zfills_short_code(self, provider: SQLiteProvider):
        """传入 '1' 应 zfill 为 '000001'，查到 code='000001' 的最新价。"""
        price = provider.get_latest_price("1")
        # 000001 最新一条是 2024-01-02 close=12
        assert price == 12.0
