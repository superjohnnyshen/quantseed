# 双均线策略示例

MA5 上穿 MA20 买入，下穿卖出。这是 quantseed 框架的第一个完整策略示例。

## 快速开始

```bash
# 1. 生成测试数据（5 只股票 × 60 天，SQLite 数据库）
python examples/dual_ma_strategy/prepare_data.py

# 2. 一键回测
quantseed backtest examples/dual_ma_strategy/
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `strategy.py` | 策略实现（信号计算 + 仓位管理 + 止损） |
| `config.json` | 参数配置（均线周期/仓位比例/股票池） |
| `prepare_data.py` | 生成模拟测试数据 |
| `run_backtest.py` | Python API 回测脚本（CLI 的等价替代） |

## 策略逻辑

- **on_open (09:25)**：执行卖出信号（死叉）+ 止损（亏损超 8%）
- **on_close (14:45)**：扫描 MA 交叉信号 + 执行买入（金叉）
- **on_eod (15:05)**：记录当日净值

## 参数说明（config.json）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `short_window` | 5 | 短期均线周期 |
| `long_window` | 20 | 长期均线周期 |
| `max_positions` | 3 | 最大持仓数 |
| `position_pct` | 0.3 | 单只仓位占总资金比例 |
| `stop_loss_pct` | -0.08 | 止损线（-8%） |
| `universe` | 5 只蓝筹 | 股票池 |

## 自定义

修改 `config.json` 调整参数，或修改 `strategy.py` 改变策略逻辑。回测结果会输出到 `run/` 目录：
- `state.json` - 策略状态
- `equity.csv` - 净值曲线
- `trades.csv` - 交易明细
