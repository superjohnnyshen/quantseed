# QuantSeed

> 个人量化从零到一启动包：**SOP 方法论 + 多策略框架 + 多数据源 + 回测引擎**。

---

## 这是什么

QuantSeed 不是又一个回测框架，而是面向**个人量化投资者**的完整策略开发启动包：

| 组件 | 说明 |
|------|------|
| **SOP.md** | 从立项到实盘的标准化流程，配真实失败案例 |
| **多策略框架** | 插件式架构，一个策略一个目录，自动发现 |
| **回测引擎** | 历史数据驱动，自动计算夏普/最大回撤/年化收益 |
| **数据管道** | 统一数据接口，支持 QMT / Tushare / AkShare |

---

## 快速开始

### 安装

```bash
# 从 GitHub 安装（推荐）
git clone https://github.com/superjohnnyshen/quantseed.git
cd quantseed
pip install -e .

# 可选：安装开发依赖（跑测试用）
pip install -e ".[dev]"
```

### 第一步：检查环境

```bash
quantseed --version    # 查看版本
quantseed check        # 检查依赖、数据源、策略目录
```

### 第二步：跑第一个回测（5 分钟出结果）

```bash
# 准备测试数据（生成 SQLite 数据库，5 只股票 × 60 天）
python examples/dual_ma_strategy/prepare_data.py

# 一键回测
quantseed backtest examples/dual_ma_strategy/
```

输出示例：
```
=== 回测结果 ===
  回测区间:     2024-02-06 ~ 2024-03-25 (35 个交易日)
  初始资金:     100000.00
  最终净值:     103026.00
  总收益率:     +3.03%
  年化收益率:   +23.94%
  最大回撤:     530.00 (-0.51%)
  夏普比率:     4.403
  交易次数:     2
```

### 第三步：实盘运行

```bash
# 复制示例策略到 strategies/
cp -r examples/demo_strategy/ strategies/

# 调试模式：立即执行一次钩子然后退出
quantseed run --once

# 正式运行：主循环，按时间自动触发
quantseed run
```

---

## 数据源

QuantSeed 默认使用 **AkShare（免费）**，无需注册即可使用。你可以切换到其他数据源：

| 数据源 | 命令 | 适用场景 |
|--------|------|----------|
| AkShare（默认） | 无需配置 | 免费，学习/原型验证 |
| Tushare | `export QUANTSEED_DATA_PROVIDER=tushare` | 有 Token，回测/研究 |
| SQLite/QMT | `export QUANTSEED_DATA_PROVIDER=sqlite` | QMT 用户，生产环境 |

```bash
# 默认使用 AkShare（免费，无需配置）
quantseed run

# 使用 Tushare
export TUSHARE_TOKEN=你的token
export QUANTSEED_DATA_PROVIDER=tushare
quantseed run

# 使用 QMT SQLite
export QUANTSEED_DATA_PROVIDER=sqlite
export QMT_DATA_PATH=C:/qmt_data/db.sqlite
quantseed run
```

> 三种数据源的差异、注册方式、积分权限、限流规避等详见 [数据源说明](docs/data-sources.md)。

---

## 写一个策略

策略只需继承 `BaseStrategy`，实现三个钩子，用 `self.buy/sell` 下单：

```python
# strategies/my_strategy/strategy.py
import datetime
from quantseed.strategy_base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "我的第一个策略"

    def __init__(self, strategy_dir=None):
        super().__init__(strategy_dir)
        # 从 config.json 读参数
        self.universe = self.config.get("universe", ["000001", "600519"])
        # 首次运行初始化资金
        if self.state.get("initial_capital") is None:
            self.state.update(
                initial_capital=100000.0,
                cash=100000.0,
                positions={},
                last_equity=100000.0,
            )

    def on_open(self, now: datetime.datetime):
        """09:25 - 检查止损"""
        for code in list(self.state.get("positions", {}).keys()):
            pos = self.get_position(code)
            price = self.get_price(code, now)
            if pos and price > 0:
                pnl = (price - pos["avg_cost"]) / pos["avg_cost"]
                if pnl < -0.08:  # 亏损 8% 止损
                    self.sell_all(code, price, now=now, note="止损")

    def on_close(self, now: datetime.datetime):
        """14:45 - 买入信号"""
        if len(self.state.get("positions", {})) >= 3:
            return  # 已满仓
        code = self.universe[0]
        price = self.get_price(code, now)
        if price > 0:
            qty = int(30000 / price / 100) * 100  # 3 万资金，整百手
            if qty > 0:
                self.buy(code, qty, price, now=now, note="建仓")

    def on_eod(self, now: datetime.datetime):
        """15:05 - 记录净值"""
        self.tracker.record_equity(
            total_equity=self.get_total_equity(now),
            cash=self.get_cash(),
            stock_value=self.get_stock_value(now),
            positions=len(self.state.get("positions", {})),
            pnl_daily=self.get_total_equity(now) - self.state.get("last_equity", 0),
            date=now,
        )
        self.state.update(last_equity=self.get_total_equity(now))
```

