"""双均线策略的离线回测驱动脚本。

模拟 scheduler 在历史交易日上逐日触发 on_open / on_close / on_eod，
让策略在 SQLite 测试数据上"跑回测"，验证：
1. 策略逻辑是否正确（信号、下单、持仓）
2. 框架是否支持离线回测（不依赖实时时钟）
3. 暴露框架的不足（为后续回测引擎设计提供输入）

用法:
    python examples/dual_ma_strategy/run_backtest.py
"""
import sys
import datetime
from pathlib import Path

# 把项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantseed.data.sqlite_provider import SQLiteProvider
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
    # 清理上次的 state/equity/trades
    for f in ["state.json", "equity.csv", "trades.csv"]:
        p = strategy_dir / f
        if p.exists():
            p.unlink()

    strategy = DualMAStrategy(strategy_dir)
    strategy.data = data  # 手动注入（绕过 scheduler）

    print(f"=== 双均线策略回测 ===")
    print(f"股票池: {strategy.universe}")
    print(f"参数: MA{strategy.short_window}/MA{strategy.long_window}, "
          f"最大持仓 {strategy.max_positions}, 仓位 {strategy.position_pct:.0%}")
    print()

    # 3. 获取交易日历，逐日触发
    calendar = data.get_trade_calendar("2024-01-01", "2024-12-31")
    if not calendar:
        print("交易日历为空")
        return

    # 跳过前 long_window 天（均线还没形成）
    warmup_days = strategy.long_window + 5
    trading_days = calendar[warmup_days:]
    print(f"回测区间: {trading_days[0]} ~ {trading_days[-1]} "
          f"({len(trading_days)} 个交易日，前 {warmup_days} 天预热)")
    print()

    for i, date_str in enumerate(trading_days, 1):
        # 模拟 scheduler 的三个时间点
        dt_open = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=9, minute=25)
        dt_close = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=14, minute=45)
        dt_eod = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=15, minute=5)

        print(f"[Day {i:02d} {date_str}]")

        # on_open: 执行卖出
        strategy.on_open(dt_open)

        # on_close: 扫描信号 + 执行买入
        strategy.on_close(dt_close)
        strategy._execute_buys(dt_close)  # 框架没有 on_close 后的买入钩子，手动调

        # on_eod: 记录净值
        strategy.on_eod(dt_eod)

        positions = strategy.state.get("positions", {})
        cash = strategy.state.get("cash", 0.0)
        print(f"  状态: 持仓 {len(positions)} 只, 现金 {cash:.2f}")
        print()

    # 4. 输出回测结果
    print("=" * 50)
    print("回测结果:")
    initial = strategy.state.get("initial_capital", 100000.0)
    final_cash = strategy.state.get("cash", 0.0)
    positions = strategy.state.get("positions", {})
    stock_value = 0.0
    for code, pos in positions.items():
        price = data.get_latest_price(code)
        stock_value += price * pos.get("qty", 0)
    final_equity = final_cash + stock_value
    pnl = final_equity - initial
    pnl_pct = pnl / initial * 100

    print(f"  初始资金: {initial:.2f}")
    print(f"  最终净值: {final_equity:.2f}")
    print(f"  盈亏: {pnl:+.2f} ({pnl_pct:+.2f}%)")
    print(f"  剩余持仓: {len(positions)} 只")
    print()

    # 读取 trades.csv 统计交易次数
    trades_path = strategy_dir / "trades.csv"
    if trades_path.exists():
        with open(trades_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        trade_count = len(lines) - 1  # 减去表头
        print(f"  总交易次数: {trade_count}")

    # 读取 equity.csv 显示净值曲线
    equity_path = strategy_dir / "equity.csv"
    if equity_path.exists():
        with open(equity_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print(f"  净值记录: {len(lines) - 1} 天")


if __name__ == "__main__":
    main()
