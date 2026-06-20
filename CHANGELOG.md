# Changelog

本文件记录 QuantSeed 的版本变更。版本号遵循 [Semantic Versioning](https://semver.org/)。

## [0.1.6] - 2026-06-21

### 新增
- **回测引擎** `quantseed/backtest/`：在历史交易日上驱动策略执行，镜像 scheduler 流程
  - `Backtester` 类：注入数据源 + 逐日触发 on_open/on_close/on_eod
  - `BacktestConfig`：支持 warmup 预热天数
  - `BacktestResult`：返回净值曲线、交易明细、绩效指标
  - `metrics.py`：总收益率、年化收益率、最大回撤、夏普比率
- `EquityTracker.record_equity/record_trade` 支持传入 `date`/`dt` 参数（实盘默认今天，回测可指定）
- `DataProvider.get_price_on_date(code, date)` 接口（v0.1.5 引入，此处补全文档）
- 29 个新单元测试覆盖回测引擎 + 绩效指标（总计 90 个测试）

### 修复
- **策略实盘买入 bug**：`DualMAStrategy.on_close` 之前只扫描信号不执行买入，scheduler 跑起来永远不会建仓。现在 `on_close` 内自动调用 `_execute_buys`
- **回测日期 bug**：`EquityTracker` 之前用 `datetime.today()` 写入日期，回测时 equity.csv 全是今天的日期。现在支持传入历史日期
- **Windows 文件锁 bug**：`StateStore.save` 在 OneDrive/杀软锁文件时偶发 `PermissionError`，加 5 次重试
- **pandas 2.x FutureWarning**：`SQLiteProvider` 拼接空 DataFrame 触发警告，过滤后再 concat
- **信号丢失 bug**：策略 `pending_signals` 之前每日覆盖，未执行的旧信号会丢。改为合并更新
- **pnl_daily 计算错误**：之前用 `total_equity - initial_capital`（累计盈亏），改为 `total_equity - last_equity`（真正的日盈亏）

### 重构
- `examples/dual_ma_strategy/run_backtest.py` 改用 `Backtester` 引擎，从 125 行简化到 65 行

### 验证
- 双均线策略回测：35 个交易日，1 次买入，最终净值 100875 (+0.88%)，夏普 1.814，最大回撤 -0.68%

## [0.1.5] - 2026-06-20

### 新增
- 双均线策略示例 `examples/dual_ma_strategy/`
  - `strategy.py`：MA5 上穿 MA20 买入，下穿卖出，含止损/仓位管理
  - `config.json`：参数化配置
  - `prepare_data.py`：生成 SQLite 测试数据（5 只股票 × 60 天）
  - `run_backtest.py`：离线回测驱动脚本
- `DataProvider.get_price_on_date(code, date)` 接口：回测场景取历史当日价
- 单元测试套件（61 个测试）：覆盖 EquityTracker、StateStore、SQLiteProvider、config

### 修复
- `StateStore.save` 在 Windows 下 `tmp.replace()` 偶发 PermissionError，加 5 次重试
- 策略 `pending_signals` 改为合并而非覆盖
- 策略 `pnl_daily` 改为真正的日盈亏
- `SQLiteProvider` 修复 pandas 2.x FutureWarning

## [0.1.4] - 2026-06-19

### 新增
- `quantseed-sop` TRAE Skill：把 SOP 方法论封装成 IDE 可调用的 Skill
- 数据源说明文档 `docs/data-sources.md`：AkShare/Tushare/QMT 的注册方式、积分权限、限流规避

## [0.1.3] - 2026-06-19

### 修复
- `SQLiteProvider._normalize_codes` 处理 6 位代码 zfill
- `SQLiteProvider._chunked` 分块查询避免 SQLITE_MAX_VARIABLE_NUMBER 限制

## [0.1.2] - 2026-06-18

### 新增
- `SQLiteProvider`：支持 QMT SQLite 数据库
- `DataProvider` 抽象接口

## [0.1.1] - 2026-06-18

### 新增
- `AkShareProvider`、`TushareProvider` 数据源
- `Scheduler` 主循环调度器
- `BaseStrategy` 策略基类，三钩子模型（on_open/on_close/on_eod）
- `StateStore` 状态持久化（崩溃恢复）
- `EquityTracker` 净值/交易日志
- `TradingAPI` QMT 交易封装
- `quantseed` CLI 命令行入口

## [0.1.0] - 2026-06-17

### 首次发布
- 项目骨架
- SOP.md 方法论（V3.1）
- README.md
