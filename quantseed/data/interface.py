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