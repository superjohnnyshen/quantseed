"""演示策略：买入最近 5 日涨幅最大的 2 只股票。

最简单的动量策略，用于验证框架运行是否正常。
"""
import datetime
import pandas as pd

from quantseed.strategy_base import BaseStrategy


class DemoMomentumStrategy(BaseStrategy):
    name = "demo_momentum"
    description = "演示策略：买入最近 5 日涨幅最大的 2 只股票"

    # 演示用样本数：AkShare 免费数据源对高频请求会限流，
    # 全市场 5000+ 只逐个请求会触发 RemoteDisconnected。
    # 实盘策略请改用 Tushare/SQLite 数据源或自行批量拉取。
    SAMPLE_SIZE = 10

    def on_open(self, now: datetime.datetime):
        """开盘：打日志，正式策略在此卖出昨日持仓。"""
        self.log(f"开盘 [{now.strftime('%H:%M')}] - 演示策略，不做实际交易")

    def on_close(self, now: datetime.datetime):
        """尾盘：计算最近 5 日涨幅，选出 Top 2。"""
        self.log(f"尾盘 [{now.strftime('%H:%M')}] - 计算动量信号")

        today = now.strftime("%Y-%m-%d")
        try:
            codes = self.data.get_all_codes()
            if not codes:
                self.log("未获取到可交易股票列表")
                return

            # 演示只取前 N 只，避免触发数据源限流
            codes = codes[:self.SAMPLE_SIZE]
            self.log(f"采样股票: {len(codes)} 只（演示限流，实盘请用全量）")

            from datetime import timedelta
            five_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

            prices = self.data.get_daily_prices(codes, five_days_ago, today)
            if prices.empty:
                self.log("未获取到价格数据")
                return

            result = []
            for code in codes:
                code_prices = prices[prices["code"] == code]
                if len(code_prices) >= 2:
                    first_close = code_prices["close"].iloc[0]
                    last_close = code_prices["close"].iloc[-1]
                    if first_close > 0:
                        pct = (last_close - first_close) / first_close
                        result.append({"code": code, "pct_5d": pct})

            if not result:
                self.log("无有效涨幅数据")
                return

            result_df = pd.DataFrame(result).sort_values("pct_5d", ascending=False)
            top_2 = result_df.head(2)

            self.log("Top 2 动量股:")
            for _, row in top_2.iterrows():
                self.log(f"  {row['code']}: {row['pct_5d']:.2%}")

        except Exception as e:
            self.log(f"信号计算异常: {e}")

    def on_eod(self, now: datetime.datetime):
        """日终：记录净值。"""
        self.log(f"日终 [{now.strftime('%H:%M')}] - 记录净值")
        self.tracker.record_equity(
            total_equity=100000.0,
            cash=100000.0,
            stock_value=0.0,
            positions=0,
            pnl_daily=0.0,
        )