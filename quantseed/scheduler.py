"""时间调度器：主循环，定时触发各策略的 on_open / on_close / on_eod。

自动扫描 strategies/ 目录，加载所有策略，按时间触发。
"""
import time
import datetime
import importlib.util
import sys
from pathlib import Path

from quantseed.config import STRATEGIES_DIR
from quantseed.strategy_base import BaseStrategy


class Scheduler:
    """主循环：扫描 strategies/，定时触发各策略。"""

    def __init__(self):
        self.strategies = []
        self._last_open_date = None
        self._last_close_date = None
        self._last_eod_date = None

    def register(self, strategy):
        """注册一个策略实例。"""
        self.strategies.append(strategy)
        return strategy

    def auto_discover(self):
        """自动扫描 strategies/ 目录，加载每个策略的 strategy.py。

        目录结构要求:
          strategies/
            my_strategy/
              strategy.py    ← 包含一个继承 BaseStrategy 的类
              config.json    ← 策略参数
        """
        if not STRATEGIES_DIR.exists():
            STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
            return

        for sub in sorted(STRATEGIES_DIR.iterdir()):
            if sub.is_dir() and (sub / "strategy.py").exists():
                try:
                    mod = _import_strategy(sub)
                    strategy_class = _find_strategy_class(mod)
                    if strategy_class:
                        instance = strategy_class(sub)
                        self.register(instance)
                        print(f"[scheduler] 加载策略: {instance.name}")
                except Exception as e:
                    print(f"[scheduler] 加载策略失败: {sub.name} - {e}")

    def run(self):
        """主循环：按时间触发 on_open / on_close / on_eod。

        时间点:
          - 09:25-09:35  on_open（开盘卖出）
          - 14:45-14:55  on_close（尾盘买入）
          - 15:05-15:15  on_eod（日终对账）
        """
        print(f"[scheduler] 启动: 共 {len(self.strategies)} 个策略")
        for s in self.strategies:
            s.log(f"策略初始化: {s.description}")

        # 注入数据接口
        from quantseed.config import get_data_provider
        data = get_data_provider()
        for s in self.strategies:
            s.data = data

        while True:
            now = datetime.datetime.now()
            today = now.strftime("%Y-%m-%d")
            hm = now.strftime("%H:%M")

            # 9:25 - 开盘后 on_open（卖出昨日持仓）
            if "09:25" <= hm <= "09:35" and today != self._last_open_date:
                for s in self.strategies:
                    try:
                        s.on_open(now)
                    except Exception as e:
                        s.log(f"on_open 异常: {e}")
                self._last_open_date = today

            # 14:45 - 尾盘 on_close（买入建仓）
            elif "14:45" <= hm <= "14:55" and today != self._last_close_date:
                for s in self.strategies:
                    try:
                        s.on_close(now)
                    except Exception as e:
                        s.log(f"on_close 异常: {e}")
                self._last_close_date = today

            # 15:05 - 日终 on_eod（对账/净值）
            elif "15:05" <= hm <= "15:15" and today != self._last_eod_date:
                for s in self.strategies:
                    try:
                        s.on_eod(now)
                    except Exception as e:
                        s.log(f"on_eod 异常: {e}")
                self._last_eod_date = today

            time.sleep(30)


def _import_strategy(strategy_dir: Path):
    """动态导入策略模块。"""
    spec = importlib.util.spec_from_file_location(
        f"strategies_{strategy_dir.name}.strategy",
        str(strategy_dir / "strategy.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _find_strategy_class(module):
    """从模块中找到继承自 BaseStrategy 的类。"""
    for name in dir(module):
        obj = getattr(module, name, None)
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseStrategy)
            and obj is not BaseStrategy
        ):
            return obj
    return None