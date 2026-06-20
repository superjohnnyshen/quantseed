"""双均线策略的离线回测脚本（使用 quantseed.backtest 引擎）。

用法:
    python examples/dual_ma_strategy/run_backtest.py
"""
import sys
from pathlib import Path

# 把项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantseed.data.sqlite_provider import SQLiteProvider
from quantseed.backtest import Backtester, BacktestConfig
from examples.dual_ma_strategy.strategy import DualMAStrategy


def main():
    # 1. 准备数据源
    db_path = Path(__file__).parent / "data" / "demo.db"
    if not db_path.exists():
        print(f"测试数据不存在: {db_path}")
        print("请先运行: python examples/dual_ma_strategy/prepare_data.py")
        return

    data = SQLiteProvider(str(db_path))

    # 2. 初始化策略（用临时目录避免污染 strategies/）
    strategy_dir = Path(__file__).parent / "run"
    strategy_dir.mkdir(exist_ok=True)
    # 清理上次回测产物，保证干净起点（必须在构造策略前调用）
    Backtester.clean_artifacts(strategy_dir)
    strategy = DualMAStrategy(strategy_dir)

    # 3. 配置回测
    config = BacktestConfig(
        start_date="2024-01-01",
        end_date="2024-12-31",
        initial_capital=100000.0,
        warmup_days=strategy.long_window + 5,  # 跳过均线预热期
    )

    # 4. 运行回测
    bt = Backtester(strategy, data, config)
    result = bt.run()

    # 5. 打印净值曲线（前 5 天 + 后 5 天）
    print("=== 净值曲线（首尾各 5 天）===")
    eq = result.equity_curve
    if len(eq) <= 10:
        print(eq.to_string(index=False))
    else:
        print(eq.head(5).to_string(index=False))
        print("  ...")
        print(eq.tail(5).to_string(index=False))
    print()

    # 6. 打印交易明细
    if not result.trades.empty:
        print("=== 交易明细 ===")
        print(result.trades.to_string(index=False))


if __name__ == "__main__":
    main()
