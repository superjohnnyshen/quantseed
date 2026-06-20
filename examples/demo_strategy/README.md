# 演示策略：买入持有 + 止损

quantseed 最简单的可运行策略，用于验证框架是否正常工作。

## 快速开始

```bash
# 1. 准备测试数据（复用 dual_ma 的数据）
python examples/demo_strategy/prepare_data.py

# 2. 一键回测
quantseed backtest examples/demo_strategy/
```

## 策略逻辑

- **on_open (09:25)**：检查止损（亏损超 10% 卖出）
- **on_close (14:45)**：首次建仓（用 80% 资金买入股票池第一只）
- **on_eod (15:05)**：记录当日净值

## 文件说明

| 文件 | 说明 |
|------|------|
| `strategy.py` | 策略实现（~100 行，适合作为新策略模板） |
| `config.json` | 参数配置（股票池/仓位比例/止损线） |
| `prepare_data.py` | 复用 dual_ma_strategy 的测试数据 |

## 参数说明（config.json）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `universe` | `["000001", "601318", "300750"]` | 股票池（第一只为建仓标的） |
| `buy_pct` | 0.8 | 建仓用资金比例 |
| `stop_loss_pct` | -0.10 | 止损线（-10%） |

## 作为新策略模板

复制本目录，修改 `strategy.py` 的三个钩子逻辑即可：

```bash
cp -r examples/demo_strategy/ strategies/my_strategy
# 编辑 strategies/my_strategy/strategy.py
quantseed run --once  # 调试
```
