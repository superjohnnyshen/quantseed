import akshare as ak
import pandas as pd
import logging
from typing import List, Optional
from .interface import DataProvider

logger = logging.getLogger(__name__)


class AkShareProvider(DataProvider):
    def __init__(self):
        self._stock_basic_cache = None

    def get_daily_prices(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        all_data = []
        for code in codes:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="hfq"
                )
                if not df.empty:
                    df['code'] = code
                    df = df.rename(columns={
                        '日期': 'trade_date',
                        '开盘': 'open',
                        '收盘': 'close',
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume',
                        '成交额': 'amount',
                        '振幅': 'amplitude',
                        '涨跌幅': 'change_pct',
                        '涨跌额': 'change_amount',
                        '换手率': 'turnover_rate'
                    })
                    df['trade_date'] = df['trade_date'].astype(str)
                    all_data.append(df)
            except Exception as e:
                logger.warning("获取 %s 日线数据失败: %s", code, e)
                continue
        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)

    def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        if self._stock_basic_cache is None:
            df = ak.stock_info_a_code_name()
            df = df.rename(columns={
                'code': 'code',
                'name': 'name'
            })
            df['code'] = df['code'].astype(str).str.zfill(6)
            self._stock_basic_cache = df
        df = self._stock_basic_cache
        if codes:
            df = df[df['code'].isin([str(c).zfill(6) for c in codes])]
        return df

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = ak.stock_zh_index_daily(symbol=index_code)
        if not df.empty:
            df = df.rename(columns={
                'date': 'trade_date',
                'open': 'open',
                'close': 'close',
                'high': 'high',
                'low': 'low',
                'volume': 'volume',
                'amount': 'amount'
            })
            df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
            df['trade_date'] = df['trade_date'].astype(str)
        return df

    def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame:
        all_data = []
        for code in codes:
            try:
                df = ak.stock_financial_report_sina(symbol=code)
                if not df.empty:
                    df['code'] = code
                    all_data.append(df)
            except Exception as e:
                logger.warning("获取 %s 基本面数据失败: %s", code, e)
                continue
        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)

    def get_trade_calendar(self, start_date: str, end_date: str) -> List[str]:
        df = ak.tool_trade_date_hist_sina()
        df['trade_date'] = df['trade_date'].astype(str)
        df = df[(df['trade_date'] >= start_date) & (df['trade_date'] <= end_date)]
        return df['trade_date'].tolist()

    def get_latest_price(self, code: str) -> float:
        df = ak.stock_zh_a_spot_em()
        df['代码'] = df['代码'].astype(str).str.zfill(6)
        row = df[df['代码'] == str(code).zfill(6)]
        if not row.empty:
            return float(row.iloc[0]['最新价'])
        return 0.0