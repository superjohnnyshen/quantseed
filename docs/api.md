# QuantSeed API 参考文档

> 本文档基于 QuantSeed 源码自动整理，覆盖策略开发、回测、数据接口、状态持久化与命令行工具。

## 目录

- [1. 概述](#1-概述)
- [2. BaseStrategy 策略基类](#2-basestrategy-策略基类)
  - [2.1 类属性与实例属性](#21-类属性与实例属性)
  - [2.2 生命周期钩子](#22-生命周期钩子)
  - [2.3 下单方法](#23-下单方法)
  - [2.4 持仓与资金查询](#24-持仓与资金查询)
  - [2.5 工具方法](#25-工具方法)
- [3. DataProvider 数据接口](#3-dataprovider-数据接口)
  - [3.1 接口方法](#31-接口方法)
  - [3.2 DataFrame 列名规范](#32-dataframe-列名规范)
  - [3.3 内置实现](#33-内置实现)
- [4. 回测引擎](#4-回测引擎)
  - [4.1 BacktestConfig](#41-backtestconfig)
  - [4.2 Backtester](#42-backtester)
  - [4.3 BacktestResult](#43-backtestresult)
- [5. 绩效指标 metrics](#5-绩效指标-metrics)
- [6. StateStore 状态持久化](#6-statestore-状态持久化)
- [7. EquityTracker 净值与交易日志](#7-equitytracker-净值与交易日志)
- [8. CLI 命令行工具](#8-cli-命令行工具)

---

## 1. 概述

QuantSeed 是面向 A 股个人量化的轻量框架，核心设计原则：

- **三个钩子驱动**：策略只需实现 `on_open` / `on_close` / `on_eod` 三个时间点逻辑。
- **回测/实盘同构**：同一份策略代码在回测和实盘下行为一致，回测通过注入历史时间触发钩子。
- **状态持久化**：每个策略独立维护 `state.json`，支持崩溃恢复。
- **数据源可插拔**：通过 `DataProvider` 抽象接口支持 SQLite / AkShare / Tushare。

策略目录约定：

```
strategies/<name>/
  strategy.py         策略代码（继承 BaseStrategy）
  config.json         策略参数
  state.json          运行状态（自动生成，崩溃恢复用）
  trades.csv          交易日志（自动生成）
  equity.csv          净值曲线（自动生成）
```

---

## 2. BaseStrategy 策略基类

`quantseed.strategy_base.BaseStrategy` 是所有策略的基类。子类只需实现三个钩子方法，下单/查询/日志等通用能力由基类提供。

### 2.1 类属性与实例属性

#### 类属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | `"base"` | 策略名称，用于日志、交易记录、策略目录定位 |
| `description` | `str` | `"基础策略"` | 策略描述 |

#### 实例属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `strategy_dir` | `pathlib.Path` | 策略目录路径，默认为 `STRATEGIES_DIR / self.name` |
| `state` | `StateStore` | 状态持久化对象，读写 `state.json` |
| `tracker` | `EquityTracker` | 净值/交易日志记录器 |
| `config` | `dict` | 从 `config.json` 加载的策略参数，文件不存在时为空 dict |
| `data` | `DataProvider \| None` | 数据接口，由调度器或回测引擎注入 |
| `trader` | `TradingAPI \| None` | 交易接口，实盘时注入，回测/模拟模式下为 `None` |

#### 示例

```python
from quantseed.strategy_base import BaseStrategy

class MyStrategy(BaseStrategy):
    name = "my_strategy"
    description = "我的第一个策略"

    def on_open(self, now):
        # 通过 self.config 读取参数
        hold_days = self.config.get("hold_days", 5)
        ...

    def on_close(self, now):
        ...

    def on_eod(self, now):
        ...
```

### 2.2 生命周期钩子

每个交易日，调度器（或回测引擎）按以下顺序触发三个钩子：

| 钩子 | 触发时间 | 典型用途 |
|------|----------|----------|
| `on_open(now)` | 09:25 | 开盘后操作，如卖出昨日持仓 |
| `on_close(now)` | 14:45 | 尾盘操作，如买入建仓 |
| `on_eod(now)` | 15:05 | 收盘后对账、记录净值 |

#### `on_open(now)`

```python
def on_open(self, now: datetime.datetime) -> None
```

- **参数**：
  - `now` (`datetime.datetime`)：当前时间戳。回测时为历史时间，实盘时为真实时间。
- **返回值**：无

#### `on_close(now)`

```python
def on_close(self, now: datetime.datetime) -> None
```

- **参数**：同 `on_open`
- **返回值**：无

#### `on_eod(now)`

```python
def on_eod(self, now: datetime.datetime) -> None
```

- **参数**：同 `on_open`
- **返回值**：无

#### 示例

```python
def on_eod(self, now):
    # 日终记录净值
    total = self.get_total_equity(now)
    cash = self.get_cash()
    stock = self.get_stock_value(now)
    positions = self.state.get("positions", {})
    self.tracker.record_equity(
        total_equity=total, cash=cash, stock_value=stock,
        positions=len(positions), date=now,
    )
    self.log(f"日终净值: {total:.2f}")
```

### 2.3 下单方法

#### `buy(code, qty, price, now=None, note="")`

买入股票。封装状态更新、交易日志、实盘下单（如果 `trader` 已连接）。

```python
def buy(self, code: str, qty: int, price: float,
        now: Optional[datetime.datetime] = None, note: str = "") -> bool
```

- **参数**：
  - `code` (`str`)：股票代码，6 位数字字符串（如 `"000001"`）
  - `qty` (`int`)：买入数量（股，应为 100 的整数倍）
  - `price` (`float`)：买入价格
  - `now` (`datetime.datetime | None`)：时间戳。回测传入历史时间，实盘默认 `None`
  - `note` (`str`)：备注信息，写入交易日志
- **返回值**：`bool`。`True` 成功；`False` 失败（现金不足 / 下单失败 / 参数非法）
- **行为**：
  1. 校验 `qty > 0` 且 `price > 0`
  2. 校验现金充足，不足则记录日志并返回 `False`
  3. 若 `trader` 已连接，调用 `trader.order_buy` 实盘下单
  4. 更新 `state.positions`（已有持仓则按加权平均更新 `avg_cost`）
  5. 扣减 `state.cash`
  6. 调用 `tracker.record_trade` 写入交易日志

#### 示例

```python
def on_close(self, now):
    code = "600519"
    price = self.get_price(code, now)
    if price > 0 and self.get_cash() > price * 100:
        ok = self.buy(code, 100, price, now=now, note="尾盘建仓")
        if not ok:
            self.log("买入失败")
```

#### `sell(code, qty, price, now=None, note="")`

卖出股票。

```python
def sell(self, code: str, qty: int, price: float,
         now: Optional[datetime.datetime] = None, note: str = "") -> bool
```

- **参数**：同 `buy`
- **返回值**：`bool`。`True` 成功；`False` 失败（无持仓 / 持仓不足 / 下单失败 / 参数非法）
- **行为**：
  1. 校验参数与持仓
  2. 若 `trader` 已连接，调用 `trader.order_sell` 实盘下单
  3. 更新 `state.positions`（卖出后数量为 0 则删除该 code 键）
  4. 增加 `state.cash`
  5. 写入交易日志

#### 示例

```python
def on_open(self, now):
    code = "600519"
    qty = self.get_position_qty(code)
    if qty > 0:
        price = self.get_price(code, now)
        self.sell(code, qty, price, now=now, note="开盘清仓")
```

#### `sell_all(code, price, now=None, note="")`

清仓某只股票（卖出全部持仓）。

```python
def sell_all(self, code: str, price: float,
             now: Optional[datetime.datetime] = None, note: str = "") -> bool
```

- **参数**：同 `sell`，但无需指定 `qty`
- **返回值**：`bool`。无持仓时返回 `False`，否则透传 `sell` 的返回值
- **实现**：内部调用 `get_position_qty` 获取数量后委托给 `sell`

#### 示例

```python
def on_open(self, now):
    for code in list(self.state.get("positions", {}).keys()):
        price = self.get_price(code, now)
        self.sell_all(code, price, now=now)
```

### 2.4 持仓与资金查询

#### `get_position(code)`

获取某只股票的持仓信息。

```python
def get_position(self, code: str) -> Optional[Dict]
```

- **参数**：`code` (`str`)：股票代码
- **返回值**：`dict | None`。格式 `{"qty": int, "avg_cost": float}`；无持仓返回 `None`

#### `get_position_qty(code)`

获取某只股票的持仓数量。

```python
def get_position_qty(self, code: str) -> int
```

- **参数**：`code` (`str`)：股票代码
- **返回值**：`int`。持仓股数，无持仓返回 `0`

#### `get_cash()`

获取当前现金。

```python
def get_cash(self) -> float
```

- **返回值**：`float`。当前可用现金

#### `get_stock_value(now=None)`

计算当前持仓市值。

```python
def get_stock_value(self, now: Optional[datetime.datetime] = None) -> float
```

- **参数**：`now` (`datetime.datetime | None`)：时间戳。回测传入历史时间取当日价，实盘为 `None` 取实时价
- **返回值**：`float`。所有持仓的市值之和；无持仓或 `data` 未注入时返回 `0.0`
- **依赖**：需要 `self.data` 已注入

#### `get_total_equity(now=None)`

计算当前总净值 = 现金 + 持仓市值。

```python
def get_total_equity(self, now: Optional[datetime.datetime] = None) -> float
```

- **参数**：同 `get_stock_value`
- **返回值**：`float`。总净值

#### `get_price(code, now=None)`

获取股票价格。

```python
def get_price(self, code: str, now: Optional[datetime.datetime] = None) -> float
```

- **参数**：
  - `code` (`str`)：股票代码
  - `now` (`datetime.datetime | None`)：时间戳
- **返回值**：`float`。股票价格；`data` 未注入或获取失败返回 `0.0`
- **行为**：
  - 回测场景（传入 `now`）：优先调用 `data.get_price_on_date(code, date_str)` 取历史当日收盘价
  - 实盘场景（`now` 为 `None`）：调用 `data.get_latest_price(code)` 取实时价

#### 示例

```python
def on_eod(self, now):
    cash = self.get_cash()
    stock = self.get_stock_value(now)
    total = self.get_total_equity(now)
    pos = self.get_position("600519")
    if pos:
        self.log(f"持仓 600519: {pos['qty']} 股, 成本 {pos['avg_cost']:.2f}")
    self.log(f"现金 {cash:.2f}, 市值 {stock:.2f}, 净值 {total:.2f}")
```

### 2.5 工具方法

#### `log(msg)`

统一日志格式输出到 stdout。

```python
def log(self, msg) -> None
```

- **参数**：`msg`：日志消息
- **输出格式**：`[<策略名>] <时间戳> - <消息>`

#### `is_trading_day()`

判断今天是否为交易日。

```python
def is_trading_day(self) -> bool
```

- **返回值**：`bool`
- **行为**：优先使用注入的 `data.get_trade_calendar` 查询交易日历；`data` 未注入或查询异常时降级为周一至周五判断

#### 示例

```python
def on_open(self, now):
    if not self.is_trading_day():
        return  # 非交易日跳过
    self.log("开始执行策略")
```

---

## 3. DataProvider 数据接口

`quantseed.data.interface.DataProvider` 是数据源的抽象基类（继承 `abc.ABC`），定义了策略可调用的全部数据方法。内置三个实现：`SQLiteProvider`、`AkShareProvider`、`TushareProvider`。

### 3.1 接口方法

#### `get_daily_prices(codes, start_date, end_date)`

获取股票日线行情。

```python
def get_daily_prices(self, codes: List[str], start_date: str, end_date: str) -> pd.DataFrame
```

- **参数**：
  - `codes` (`List[str]`)：股票代码列表（6 位数字字符串）
  - `start_date` (`str`)：开始日期，格式 `YYYY-MM-DD`
  - `end_date` (`str`)：结束日期，格式 `YYYY-MM-DD`
- **返回值**：`pd.DataFrame`，列名见 [3.2 DataFrame 列名规范](#32-dataframe-列名规范)

#### `get_stock_basic(codes=None)`

获取股票基本信息。

```python
def get_stock_basic(self, codes: Optional[List[str]] = None) -> pd.DataFrame
```

- **参数**：`codes` (`List[str] | None`)：股票代码列表，`None` 表示全部
- **返回值**：`pd.DataFrame`

#### `get_fundamentals(codes, date)`

获取基本面数据。

```python
def get_fundamentals(self, codes: List[str], date: str) -> pd.DataFrame
```

- **参数**：
  - `codes` (`List[str]`)：股票代码列表
  - `date` (`str`)：报告期，格式 `YYYY-MM-DD`（不同实现对日期过滤的支持程度不同）
- **返回值**：`pd.DataFrame`

#### `get_trade_calendar(start_date, end_date)`

获取交易日历。

```python
def get_trade_calendar(self, start_date: str, end_date: str) -> List[str]
```

- **参数**：`start_date`、`end_date` (`str`)：日期，格式 `YYYY-MM-DD`
- **返回值**：`List[str]`，升序排列的交易日字符串列表，格式 `YYYY-MM-DD`

#### `get_latest_price(code)`

获取最新价格（实盘场景）。

```python
def get_latest_price(self, code: str) -> float
```

- **参数**：`code` (`str`)：股票代码
- **返回值**：`float`。最新价；获取失败返回 `0.0`

#### `get_price_on_date(code, date)`

获取指定日期的收盘价（回测场景）。

```python
def get_price_on_date(self, code: str, date: str) -> float
```

- **参数**：
  - `code` (`str`)：股票代码
  - `date` (`str`)：日期，格式 `YYYY-MM-DD`
- **返回值**：`float`。当日收盘价；无数据返回 `0.0`
- **默认实现**：从 `get_daily_prices([code], date, date)` 取最后一行的 `close` 列。子类可重写以优化性能。

#### `get_all_codes()`

获取全部股票代码。

```python
def get_all_codes(self) -> List[str]
```

- **返回值**：`List[str]`。默认从 `get_stock_basic()` 的 `code` 列派生。

#### `get_index_daily(index_code, start_date, end_date)`

获取指数日线行情。

```python
def get_index_daily(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame
```

- **参数**：
  - `index_code` (`str`)：指数代码
  - `start_date`、`end_date` (`str`)：日期，格式 `YYYY-MM-DD`
- **返回值**：`pd.DataFrame`

### 3.2 DataFrame 列名规范

不同数据源返回的 DataFrame 列名略有差异，下表列出各实现的实际列名。

#### `get_daily_prices` 返回列

| 列名 | SQLite | AkShare | Tushare | 说明 |
|------|:------:|:-------:|:-------:|------|
| `trade_date` | ✅ | ✅ | ✅ | 交易日期（字符串） |
| `code` | ✅ | ✅ | ✅ | 股票代码（6 位） |
| `open` | ✅ | ✅ | ✅ | 开盘价 |
| `close` | ✅ | ✅ | ✅ | 收盘价 |
| `high` | ✅ | ✅ | ✅ | 最高价 |
| `low` | ✅ | ✅ | ✅ | 最低价 |
| `volume` | ✅ | ✅ | ✅ | 成交量 |
| `amount` | ✅ | ✅ | ✅ | 成交额 |
| `change_pct` | ✅ | ✅ | ✅ | 涨跌幅（%） |
| `turnover_rate` | ✅ | ✅ | — | 换手率（%） |
| `amplitude` | — | ✅ | — | 振幅 |
| `change_amount` | — | ✅ | — | 涨跌额 |
| `ts_code` | — | — | ✅ | Tushare 原始代码（如 `600519.SH`） |

> 注：AkShare 与 Tushare 返回的后复权数据（`adjust="hfq"` / `adj='hfq'`）。

#### `get_stock_basic` 返回列

| 列名 | SQLite | AkShare | Tushare | 说明 |
|------|:------:|:-------:|:-------:|------|
| `code` | ✅ | ✅ | ✅ | 股票代码（6 位） |
| `name` | ✅ | ✅ | ✅ | 股票名称 |
| `list_date` | ✅ | — | ✅ | 上市日期 |
| `delist_date` | ✅ | — | ✅ | 退市日期 |
| `ts_code` | — | — | ✅ | Tushare 原始代码 |

#### `get_index_daily` 返回列

| 列名 | SQLite | AkShare | Tushare | 说明 |
|------|:------:|:-------:|:-------:|------|
| `trade_date` | ✅ | ✅ | ✅ | 交易日期 |
| `open` | ✅ | — | — | 开盘价 |
| `close` | ✅ | — | — | 收盘价 |
| `high` | ✅ | — | — | 最高价 |
| `low` | ✅ | — | — | 最低价 |
| `volume` | ✅ | — | ✅ | 成交量 |
| `amount` | ✅ | — | — | 成交额 |
| `change_pct` | ✅ | — | ✅ | 涨跌幅 |

> 注：AkShare 与 Tushare 的 `get_index_daily` 直接透传上游字段，列名以原始接口为准。

#### `get_fundamentals` 返回列

- **SQLite**：`SELECT * FROM fundamentals WHERE code IN (...) AND report_date = ?`，列名取决于数据库 schema，至少包含 `code`、`report_date`。
- **AkShare**：透传 `ak.stock_financial_report_sina` 的全部字段，并追加 `code` 列。`date` 参数暂被忽略，返回最新可用报告。
- **Tushare**：透传 `pro.fina_indicator` 的全部字段，并追加 `code` 列。按 `period` 过滤。

### 3.3 内置实现

| 实现类 | 模块路径 | 数据来源 | 适用场景 |
|--------|----------|----------|----------|
| `SQLiteProvider` | `quantseed.data.sqlite_provider` | 本地 SQLite 数据库 | 回测、离线分析、QMT 数据同步 |
| `AkShareProvider` | `quantseed.data.akshare_provider` | AkShare 公开接口 | 免费实盘、快速验证 |
| `TushareProvider` | `quantseed.data.tushare_provider` | Tushare Pro 接口 | 专业研究、需 Token |

#### `SQLiteProvider` 构造

```python
from quantseed.data.sqlite_provider import SQLiteProvider

data = SQLiteProvider(db_path="path/to/data.db")
```

- **参数**：`db_path` (`str`)：SQLite 数据库文件路径
- **要求**：数据库需包含 `daily_prices`、`stock_basic`、`index_daily`、`fundamentals`、`trade_calendar` 等表

#### 示例

```python
from quantseed.data.sqlite_provider import SQLiteProvider

data = SQLiteProvider("data/demo.db")
df = data.get_daily_prices(["600519"], "2024-01-01", "2024-12-31")
print(df[["trade_date", "code", "close"]].head())

calendar = data.get_trade_calendar("2024-01-01", "2024-01-31")
print(f"1 月交易日数: {len(calendar)}")
```

---

## 4. 回测引擎

`quantseed.backtest.engine` 提供回测能力，镜像实盘调度流程在历史交易日上逐日驱动策略。

### 4.1 BacktestConfig

回测参数配置（`@dataclass`）。

```python
from quantseed.backtest import BacktestConfig

config = BacktestConfig(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    warmup_days=25,
    progress=True,
)
```

#### 字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start_date` | `str` | — | 回测开始日期（`YYYY-MM-DD`），必填 |
| `end_date` | `str` | — | 回测结束日期（`YYYY-MM-DD`），必填 |
| `initial_capital` | `float` | `100000.0` | 初始资金 |
| `warmup_days` | `int` | `0` | 预热天数，跳过前 N 个交易日（用于均线等指标预热） |
| `progress` | `bool` | `True` | 是否打印回测进度 |

### 4.2 Backtester

回测引擎。

```python
from quantseed.backtest import Backtester, BacktestConfig

bt = Backtester(strategy, data, config)
result = bt.run()
```

#### `__init__(strategy, data, config)`

```python
def __init__(self, strategy: BaseStrategy, data: DataProvider, config: BacktestConfig)
```

- **参数**：
  - `strategy` (`BaseStrategy`)：策略实例（已初始化，`strategy_dir` 指向可写目录）
  - `data` (`DataProvider`)：数据源
  - `config` (`BacktestConfig`)：回测参数

#### `run() -> BacktestResult`

执行回测。

```python
def run(self) -> BacktestResult
```

- **返回值**：`BacktestResult`
- **流程**：
  1. 注入数据源到策略
  2. 获取交易日历，跳过 `warmup_days` 个预热日
  3. 逐日触发 `on_open(09:25)` → `on_close(14:45)` → `on_eod(15:05)`
  4. 读取 `equity.csv` 与 `trades.csv`，计算绩效指标
- **注意**：调用方应保证 `strategy_dir` 下没有上一次回测的 `state.json`/`equity.csv`/`trades.csv`，否则状态会延续。推荐先调用 `clean_artifacts`。

#### `clean_artifacts(strategy_dir)` (静态方法)

清理策略目录下的回测产物。

```python
@staticmethod
def clean_artifacts(strategy_dir) -> None
```

- **参数**：`strategy_dir` (`str | Path`)：策略目录路径
- **清理文件**：`state.json`、`equity.csv`、`trades.csv`
- **应在构造策略前调用**，保证回测从干净状态开始

#### 示例

```python
from quantseed.data.sqlite_provider import SQLiteProvider
from quantseed.backtest import Backtester, BacktestConfig

# 1. 清理上次回测产物
Backtester.clean_artifacts("strategies/my_strategy")

# 2. 初始化策略与数据
strategy = MyStrategy(strategy_dir="strategies/my_strategy")
data = SQLiteProvider("data/demo.db")

# 3. 配置回测
config = BacktestConfig(
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000.0,
    warmup_days=25,
)

# 4. 执行
bt = Backtester(strategy, data, config)
result = bt.run()
print(result.summary())
```

### 4.3 BacktestResult

回测结果（`@dataclass`）。

#### 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `metrics` | `dict` | 绩效指标字典，详见 [第 5 节](#5-绩效指标-metrics) |
| `equity_curve` | `pd.DataFrame` | 净值曲线，列同 `equity.csv` |
| `trades` | `pd.DataFrame` | 交易明细，列同 `trades.csv` |
| `trading_days` | `list` | 实际回测的交易日列表 |

#### `summary() -> str`

生成文本摘要。

```python
def summary(self) -> str
```

- **返回值**：`str`。包含回测区间、初始资金、最终净值、总收益率、年化收益率、最大回撤、夏普比率、交易次数的格式化文本

#### `equity_chart(width=50, height=15) -> str`

生成 ASCII 净值曲线图。

```python
def equity_chart(self, width: int = 50, height: int = 15) -> str
```

- **参数**：
  - `width`：图表宽度（字符数），默认 50
  - `height`：图表高度（行数），默认 15
- **返回值**：`str`。ASCII 图表字符串，含坐标轴和日期范围
- **示例输出**：
```
净值曲线 (99325 ~ 101250)
┌───────────────────────────────────┐
│                                 ● │
│                                ││ │
│                                │ ●│
│                                │  │
│●●●●●●●●●●●●●●●●●●●●●●●●●●   │ ●   │
│                         │   │     │
│                         │  ●●     │
│                         │ │       │
│                         │ ●       │
│                          ●        │
└───────────────────────────────────┘
  2024-02-06               2024-03-25
```

#### `equity_curve` 列名

| 列名 | 类型 | 说明 |
|------|------|------|
| `date` | `str` | 日期（`YYYY-MM-DD`） |
| `total_equity` | `float` | 总净值 |
| `cash` | `float` | 现金 |
| `stock_value` | `float` | 持仓市值 |
| `positions` | `int` | 持仓股票数量 |
| `pnl_daily` | `float` | 当日盈亏 |

#### `trades` 列名

| 列名 | 类型 | 说明 |
|------|------|------|
| `datetime` | `str` | 交易时间（`YYYY-MM-DD HH:MM:SS`） |
| `code` | `str` | 股票代码 |
| `name` | `str` | 股票名称（默认等于 code） |
| `action` | `str` | 交易方向（`BUY` / `SELL`） |
| `price` | `float` | 成交价格 |
| `qty` | `int` | 成交数量 |
| `amount` | `float` | 成交金额 |
| `strategy` | `str` | 策略名称 |
| `note` | `str` | 备注 |

#### 示例

```python
result = bt.run()
print(result.summary())

# 访问指标
print(f"夏普比率: {result.metrics['sharpe']:.3f}")
print(f"最大回撤: {result.metrics['max_drawdown_pct']:.2%}")

# 导出净值曲线
result.equity_curve.to_csv("output/equity.csv", index=False)
```

---

## 5. 绩效指标 metrics

`quantseed.backtest.metrics` 提供绩效指标计算函数。所有函数接收 equity DataFrame（列：`date`、`total_equity`、`pnl_daily`），返回纯数值或字典，不依赖任何 I/O。

#### `total_return(equity_df, initial_capital) -> float`

总收益率。

```python
def total_return(equity_df: pd.DataFrame, initial_capital: float) -> float
```

- **参数**：
  - `equity_df` (`pd.DataFrame`)：净值曲线，需含 `total_equity` 列
  - `initial_capital` (`float`)：初始资金
- **返回值**：`float`。小数形式，如 `0.088` 表示 +8.8%

#### `annual_return(total_ret, num_trading_days) -> float`

年化收益率，按 252 个交易日年化。

```python
def annual_return(total_ret: float, num_trading_days: int) -> float
```

- **参数**：
  - `total_ret` (`float`)：总收益率（小数）
  - `num_trading_days` (`int`)：交易日数
- **返回值**：`float`。公式 `(1 + r)^(252/n) - 1`

#### `max_drawdown(equity_df) -> tuple`

最大回撤。

```python
def max_drawdown(equity_df: pd.DataFrame) -> tuple
```

- **参数**：`equity_df` (`pd.DataFrame`)：净值曲线
- **返回值**：`tuple (float, float)`。`(绝对回撤金额, 百分比回撤)`，百分比为负数（如 `-0.12` 表示 -12%）

#### `sharpe_ratio(equity_df, annualization=252) -> float`

夏普比率（简化版，无风险利率 = 0）。

```python
def sharpe_ratio(equity_df: pd.DataFrame, annualization: int = 252) -> float
```

- **参数**：
  - `equity_df` (`pd.DataFrame`)：净值曲线
  - `annualization` (`int`)：年化因子，默认 252
- **返回值**：`float`。公式 `mean(daily_return) / std(daily_return) * sqrt(252)`

#### `compute_metrics(equity_df, initial_capital, num_trading_days, num_trades=0) -> dict`

一次性计算全部指标。

```python
def compute_metrics(
    equity_df: pd.DataFrame,
    initial_capital: float,
    num_trading_days: int,
    num_trades: int = 0,
) -> Dict[str, float]
```

- **返回值**：`dict`，包含以下键：

| 键 | 类型 | 说明 |
|----|------|------|
| `initial_capital` | `float` | 初始资金 |
| `final_equity` | `float` | 最终净值 |
| `total_return` | `float` | 总收益率（小数） |
| `annual_return` | `float` | 年化收益率（小数） |
| `max_drawdown` | `float` | 最大回撤绝对值 |
| `max_drawdown_pct` | `float` | 最大回撤百分比（负数） |
| `sharpe` | `float` | 夏普比率 |
| `num_trades` | `int` | 交易次数 |
| `num_trading_days` | `int` | 交易日数 |

#### 示例

```python
from quantseed.backtest.metrics import compute_metrics

metrics = compute_metrics(
    equity_df=result.equity_curve,
    initial_capital=100000.0,
    num_trading_days=242,
    num_trades=48,
)
print(f"年化收益: {metrics['annual_return']:.2%}")
print(f"最大回撤: {metrics['max_drawdown_pct']:.2%}")
```

---

## 6. StateStore 状态持久化

`quantseed.state_store.StateStore` 提供简单的 JSON 状态持久化，支持原子写入与缓存。每个策略实例独立管理自己的 `state.json`。

#### `__init__(state_path)`

```python
def __init__(self, state_path: Path)
```

- **参数**：`state_path` (`Path`)：状态文件路径

#### `load(default=None) -> dict`

加载状态。带文件 mtime 缓存，文件未修改时直接返回缓存。

```python
def load(self, default=None) -> dict
```

- **参数**：`default` (`dict | None`)：文件不存在或加载失败时的返回值，默认 `{}`
- **返回值**：`dict`。状态字典

#### `save(data) -> None`

保存状态。先写临时文件再原子替换，Windows 下对 `PermissionError` 重试 5 次。

```python
def save(self, data) -> None
```

- **参数**：`data` (`dict`)：要保存的状态字典

#### `update(**kwargs) -> dict`

更新部分字段并保存。

```python
def update(self, **kwargs) -> dict
```

- **参数**：`**kwargs`：要更新的键值对
- **返回值**：`dict`。更新后的完整状态

#### `get(key, default=None)`

读取单个字段。

```python
def get(self, key, default=None)
```

- **参数**：
  - `key` (`str`)：字段名
  - `default`：字段不存在时的默认值
- **返回值**：字段值或 `default`

#### state.json 典型结构

```json
{
  "cash": 50000.0,
  "positions": {
    "600519": {"qty": 100, "avg_cost": 1800.0},
    "000001": {"qty": 200, "avg_cost": 12.5}
  }
}
```

#### 示例

```python
# 在策略中读写自定义状态
self.state.update(last_buy_date="2024-03-15")
last = self.state.get("last_buy_date")
```

---

## 7. EquityTracker 净值与交易日志

`quantseed.equity_tracker.EquityTracker` 负责记录净值曲线与交易明细，写入 CSV 文件。每个策略实例独立管理自己的 `equity.csv` 和 `trades.csv`。

#### `__init__(equity_path, trades_path)`

```python
def __init__(self, equity_path: Path, trades_path: Path)
```

- **参数**：
  - `equity_path` (`Path`)：净值曲线 CSV 路径
  - `trades_path` (`Path`)：交易明细 CSV 路径
- **行为**：构造时自动写入表头（文件不存在时）

#### `record_equity(total_equity, cash, stock_value, positions, pnl_daily=0.0, date=None)`

记录当日净值。

```python
def record_equity(self, total_equity, cash, stock_value, positions,
                  pnl_daily=0.0, date=None)
```

- **参数**：
  - `total_equity` (`float`)：总净值
  - `cash` (`float`)：现金
  - `stock_value` (`float`)：持仓市值
  - `positions` (`int`)：持仓股票数量
  - `pnl_daily` (`float`)：当日盈亏，默认 `0.0`
  - `date` (`datetime.date | datetime.datetime | str | None`)：日期。实盘默认今天；回测应传入当日日期。接受 `datetime.date` / `datetime.datetime` / `YYYY-MM-DD` 字符串
- **写入列**：`date, total_equity, cash, stock_value, positions, pnl_daily`

#### `record_trade(code, name, action, price, qty, strategy, note="", dt=None)`

记录一笔交易。

```python
def record_trade(self, code, name, action, price, qty, strategy, note="", dt=None)
```

- **参数**：
  - `code` (`str`)：股票代码
  - `name` (`str`)：股票名称
  - `action` (`str`)：交易方向（如 `"BUY"` / `"SELL"`）
  - `price` (`float`)：成交价格
  - `qty` (`int`)：成交数量
  - `strategy` (`str`)：策略名称
  - `note` (`str`)：备注，默认空字符串
  - `dt` (`datetime.datetime | str | None`)：时间戳。实盘默认现在；回测应传入当时时间。接受 `datetime.datetime` / `YYYY-MM-DD HH:MM:SS` 字符串
- **写入列**：`datetime, code, name, action, price, qty, amount, strategy, note`（`amount = price * qty`）

#### `get_last_equity()`

获取最后一条净值记录。

```python
def get_last_equity(self)
```

- **返回值**：`dict | None`。最后一条净值记录（`DictReader` 行），文件不存在或为空返回 `None`

#### 示例

```python
# 在 on_eod 中记录净值
def on_eod(self, now):
    total = self.get_total_equity(now)
    cash = self.get_cash()
    stock = self.get_stock_value(now)
    positions = len(self.state.get("positions", {}))
    self.tracker.record_equity(
        total_equity=total, cash=cash, stock_value=stock,
        positions=positions, date=now,
    )
```

---

## 8. CLI 命令行工具

`quantseed` 命令行入口提供环境检查、策略运行、数据同步、回测四个子命令。

### `quantseed --version`

显示版本号。

```bash
quantseed --version
# 或
quantseed -V
```

### `quantseed check`

检查运行环境，包括 Python 依赖、数据源、策略目录、QMT 配置。

```bash
quantseed check [--verbose]
```

- **参数**：
  - `--verbose`, `-v`：详细输出（拉取股票代码数量等）
- **检查项**：
  1. Python 依赖（pandas、numpy 必装；akshare、tushare、pytest 可选）
  2. 数据源（SQLite / Tushare / AkShare）
  3. 策略目录（`strategies/` 下含 `strategy.py` 的子目录）
  4. QMT 交易配置（`QMT_USERDATA_PATH`）

### `quantseed run`

启动策略调度器，自动发现 `strategies/` 下的策略并按时间点触发钩子。

```bash
quantseed run [--once]
```

- **参数**：
  - `--once`：只执行一次当前时间点的钩子然后退出（调试用）

### `quantseed sync`

触发数据同步。

```bash
quantseed sync [--full]
```

- **参数**：
  - `--full`：全量同步（默认增量）
- **行为**：
  - SQLite：提示通过 QMT xtdata 同步
  - Tushare / AkShare：测试连接并报告可用股票数量（按需拉取，无需预同步）

### `quantseed backtest`

回测策略。

```bash
quantseed backtest <strategy_dir> [--data PATH] [--start DATE] [--end DATE] [--capital N] [--warmup N]
```

- **位置参数**：
  - `strategy_dir`：策略目录路径（需含 `strategy.py` + `config.json`）
- **可选参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--data` | `str` | `<strategy_dir>/data/demo.db` | SQLite 数据库路径 |
| `--start` | `str` | `2024-01-01` | 回测开始日期（`YYYY-MM-DD`） |
| `--end` | `str` | `2024-12-31` | 回测结束日期（`YYYY-MM-DD`） |
| `--capital` | `float` | `100000.0` | 初始资金 |
| `--warmup` | `int` | `long_window + 5` | 预热天数；未指定时取策略 `long_window` 属性 + 5，无该属性则用 20+5 |

- **流程**：
  1. 动态导入 `strategy.py`，查找 `BaseStrategy` 子类
  2. 校验数据库存在
  3. 调用 `Backtester.clean_artifacts` 清理上次回测产物
  4. 初始化策略与 `SQLiteProvider`
  5. 执行回测，打印净值曲线（首尾各 5 天）与交易明细

#### 示例

```bash
# 基本回测
quantseed backtest strategies/my_strategy

# 指定数据源与回测区间
quantseed backtest strategies/my_strategy \
  --data data/custom.db \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --capital 200000 \
  --warmup 30
```
