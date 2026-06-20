"""演示策略：买入持有 + 日终记录净值。

这是 quantseed 最简单的可运行策略，用于：
1. 验证框架是否正常工作
2. 演示 BaseStrategy 的 buy/sell/get_total_equity 用法
3. 作为新策略的起点模板

策略逻辑：
- 首次运行 on_close 时，用 50% 资金买入股票池第一只股票
- 之后每天 on_eod 记录净值
- on_open 检查是否需要止损（亏损超过 10% 卖出）

注意：本策略仅用于演示，不构成投资建议。
"""
import datetime
from typing import List

from quantseed.strategy_base import BaseStrategy


class DemoStrategy(BaseStrategy):
    name = "demo"
    description = "演示策略：买入持有 + 止损"

    def __init__(self, strategy_dir=None):
        super().__init__(strategy_dir)
        # 从 config.json 读参数，支持参数化
        self.universe: List[str] = self.config.get(
            "universe", ["600519", "000001", "300750"]
        )
        self.buy_pct: float = self.config.get("buy_pct", 0.5)  # 用 50% 资金买入
        self.stop_loss_pct: float = self.config.get("stop_loss_pct", -0.10)

        # 首次运行时初始化 state
        if self.state.get("initial_capital") is None:
            self.state.update(
                initial_capital=100000.0,
                cash=100000.0,
                positions={},
                last_equity=100000.0,
            )

    def on_open(self, now: datetime.datetime):
        """09:25 开盘：检查止损。"""
        positions = self.state.get("positions", {})
        if not positions:
            return

        self.log(f"开盘 [{now.strftime('%H:%M')}] - 检查止损")
        for code in list(positions.keys()):
            avg_cost = positions[code].get("avg_cost", 0)
            price = self.get_price(code, now)
            if avg_cost > 0 and price > 0:
                pnl_pct = (price - avg_cost) / avg_cost
                if pnl_pct <= self.stop_loss_pct:
                    self.log(f"  {code} 触发止损 (亏损 {pnl_pct:.2%})")
                    self.sell_all(code, price, now=now, note="止损")

    def on_close(self, now: datetime.datetime):
        """14:45 尾盘：首次买入。"""
        positions = self.state.get("positions", {})
        if positions:
            # 已建仓，不重复买入
            return

        self.log(f"尾盘 [{now.strftime('%H:%M')}] - 建仓")
        target_amount = self.state.get("initial_capital", 100000.0) * self.buy_pct
        code = self.universe[0]  # 买股票池第一只

        price = self.get_price(code, now)
        if price <= 0:
            self.log(f"  无法获取 {code} 的价格，跳过")
            return

        qty = int(target_amount / price / 100) * 100  # 整百手
        if qty > 0:
            self.buy(code, qty, price, now=now, note="首次建仓")

    def on_eod(self, now: datetime.datetime):
        """15:05 日终：记录净值。"""
        cash = self.get_cash()
        positions = self.state.get("positions", {})
        last_equity = self.state.get("last_equity", 0.0)

        stock_value = self.get_stock_value(now)
        total_equity = cash + stock_value
        pnl_daily = total_equity - last_equity

        self.tracker.record_equity(
            total_equity=total_equity,
            cash=cash,
            stock_value=stock_value,
            positions=len(positions),
            pnl_daily=pnl_daily,
            date=now,
        )
        self.state.update(last_equity=total_equity)
        self.log(
            f"日终 [{now.strftime('%H:%M')}] - 净值 {total_equity:.2f} "
            f"(现金 {cash:.2f} + 股票 {stock_value:.2f}, 日盈亏 {pnl_daily:+.2f})"
        )
