"""命令行入口。"""
import argparse
import importlib
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="quantseed",
        description="QuantSeed - 量化策略从零到一启动包",
    )
    parser.add_argument("--version", "-V", action="store_true", help="显示版本号")
    sub = parser.add_subparsers(dest="command")

    # quantseed run
    run = sub.add_parser("run", help="启动策略调度器")
    run.add_argument("--once", action="store_true",
                     help="只执行一次当前时间点的钩子然后退出（调试用）")

    # quantseed check
    check = sub.add_parser("check", help="检查运行环境")
    check.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # quantseed sync
    sync = sub.add_parser("sync", help="同步数据（QMT）")
    sync.add_argument("--full", action="store_true", help="全量同步（默认增量）")

    # quantseed backtest
    bt = sub.add_parser("backtest", help="回测策略")
    bt.add_argument("strategy_dir", help="策略目录路径（含 strategy.py + config.json）")
    bt.add_argument("--data", help="SQLite 数据库路径（默认用策略目录下的 data/demo.db）")
    bt.add_argument("--start", default="2024-01-01", help="回测开始日期 (YYYY-MM-DD)")
    bt.add_argument("--end", default="2024-12-31", help="回测结束日期 (YYYY-MM-DD)")
    bt.add_argument("--capital", type=float, default=100000.0, help="初始资金")
    bt.add_argument("--warmup", type=int, default=None,
                    help="预热天数（默认用策略 config 的 long_window+5）")

    args = parser.parse_args()

    if args.version:
        from quantseed import __version__
        print(f"quantseed {__version__}")
        return

    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        _cmd_run(args.once)
    elif args.command == "check":
        _cmd_check(args.verbose)
    elif args.command == "sync":
        _cmd_sync(args.full)
    elif args.command == "backtest":
        _cmd_backtest(args)


def _cmd_run(once=False):
    """启动策略调度器。"""
    from quantseed.scheduler import Scheduler

    sched = Scheduler()
    sched.auto_discover()

    if not sched.strategies:
        print("未发现任何策略，请在 strategies/ 目录下创建策略。")
        print("示例：")
        print("  cp -r examples/demo_strategy/ strategies/      # 最小示例（买入持有+止损）")
        print("  cp -r examples/dual_ma_strategy/ strategies/   # 双均线策略（含信号/仓位管理）")
        return

    sched.run(once=once)


def _cmd_check(verbose=False):
    """检查运行环境。"""
    from quantseed import __version__

    print(f"QuantSeed v{__version__} 环境检查")
    print("=" * 50)

    all_ok = True

    # 1. Python 依赖检查
    print("\n[1] Python 依赖")
    deps = [
        ("pandas", "pandas", "核心依赖（必装）"),
        ("numpy", "numpy", "核心依赖（必装）"),
        ("akshare", None, "AkShare 数据源（可选）"),
        ("tushare", None, "Tushare 数据源（可选）"),
        ("pytest", None, "测试工具（可选，开发用）"),
    ]
    for import_name, _, desc in deps:
        try:
            importlib.import_module(import_name)
            print(f"  [OK]   {import_name:<12} {desc}")
        except ImportError:
            optional = import_name in ("akshare", "tushare", "pytest")
            mark = "[WARN] " if optional else "[FAIL] "
            if not optional:
                all_ok = False
            print(f"  {mark}{import_name:<12} {desc} - 未安装")

    # 2. 数据源
    print("\n[2] 数据源")
    from quantseed.config import DATA_PROVIDER, SQLITE_DB_PATH, TUSHARE_TOKEN
    from quantseed.config import get_data_provider

    print(f"  当前数据源: {DATA_PROVIDER}")

    try:
        data = get_data_provider()
        if DATA_PROVIDER == "sqlite":
            from quantseed.data.sqlite_provider import SQLiteProvider
            if isinstance(data, SQLiteProvider):
                codes = data.get_all_codes()
                if codes:
                    print(f"  [OK]   SQLite: {SQLITE_DB_PATH} - {len(codes)} 只股票")
                else:
                    print(f"  [WARN] SQLite: {SQLITE_DB_PATH} - 数据库为空，请运行 quantseed sync")
                    all_ok = False
        elif DATA_PROVIDER == "tushare":
            if TUSHARE_TOKEN:
                if verbose:
                    codes = data.get_all_codes()
                    print(f"  [OK]   Tushare: Token 已设置，可获取 {len(codes)} 只股票")
                else:
                    print(f"  [OK]   Tushare: Token 已设置")
            else:
                print(f"  [FAIL] Tushare: Token 未设置 (TUSHARE_TOKEN)")
                all_ok = False
        elif DATA_PROVIDER == "akshare":
            if verbose:
                codes = data.get_all_codes()
                print(f"  [OK]   AkShare: 免费数据源，可获取 {len(codes)} 只股票")
            else:
                print(f"  [OK]   AkShare: 免费数据源，就绪")
    except Exception as e:
        print(f"  [FAIL] 数据源异常: {e}")
        all_ok = False

    # 3. 策略目录
    print("\n[3] 策略目录")
    from quantseed.config import STRATEGIES_DIR
    print(f"  路径: {STRATEGIES_DIR}")
    if STRATEGIES_DIR.exists():
        strategies = [d.name for d in STRATEGIES_DIR.iterdir() if d.is_dir() and (d / "strategy.py").exists()]
        if strategies:
            print(f"  [OK]   已发现策略: {', '.join(strategies)}")
        else:
            print(f"  [WARN] 策略目录为空（复制 examples/ 下的策略到此）")
    else:
        print(f"  [WARN] 策略目录不存在（运行 quantseed run 会自动创建）")

    # 4. QMT 交易
    print("\n[4] QMT 交易")
    from quantseed.config import QMT_USERDATA_PATH
    if QMT_USERDATA_PATH:
        print(f"  [OK]   QMT: {QMT_USERDATA_PATH}")
    else:
        print(f"  [INFO] QMT: 未配置（QMT_USERDATA_PATH 为空，仅回测/模拟可用）")

    # 5. 总结
    print("\n" + "=" * 50)
    if all_ok:
        print("环境检查通过，可以运行 quantseed run")
    else:
        print("环境检查发现问题，请修复 [FAIL] 项后重试")


