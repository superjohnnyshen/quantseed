from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def get_all_codes(self) -> List[str]:
        pass

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