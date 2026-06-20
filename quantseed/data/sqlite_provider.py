import sqlite3
import pandas as pd
from typing import List, Optional
from .interface import DataProvider


class SQLiteProvider(DataProvider):
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._stock_basic_cache = None

    def _connect(self):
        return sqlite3.connect(self._db_path)

    def get_all_codes(self) -> List[str]:
        df = self.get_stock_basic()
        return df['code'].tolist()

    def get_daily_prices(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        conn = self._connect()
        placeholders = ','.join(['?'] * len(codes))
        query = f"""
            SELECT trade_date, code, open, close, high, low, volume, amount, change_pct, turnover_rate
            FROM daily_prices
            WHERE code IN ({placeholders})
            AND trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date, code
        """
        df = pd.read_sql_query(query, conn, params=codes + [start_date, end_date])
        conn.close()
        return df

    def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        if self._stock_basic_cache is None:
            conn = self._connect()
            df = pd.read_sql_query("SELECT code, name, list_date, delist_date FROM stock_basic", conn)
            conn.close()
            df['code'] = df['code'].astype(str).str.zfill(6)
            self._stock_basic_cache = df
        df = self._stock_basic_cache
        if codes:
            df = df[df['code'].isin([str(c).zfill(6) for c in codes])]
        return df

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        conn = self._connect()
        query = """
            SELECT trade_date, open, close, high, low, volume, amount, change_pct
            FROM index_daily
            WHERE index_code = ?
            AND trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date
        """
        df = pd.read_sql_query(query, conn, params=[index_code, start_date, end_date])
        conn.close()
        return df

    def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame:
        conn = self._connect()
        placeholders = ','.join(['?'] * len(codes))
        query = f"""
            SELECT * FROM fundamentals
            WHERE code IN ({placeholders})
            AND report_date = ?
        """
        df = pd.read_sql_query(query, conn, params=codes + [date])
        conn.close()
        return df

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[str]:
        conn = self._connect()
        query = """
            SELECT trade_date FROM trade_calendar
            WHERE trade_date >= ?
            AND trade_date <= ?
            ORDER BY trade_date
        """
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        conn.close()
        return df['trade_date'].tolist()

    def get_latest_price(self, code: str) -> float:
        conn = self._connect()
        query = """
            SELECT close FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """
        df = pd.read_sql_query(query, conn, params=[str(code).zfill(6)])
        conn.close()
        if not df.empty:
            return float(df.iloc[0]['close'])
        return 0.0