import sqlite3
import pandas as pd
from contextlib import closing
from typing import List, Optional
from .interface import DataProvider

# SQLite 默认 SQLITE_MAX_VARIABLE_NUMBER=999，留余量取 500
_MAX_PARAMS = 500


class SQLiteProvider(DataProvider):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._stock_basic_cache = None

    def _connect(self):
        return sqlite3.connect(self._db_path)

    @staticmethod
    def _normalize_codes(codes: List[str]) -> List[str]:
        """统一为 6 位前导零字符串。"""
        return [str(c).zfill(6) for c in codes]

    @staticmethod
    def _chunked(items: List[str], size: int = _MAX_PARAMS):
        """将列表切分为不超过 size 长度的子列表，规避 SQLite 参数上限。"""
        for i in range(0, len(items), size):
            yield items[i:i + size]

    def get_daily_prices(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        if not codes:
            return pd.DataFrame()
        codes = self._normalize_codes(codes)
        query_tmpl = """
            SELECT trade_date, code, open, close, high, low, volume, amount, change_pct, turnover_rate
            FROM daily_prices
            WHERE code IN ({placeholders})
            AND trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date, code
        """
        # closing() 确保 with 块退出时关闭连接
        # sqlite3.Connection 的 with 只管理事务，不关闭连接
        frames: List[pd.DataFrame] = []
        with closing(self._connect()) as conn:
            for chunk in self._chunked(codes):
                placeholders = ','.join(['?'] * len(chunk))
                query = query_tmpl.format(placeholders=placeholders)
                frames.append(pd.read_sql_query(
                    query, conn, params=chunk + [start_date, end_date]
                ))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        if self._stock_basic_cache is None:
            with closing(self._connect()) as conn:
                df = pd.read_sql_query("SELECT code, name, list_date, delist_date FROM stock_basic", conn)
            df['code'] = df['code'].astype(str).str.zfill(6)
            self._stock_basic_cache = df
        df = self._stock_basic_cache
        if codes:
            df = df[df['code'].isin([str(c).zfill(6) for c in codes])]
        return df

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        query = """
            SELECT trade_date, open, close, high, low, volume, amount, change_pct
            FROM index_daily
            WHERE index_code = ?
            AND trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date
        """
        with closing(self._connect()) as conn:
            df = pd.read_sql_query(query, conn, params=[index_code, start_date, end_date])
        return df

    def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame:
        if not codes:
            return pd.DataFrame()
        codes = self._normalize_codes(codes)
        query_tmpl = """
            SELECT * FROM fundamentals
            WHERE code IN ({placeholders})
            AND report_date = ?
        """
        frames: List[pd.DataFrame] = []
        with closing(self._connect()) as conn:
            for chunk in self._chunked(codes):
                placeholders = ','.join(['?'] * len(chunk))
                query = query_tmpl.format(placeholders=placeholders)
                frames.append(pd.read_sql_query(
                    query, conn, params=chunk + [date]
                ))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[str]:
        query = """
            SELECT trade_date FROM trade_calendar
            WHERE trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date
        """
        with closing(self._connect()) as conn:
            df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        return df['trade_date'].tolist()

    def get_latest_price(self, code: str) -> float:
        query = """
            SELECT close FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """
        with closing(self._connect()) as conn:
            df = pd.read_sql_query(query, conn, params=[str(code).zfill(6)])
        if not df.empty:
            return float(df.iloc[0]['close'])
        return 0.0