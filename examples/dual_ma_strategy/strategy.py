"""双均线策略示例：MA5 上穿 MA20 买入，下穿卖出。

这是 quantseed 框架的第一个真实策略示例，展示：
1. 如何用 BaseStrategy 的三个钩子（on_open/on_close/on_eod）
2. 如何从 self.data 读取历史价格计算信号
3. 如何用 self.state 持久化持仓状态（崩溃恢复）
4. 如何用 self.tracker 记录交易和净值
5. 如何用 config.json 参数化策略

策略逻辑：
- on_close（14:45）：扫描股票池，计算 MA5/MA20
    - MA5 上穿 MA20 → 买入信号
    - MA5 下穿 MA20 → 卖出信号
- on_open（09:25）：执行卖出（先卖后买，释放资金）
- on_eod（15:05）：记录当日净值

仓位管理：
- 等权分配，每只股票占总资金 position_pct（默认 30%）
- 最多持有 max_positions 只（默认 3 只）
- 单只止损 stop_loss_pct（默认 -8%）

注意：本示例用模拟数据演示框架用法，不构成投资建议。
"""
import datetime
from typing import Dict, List

import pandas as pd

from quantseed.strategy_base import BaseStrategy


class DualMAStrategy(BaseStrategy):
    name = "dual_ma"
    description = "双均线策略：MA5 上穿 MA20 买入，下穿卖出"

    def __init__(self, strategy_dir=None):
        super().__init__(strategy_dir)
        # 从 config.json 读取参数
        self.short_window: int = self.config.get("short_window", 5)
        self.long_window: int = self.config.get("long_window", 20)
        self.max_positions: int = self.config.get("max_positions", 3)
        self.position_pct: float = self.config.get("position_pct", 0.3)
        self.stop_loss_pct: float = self.config.get("stop_loss_pct", -0.08)
        self.universe: List[str] = self.config.get(
            "universe", ["600519", "000001", "300750"]
        )
        # 初始资金（首次运行时写入 state）
        if self.state.get("initial_capital") is None:
            self.state.update(
                initial_capital=100000.0,
                cash=100000.0,
                positions={},       # {code: {qty, avg_cost}}
                last_equity=100000.0,  # 昨日净值，用于算 pnl_daily
            )

    def _get_price(self, code: str, now: datetime.datetime) -> float:
        """获取当前日期的收盘价。

        回测场景：用 get_price_on_date 取历史当日价。
        实盘场景：如果 get_price_on_date 返回 0（今天还没收盘），降级用 get_latest_price。
        """
        if self.data is None:
            return 0.0
        date_str = now.strftime("%Y-%m-%d")
        try:
            price = self.data.get_price_on_date(code, date_str)
            if price > 0:
                return price
        except Exception:
            pass
        # 降级：实盘当日还没数据时用实时价
        try:
            return self.data.get_latest_price(code)
        except Exception:
            return 0.0

    # ========== 三个钩子 ==========

    def on_open(self, now: datetime.datetime):
        """09:25 开盘：执行卖出信号（先卖后买，释放资金）。"""
        self.log(f"开盘 [{now.strftime('%H:%M')}] - 检查卖出信号")
        self._execute_sells(now)

    def on_close(self, now: datetime.datetime):
        """14:45 尾盘：扫描信号 + 执行买入（先扫信号，再用当日收盘价买入）。"""
        self.log(f"尾盘 [{now.strftime('%H:%M')}] - 计算双均线信号")
        self._scan_signals(now)
        self._execute_buys(now)

    def on_eod(self, now: datetime.datetime):
        """15:05 日终：记录净值。"""
        self.log(f"日终 [{now.strftime('%H:%M')}] - 记录净值")
        self._record_equity(now)

    # ========== 信号计算 ==========

    def _scan_signals(self, now: datetime.datetime) -> Dict[str, str]:
        """扫描股票池，计算 MA 交叉信号。

        Returns:
            {code: "BUY" | "SELL" | "HOLD"}
        """
        signals: Dict[str, str] = {}
        if self.data is None:
            self.log("数据接口未注入")
            return signals

        today = now.strftime("%Y-%m-%d")
        # 拉取 long_window + 5 天的数据，确保能算出两条均线
        lookback_days = self.long_window + 10
        start_date = (now - datetime.timedelta(days=lookback_days * 2)).strftime(
            "%Y-%m-%d"
        )

        try:
            prices = self.data.get_daily_prices(self.universe, start_date, today)
        except Exception as e:
            self.log(f"拉取价格失败: {e}")
            return signals

        if prices.empty:
            self.log("价格数据为空")
            return signals

        for code in self.universe:
            code_prices = prices[prices["code"] == code].sort_values("trade_date")
            if len(code_prices) < self.long_window + 1:
                continue

            ma_short = code_prices["close"].rolling(self.short_window).mean()
            ma_long = code_prices["close"].rolling(self.long_window).mean()

            # 金叉：昨天 MA5 < MA20，今天 MA5 > MA20
            # 死叉：昨天 MA5 > MA20，今天 MA5 < MA20
            prev_diff = ma_short.iloc[-2] - ma_long.iloc[-2]
            curr_diff = ma_short.iloc[-1] - ma_long.iloc[-1]

            if prev_diff < 0 and curr_diff > 0:
                signals[code] = "BUY"
                self.log(f"  {code} 金叉信号 (MA{self.short_window}上穿MA{self.long_window})")
            elif prev_diff > 0 and curr_diff < 0:
                signals[code] = "SELL"
                self.log(f"  {code} 死叉信号 (MA{self.short_window}下穿MA{self.long_window})")
            else:
                signals[code] = "HOLD"

        # 把信号合并到 pending_signals（不覆盖未执行的旧信号）
        if signals:
            pending = self.state.get("pending_signals", {})
            pending.update(signals)
            self.state.update(pending_signals=pending)
        return signals

    # ========== 交易执行 ==========

    def _execute_sells(self, now: datetime.datetime):
        """执行卖出信号 + 止损。"""
        signals = self.state.get("pending_signals", {})
        positions: Dict = self.state.get("positions", {})
        cash: float = self.state.get("cash", 0.0)

        if not positions and not signals:
            return

        to_sell: List[str] = []

        # 1. 死叉信号卖出
        for code, signal in signals.items():
            if signal == "SELL" and code in positions:
                to_sell.append(code)

        # 2. 止损卖出
        for code in list(positions.keys()):
            avg_cost = positions[code].get("avg_cost", 0)
            latest_price = self._get_price(code, now)
            if avg_cost > 0 and latest_price > 0:
                pnl_pct = (latest_price - avg_cost) / avg_cost
                if pnl_pct <= self.stop_loss_pct:
                    to_sell.append(code)
                    self.log(f"  {code} 触发止损 (亏损 {pnl_pct:.2%})")

        # 执行卖出
        for code in to_sell:
            if code not in positions:
                continue
            pos = positions[code]
            qty = pos.get("qty", 0)
            if qty <= 0:
                continue
            price = self._get_price(code, now)
            if price <= 0:
                continue

            amount = price * qty
            cash += amount
            del positions[code]

            self.tracker.record_trade(
                code=code,
                name=code,  # 实盘可从 stock_basic 查 name
                action="SELL",
                price=price,
                qty=qty,
                strategy=self.name,
                note=f"卖出 {qty} 股 @ {price}",
                dt=now,
            )
            self.log(f"  卖出 {code}: {qty} 股 @ {price:.2f} = {amount:.2f}")

        # 清理已执行的信号
        remaining_signals = {
            k: v for k, v in signals.items() if k not in to_sell
        }
        self.state.update(
            positions=positions,
            cash=cash,
            pending_signals=remaining_signals,
        )

    def _execute_buys(self, now: datetime.datetime):
        """执行买入信号（在 on_close 后调用，用当日收盘价）。"""
        signals = self.state.get("pending_signals", {})
        positions: Dict = self.state.get("positions", {})
        cash: float = self.state.get("cash", 0.0)

        buy_signals = [c for c, s in signals.items() if s == "BUY"]
        if not buy_signals:
            return

        # 仓位限制
        available_slots = self.max_positions - len(positions)
        if available_slots <= 0:
            self.log(f"已达最大持仓数 {self.max_positions}，跳过买入")
            return

        buy_candidates = buy_signals[:available_slots]
        target_amount = self.state.get("initial_capital", 100000.0) * self.position_pct

        bought_codes = []
        for code in buy_candidates:
            if cash < target_amount:
                self.log(f"现金不足 ({cash:.2f} < {target_amount:.2f})，跳过 {code}")
                continue
            price = self._get_price(code, now)
            if price <= 0:
                continue

            qty = int(target_amount / price / 100) * 100  # 整百手
            if qty <= 0:
                continue
            amount = price * qty
            cash -= amount
            positions[code] = {"qty": qty, "avg_cost": price}
            bought_codes.append(code)

            self.tracker.record_trade(
                code=code,
                name=code,
                action="BUY",
                price=price,
                qty=qty,
                strategy=self.name,
                note=f"买入 {qty} 股 @ {price}",
                dt=now,
            )
            self.log(f"  买入 {code}: {qty} 股 @ {price:.2f} = {amount:.2f}")

        # 清理已执行的买入信号
        remaining_signals = {
            k: v for k, v in signals.items() if k not in bought_codes
        }
        self.state.update(
            positions=positions,
            cash=cash,
            pending_signals=remaining_signals,
        )

    # ========== 净值记录 ==========

    def _record_equity(self, now: datetime.datetime):
        """计算并记录当日净值。"""
        positions: Dict = self.state.get("positions", {})
        cash: float = self.state.get("cash", 0.0)
        last_equity: float = self.state.get("last_equity", 0.0)

        stock_value = 0.0
        for code, pos in positions.items():
            qty = pos.get("qty", 0)
            price = self._get_price(code, now)
            stock_value += price * qty

        total_equity = cash + stock_value
        # 真正的日盈亏 = 今日净值 - 昨日净值
        pnl_daily = total_equity - last_equity

        self.tracker.record_equity(
            total_equity=total_equity,
            cash=cash,
            stock_value=stock_value,
            positions=len(positions),
            pnl_daily=pnl_daily,
            date=now,
        )
        # 更新 last_equity 供明日使用
        self.state.update(last_equity=total_equity)
        self.log(
            f"  净值: {total_equity:.2f} (现金 {cash:.2f} + 股票 {stock_value:.2f}, "
            f"日盈亏 {pnl_daily:+.2f})"
        )