def _cmd_sync(full=False):
    """触发数据同步。"""
    from quantseed.config import DATA_PROVIDER, get_data_provider

    print(f"数据同步: 当前数据源 = {DATA_PROVIDER}")

    if DATA_PROVIDER == "sqlite":
        print("SQLite 数据源通过 QMT xtdata 同步，请在 QMT 中执行数据下载。")
        print("导出路径: 请设置 QMT_DATA_PATH 环境变量指向数据库文件。")
    elif DATA_PROVIDER == "tushare":
        try:
            data = get_data_provider()
            codes = data.get_all_codes()
            print(f"Tushare 连接成功，可用 {len(codes)} 只股票。")
            print("数据按需拉取，无需预同步。")
        except Exception as e:
            print(f"Tushare 连接失败: {e}")
    elif DATA_PROVIDER == "akshare":
        try:
            data = get_data_provider()
            codes = data.get_all_codes()
            print(f"AkShare 连接成功，可用 {len(codes)} 只股票。")
            print("数据按需拉取，无需预同步。")
        except Exception as e:
            print(f"AkShare 连接失败: {e}")
    else:
        print(f"未知数据源: {DATA_PROVIDER}")


def _cmd_backtest(args):
    """回测策略。"""
    import datetime
    import importlib.util
    import sys as _sys
    from pathlib import Path

    from quantseed.data.sqlite_provider import SQLiteProvider
    from quantseed.backtest import Backtester, BacktestConfig
    from quantseed.strategy_base import BaseStrategy

    strategy_dir = Path(args.strategy_dir).resolve()
    if not (strategy_dir / "strategy.py").exists():
        print(f"错误: {strategy_dir}/strategy.py 不存在")
        _sys.exit(1)

    # 动态导入策略
    spec = importlib.util.spec_from_file_location(
        f"bt_strategy.{strategy_dir.name}.strategy",
        str(strategy_dir / "strategy.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    # 找到策略类
    strategy_class = None
    for name in dir(mod):
        obj = getattr(mod, name, None)
        if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
            strategy_class = obj
            break

    if strategy_class is None:
        print(f"错误: {strategy_dir}/strategy.py 中未找到 BaseStrategy 子类")
        _sys.exit(1)

    # 确定数据源
    db_path = Path(args.data) if args.data else strategy_dir / "data" / "demo.db"
    if not db_path.exists():
        print(f"错误: 数据库不存在: {db_path}")
        print(f"请先准备数据，或用 --data 指定 SQLite 数据库路径")
        _sys.exit(1)

    data = SQLiteProvider(str(db_path))

    # 用临时运行目录，避免污染策略源码目录
    run_dir = strategy_dir / "run"
    run_dir.mkdir(exist_ok=True)
    Backtester.clean_artifacts(run_dir)

    # 初始化策略（指向 run 目录）
    strategy = strategy_class(run_dir)

    # 确定 warmup
    warmup = args.warmup
    if warmup is None:
        # 默认用策略的 long_window + 5
        long_window = getattr(strategy, "long_window", 20)
        warmup = long_window + 5

    config = BacktestConfig(
        start_date=args.start,
        end_date=args.end,
        initial_capital=args.capital,
        warmup_days=warmup,
    )

    bt = Backtester(strategy, data, config)
    result = bt.run()

    # 打印净值曲线（首尾各 5 天）
    print("=== 净值曲线（首尾各 5 天）===")
    eq = result.equity_curve
    if len(eq) <= 10:
        print(eq.to_string(index=False))
    else:
        print(eq.head(5).to_string(index=False))
        print("  ...")
        print(eq.tail(5).to_string(index=False))
    print()

    # 打印交易明细
    if not result.trades.empty:
        print("=== 交易明细 ===")
        print(result.trades.to_string(index=False))

    # 打印净值曲线图
    print("\n=== 净值曲线 ===")
    print(result.equity_chart())


if __name__ == "__main__":
    main()
