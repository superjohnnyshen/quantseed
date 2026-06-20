# QuantSeed

> 量化策略从零到一启动包：**SOP 方法论 + 多策略框架 + 数据管道**。

---

## 这是什么

QuantSeed 不是又一个回测框架，而是一个**完整的量化策略开发启动包**：

| 组件 | 说明 |
|------|------|
| **SOP.md** | 从立项到实盘的标准化流程，配真实失败案例 |
| **多策略框架** | 插件式架构，一个策略一个目录，自动发现 |
| **数据管道** | 统一数据接口，支持 QMT / Tushare / AkShare |

---

## 快速开始

```bash
pip install quantseed
```

### 第一步：检查环境

```bash
quantseed check
```

### 第二步：复制示例策略

```bash
cp -r examples/demo_strategy/ strategies/
```

### 第三步：启动

```bash
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

---

## 写一个策略

```python
# strategies/my_strategy/strategy.py
import datetime
from quantseed.strategy_base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "我的第一个策略"

    def on_open(self, now: datetime.datetime):
        # 9:25 - 卖出昨日持仓
        self.log("开盘卖出")

    def on_close(self, now: datetime.datetime):
        # 14:45 - 买入建仓
        codes = self.data.get_all_codes()
        self.log(f"可交易股票: {len(codes)} 只")

    def on_eod(self, now: datetime.datetime):
        # 15:05 - 日终对账
        self.tracker.record_equity(100000, 100000, 0, 0)
```

---

## 阅读 SOP

完整的标准化投研流程，含真实项目案例：

→ [SOP.md](./SOP.md)

---

## 项目结构

```
quantseed/
├── SOP.md                     # 方法论
├── README.md
├── pyproject.toml
├── quantseed/
│   ├── config.py              # 环境变量驱动
│   ├── scheduler.py           # 主循环
│   ├── strategy_base.py       # 策略基类
│   ├── state_store.py         # 状态持久化
│   ├── equity_tracker.py      # 净值追踪
│   ├── trading.py             # QMT 交易封装（可选）
│   ├── cli.py                 # 命令行入口
│   └── data/                  # 数据层
│       ├── interface.py       # 数据接口
│       ├── sqlite_provider.py # QMT/SQLite
│       ├── tushare_provider.py
│       └── akshare_provider.py
├── examples/
│   └── demo_strategy/
└── .trae/                     # TRAE Skill 配置
```

---

## 许可证

MIT