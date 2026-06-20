"""策略基类：所有策略继承此类，只需实现 on_open / on_close / on_eod。

策略目录约定：
  strategies/<name>/
    strategy.py         策略代码（继承 BaseStrategy）
    config.json         策略参数

自动生成：
  strategies/<name>/state.json      运行状态（崩溃恢复用）
  strategies/<name>/trades.csv      交易日志
  strategies/<name>/equity.csv      净值曲线
"""
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING

from quantseed.state_store import StateStore
from quantseed.equity_tracker import EquityTracker

if TYPE_CHECKING:
    from quantseed.data.interface import DataProvider
    from quantseed.trading import TradingAPI

logger = logging.getLogger(__name__)


class BaseStrategy:
    """策略基类。子类实现三个时间点的行为即可。

    使用示例:
        class MyStrategy(BaseStrategy):
            name = "my_strategy"
            description = "我的第一个策略"

            def on_open(self, now):
                # 9:25 卖出昨日持仓
                pass

            def on_close(self, now):
                # 14:45 买入建仓
                pass

            def on_eod(self, now):
                # 15:05 日终对账
                pass
    """

    name = "base"
    description = "基础策略"

    def __init__(self, strategy_dir=None):
        if strategy_dir is None:
            from quantseed.config import STRATEGIES_DIR
            strategy_dir = STRATEGIES_DIR / self.name
        self.strategy_dir = Path(strategy_dir)
        self.strategy_dir.mkdir(parents=True, exist_ok=True)

        # 状态持久化
        self.state = StateStore(self.strategy_dir / "state.json")

        # 净值/交易日志
        self.tracker = EquityTracker(
            self.strategy_dir / "equity.csv",
            self.strategy_dir / "trades.csv",
        )

        # 从 config.json 读取参数
        self.config = self._load_config()

        # 数据接口（由调度器注入）
        self.data: Optional["DataProvider"] = None

        # 交易接口（由调度器注入，实盘时可用）
        self.trader: Optional["TradingAPI"] = None

    def _load_config(self):
        cfg_path = self.strategy_dir / "config.json"
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    # === 子类必须实现的方法 ===
    def on_open(self, now: datetime.datetime):
        """9:25 开盘后触发（卖出昨日持仓）。"""
        pass

    def on_close(self, now: datetime.datetime):
        """14:45 尾盘触发（买入建仓）。"""
        pass

    def on_eod(self, now: datetime.datetime):
        """15:05 收盘后触发（对账/记录净值）。"""
        pass

    # === 下单辅助方法（推荐使用，避免重复造轮子）===

    def buy(self, code: str, qty: int, price: float,
            now: Optional[datetime.datetime] = None, note: str = "") -> bool:
        """买入股票。

        封装 state 更新 + 交易日志 + 实盘下单（如果 trader 已连接）。
        回测/模拟模式下立即成交并更新 state；实盘模式下额外调用 trader 下单。

        Args:
            code: 股票代码（6 位数字字符串）
            qty: 买入数量（股，应为 100 的整数倍）
            price: 买入价格
            now: 时间戳（回测传入历史时间，实盘默认现在）
            note: 备注信息

        Returns:
            True 成功，False 失败（现金不足 / 下单失败）
        """
        if qty <= 0 or price <= 0:
            return False

        amount = price * qty
        cash = self.state.get("cash", 0.0)
        if cash < amount:
            self.log(f"买入失败 {code}: 现金不足 ({cash:.2f} < {amount:.2f})")
            return False

        # 实盘下单（如果 trader 已连接）
        if self.trader is not None and self.trader.is_connected:
            order_id, err = self.trader.order_buy(code, price, qty, self.name)
            if err:
                self.log(f"买入下单失败 {code}: {err}")
                return False

        # 更新持仓
        positions: Dict = self.state.get("positions", {})
        if code in positions:
            old_qty = positions[code].get("qty", 0)
            old_cost = positions[code].get("avg_cost", 0)
            new_qty = old_qty + qty
            new_cost = (old_cost * old_qty + price * qty) / new_qty
            positions[code] = {"qty": new_qty, "avg_cost": round(new_cost, 4)}
        else:
            positions[code] = {"qty": qty, "avg_cost": price}

        cash -= amount
        self.state.update(positions=positions, cash=cash)

        # 记录交易
        self.tracker.record_trade(
            code=code, name=code, action="BUY",
            price=price, qty=qty, strategy=self.name,
            note=note or f"买入 {qty} 股 @ {price}", dt=now,
        )
        self.log(f"买入 {code}: {qty} 股 @ {price:.2f} = {amount:.2f}")
        return True

    def sell(self, code: str, qty: int, price: float,
             now: Optional[datetime.datetime] = None, note: str = "") -> bool:
        """卖出股票。

        Args:
            code: 股票代码
            qty: 卖出数量
            price: 卖出价格
            now: 时间戳
            note: 备注

        Returns:
            True 成功，False 失败（持仓不足 / 下单失败）
        """
        if qty <= 0 or price <= 0:
            return False

        positions: Dict = self.state.get("positions", {})
        if code not in positions:
            self.log(f"卖出失败 {code}: 无持仓")
            return False

        held_qty = positions[code].get("qty", 0)
        if held_qty < qty:
            self.log(f"卖出失败 {code}: 持仓不足 ({held_qty} < {qty})")
            return False

        # 实盘下单
        if self.trader is not None and self.trader.is_connected:
            order_id, err = self.trader.order_sell(code, price, qty, self.name)
            if err:
                self.log(f"卖出下单失败 {code}: {err}")
                return False

        # 更新持仓
        amount = price * qty
        cash = self.state.get("cash", 0.0) + amount
        new_qty = held_qty - qty
        if new_qty <= 0:
            del positions[code]
        else:
            positions[code] = {"qty": new_qty, "avg_cost": positions[code].get("avg_cost", 0)}

        self.state.update(positions=positions, cash=cash)

        self.tracker.record_trade(
            code=code, name=code, action="SELL",
            price=price, qty=qty, strategy=self.name,
            note=note or f"卖出 {qty} 股 @ {price}", dt=now,
        )
        self.log(f"卖出 {code}: {qty} 股 @ {price:.2f} = {amount:.2f}")
        return True

    def sell_all(self, code: str, price: float,
                 now: Optional[datetime.datetime] = None, note: str = "") -> bool:
        """清仓某只股票。"""
        qty = self.get_position_qty(code)
        if qty <= 0:
            return False
        return self.sell(code, qty, price, now, note or "清仓")

    # === 持仓/资金查询 ===

    def get_position(self, code: str) -> Optional[Dict]:
        """获取某只股票的持仓信息 {qty, avg_cost}，无持仓返回 None。"""
        positions = self.state.get("positions", {})
        return positions.get(code)

    def get_position_qty(self, code: str) -> int:
        """获取某只股票的持仓数量。"""
        pos = self.get_position(code)
        return pos.get("qty", 0) if pos else 0

    def get_cash(self) -> float:
        """获取当前现金。"""
        return float(self.state.get("cash", 0.0))

    def get_stock_value(self, now: Optional[datetime.datetime] = None) -> float:
        """计算当前持仓市值。需要 self.data 已注入。"""
        positions = self.state.get("positions", {})
        if not positions or self.data is None:
            return 0.0
        total = 0.0
        for code, pos in positions.items():
            qty = pos.get("qty", 0)
            price = self.get_price(code, now)
            total += price * qty
        return total

    def get_total_equity(self, now: Optional[datetime.datetime] = None) -> float:
        """计算当前总净值 = 现金 + 持仓市值。"""
        return self.get_cash() + self.get_stock_value(now)

    def get_price(self, code: str, now: Optional[datetime.datetime] = None) -> float:
        """获取股票价格。

        回测场景（传入 now）：优先用 get_price_on_date 取历史当日价。
        实盘场景（now 为 None）：用 get_latest_price 取实时价。
        """
        if self.data is None:
            return 0.0
        if now is not None:
            date_str = now.strftime("%Y-%m-%d")
            try:
                price = self.data.get_price_on_date(code, date_str)
                if price > 0:
                    return price
            except Exception:
                pass
        try:
            return self.data.get_latest_price(code)
        except Exception:
            return 0.0

    # === 公用工具 ===

    def log(self, msg):
        """统一日志格式。"""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{self.name}] {ts} - {msg}")

    def is_trading_day(self):
        """判断今天是否为交易日。使用注入的数据接口查询交易日历。"""
        if self.data is None:
            return datetime.date.today().weekday() < 5
        try:
            today = datetime.date.today().strftime("%Y-%m-%d")
            calendar = self.data.get_trade_calendar(today, today)
            return today in calendar
        except Exception:
            return datetime.date.today().weekday() < 5

    def __str__(self):
        return f"<Strategy {self.name}>"
