import pandas as pd
import logging
from typing import List, Optional
from .interface import DataProvider

logger = logging.getLogger(__name__)


class TushareProvider(DataProvider):
    def __init__(self, token: str):
        import tushare as ts  # 延迟导入：仅在使用 Tushare 时才需要安装
        ts.set_token(token)
        self._ts = ts
        self._pro = ts.pro_api()
        self._stock_basic_cache = None

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """将纯数字代码转换为 Tushare ts_code 格式。

        规则:
          - 6xxxxx → SH（上海主板/科创板）
          - 8xxxxx → BJ（北交所）
          - 其余   → SZ（深圳主板/创业板）
        """
        code = str(code).zfill(6)
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('8'):
            return f"{code}.BJ"
        else:
            return f"{code}.SZ"

    @staticmethod
    def _to_tushare_date(date_str: str) -> str:
        """将 YYYY-MM-DD 转换为 Tushare 要求的 YYYYMMDD 格式。"""
        return date_str.replace("-", "")

    def get_daily_prices(
        self,
        codes: List[str],
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        if not codes:
            return pd.DataFrame()
        all_data = []
        for code in codes:
            try:
                # 使用 pro_bar 获取后复权数据，pro.daily 不支持 adj 参数
                df = self._ts.pro_bar(
                    ts_code=self._to_ts_code(code),
                    start_date=self._to_tushare_date(start_date),
                    end_date=self._to_tushare_date(end_date),
                    adj='hfq'
                )
                if df is not None and not df.empty:
                    df['code'] = df['ts_code'].str[:6]
                    df = df.rename(columns={
                        'vol': 'volume',
                        'pct_chg': 'change_pct',
                    })
                    all_data.append(df)
            except Exception as e:
                logger.warning("获取 %s 日线数据失败: %s", code, e)
                continue
        if not all_data:
            return pd.DataFrame()
        return pd.concat(all_data, ignore_index=True)

    def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame:
        if self._stock_basic_cache is None:
            df = self._pro.stock_basic(exchange='', list_status='L')
            df = df[['ts_code', 'symbol', 'name', 'list_date', 'delist_date']]
            df = df.rename(columns={'symbol': 'code'})
            df['code'] = df['code'].astype(str).str.zfill(6)
            self._stock_basic_cache = df
        df = self._stock_basic_cache
        if codes:
            df = df[df['code'].isin([str(c).zfill(6) for c in codes])]
        return df

    def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        df = self._pro.index_daily(
            ts_code=index_code,
            start_date=self._to_tushare_date(start_date),
            end_date=self._to_tushare_date(end_date)
        )
        if not df.empty:
            df = df.rename(columns={
                'vol': 'volume',
                'pct_chg': 'change_pct',
            })
        return df

    def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame:
        """获取基本面数据。

        Args:
            codes: 股票代码列表
            date: 报告期，格式 YYYY-MM-DD 或 YYYYMMDD
        """
        if not codes:
            return pd.DataFrame()
        period = self._to_tushare_date(date)
        all_data = []
        for code in codes:
            ts_code = self._to_ts_code(code)
            try:
                df = self._pro.fina_indicator(ts_code=ts_code, period=period)
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
        df = self._pro.trade_cal(
            start_date=self._to_tushare_date(start_date),
            end_date=self._to_tushare_date(end_date)
        )
        df = df[df['is_open'] == 1]
        # 统一返回 YYYY-MM-DD 格式
        return [d[:4] + "-" + d[4:6] + "-" + d[6:8] for d in df['cal_date'].tolist()]

    def get_latest_price(self, code: str) -> float:
        ts_code = self._to_ts_code(code)
        # realtime_quote 需要较高积分权限，降级使用最新日线收盘价
        try:
            df = self._pro.realtime_quote(ts_code=ts_code)
            if not df.empty:
                return float(df.iloc[0]['price'])
        except Exception as e:
            logger.debug("realtime_quote 不可用，降级使用最新日线: %s", e)
        # 降级：取最新交易日收盘价
        try:
            df = self._pro.daily(ts_code=ts_code, limit=1)
            if not df.empty:
                return float(df.iloc[0]['close'])
        except Exception as e:
            logger.warning("获取 %s 最新价格失败: %s", code, e)
        return 0.0