配套 `config.json`：
```json
{
    "universe": ["000001", "600519", "300750"]
}
```

### BaseStrategy 常用方法

| 方法 | 说明 |
|------|------|
| `self.buy(code, qty, price, now=None, note="")` | 买入，自动管理 state + 交易日志 |
| `self.sell(code, qty, price, now=None, note="")` | 卖出 |
| `self.sell_all(code, price, now=None, note="")` | 清仓 |
| `self.get_position(code)` | 获取持仓 `{qty, avg_cost}` |
| `self.get_cash()` | 当前现金 |
| `self.get_total_equity(now)` | 总净值（现金 + 持仓市值） |
| `self.get_price(code, now)` | 获取价格（回测取历史价，实盘取实时价） |
| `self.log(msg)` | 打印日志 |
| `self.data.get_daily_prices(codes, start, end)` | 获取历史日线 |

> 完整 API 详见 [API 参考文档](docs/api.md)。

---

## 回测

回测引擎在历史数据上驱动策略执行，自动计算绩效指标：

```bash
# CLI 一键回测
quantseed backtest examples/dual_ma_strategy/ \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --capital 100000 \
    --warmup 25
```

```python
# Python API
from quantseed.data.sqlite_provider import SQLiteProvider
from quantseed.backtest import Backtester, BacktestConfig
from examples.dual_ma_strategy.strategy import DualMAStrategy
from pathlib import Path

data = SQLiteProvider("examples/dual_ma_strategy/data/demo.db")
strategy_dir = Path("examples/dual_ma_strategy/run")
Backtester.clean_artifacts(strategy_dir)  # 清理上次产物
strategy = DualMAStrategy(strategy_dir)

config = BacktestConfig(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    warmup_days=25,  # 跳过前 25 天（均线预热）
)

bt = Backtester(strategy, data, config)
result = bt.run()
print(result.summary())
# result.metrics       -> dict（总收益率/年化/夏普/最大回撤）
# result.equity_curve  -> DataFrame（每日净值）
# result.trades        -> DataFrame（交易明细）
```

---

## CLI 命令

```bash
quantseed --version              # 查看版本
quantseed check [--verbose]      # 检查环境（依赖/数据源/策略）
quantseed run [--once]           # 运行策略（--once 调试模式，执行一次后退出）
quantseed backtest <dir> [opts]  # 回测策略
quantseed sync [--full]          # 同步数据
```

---

## 阅读 SOP

完整的标准化投研流程，含真实项目案例：

[SOP.md](./SOP.md)

---

## 项目结构

```
quantseed/
├── SOP.md                       # 方法论（V3.1）
├── README.md
├── CHANGELOG.md                 # 版本变更记录
├── LICENSE
├── pyproject.toml
├── quantseed/
│   ├── __init__.py              # 包入口
│   ├── config.py                # 环境变量驱动 + 数据源工厂
│   ├── scheduler.py             # 主循环调度器
│   ├── strategy_base.py         # 策略基类（含 buy/sell 下单方法）
│   ├── state_store.py           # 状态持久化
│   ├── equity_tracker.py        # 净值追踪
│   ├── trading.py               # QMT 交易封装
│   ├── cli.py                   # 命令行入口
│   ├── backtest/                # 回测引擎
│   │   ├── engine.py            #   Backtester
│   │   └── metrics.py           #   绩效指标
│   └── data/                    # 数据层
│       ├── interface.py         #   数据接口抽象
│       ├── akshare_provider.py  #   AkShare（免费）
│       ├── tushare_provider.py  #   Tushare
│       └── sqlite_provider.py   #   QMT SQLite
├── examples/
│   ├── demo_strategy/           # 最小示例（买入持有 + 止损）
│   └── dual_ma_strategy/        # 双均线策略（含回测）
├── tests/                       # 单元测试（90 个）
└── docs/
    ├── api.md                   # API 参考文档
    └── data-sources.md          # 数据源说明
```

---

## 许可证

MIT
