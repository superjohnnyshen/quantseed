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
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from quantseed.state_store import StateStore
from quantseed.equity_tracker import EquityTracker

if TYPE_CHECKING:
    from quantseed.data.interface import DataProvider


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

    # === 公用工具 ===
    def log(self, msg):
        """统一日志格式。"""
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{self.name}] {ts} - {msg}")

    def is_trading_day(self):
        """判断是否为交易日。子类可覆盖实现更精确的判断。"""
        return True

    def __str__(self):
        return f"<Strategy {self.name}>"