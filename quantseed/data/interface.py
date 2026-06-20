from abc import ABC, abstractmethod
from typing import List, Optional
import pandas as pd


class DataProvider(ABC):
    def get_all_codes(self) -> List[str]:
        """获取全部股票代码。默认从 get_stock_basic() 派生。"""
        df = self.get_stock_basic()
        return df['code'].tolist()

    @abstractmethod
    def get_daily_prices(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_trade_calendar(self, start_date: str, end_date: str) -> List[str]:
        pass

    @abstractmethod
    def get_latest_price(self, code: str) -> float:
        pass

    def get_price_on_date(self, code: str, date: str) -> float:
        """获取某只股票在指定日期的收盘价。

        实盘场景：date 为今天时等价于 get_latest_price。
        回测场景：返回历史当日的收盘价，避免 get_latest_price 返回数据库最新价。

        默认实现：从 get_daily_prices 取该日数据。子类可重写以优化性能。
        """
        df = self.get_daily_prices([code], date, date)
        if df.empty:
            return 0.0
        return float(df.iloc[-1]["close"])