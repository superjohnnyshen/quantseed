"""命令行入口。"""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="quantseed",
        description="QuantSeed - 量化策略从零到一启动包",
    )
    sub = parser.add_subparsers(dest="command")

    # quantseed run
    sub.add_parser("run", help="启动策略调度器")

    # quantseed check
    check = sub.add_parser("check", help="检查运行环境")
    check.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    # quantseed sync
    sync = sub.add_parser("sync", help="同步数据（QMT）")
    sync.add_argument("--full", action="store_true", help="全量同步（默认增量）")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        _cmd_run()
    elif args.command == "check":
        _cmd_check(args.verbose)
    elif args.command == "sync":
        _cmd_sync(args.full)


def _cmd_run():
    """启动策略调度器。"""
    from quantseed.scheduler import Scheduler

    sched = Scheduler()
    sched.auto_discover()

    if not sched.strategies:
        print("未发现任何策略，请在 strategies/ 目录下创建策略。")
        print("示例: 将 examples/demo_strategy/ 复制到 strategies/")
        return

    sched.run()


def _cmd_check(verbose=False):
    """检查运行环境。"""
    print("QuantSeed 环境检查")
    print("=" * 40)

    # 数据源
    from quantseed.config import DATA_PROVIDER, SQLITE_DB_PATH, TUSHARE_TOKEN
    from quantseed.config import get_data_provider

    print(f"数据源: {DATA_PROVIDER}")

    try:
        data = get_data_provider()
        if DATA_PROVIDER == "sqlite":
            from quantseed.data.sqlite_provider import SQLiteProvider
            if isinstance(data, SQLiteProvider):
                codes = data.get_all_codes()
                if codes:
                    print(f"  SQLite: {SQLITE_DB_PATH} - 数据正常，{len(codes)} 只股票")
                else:
                    print(f"  SQLite: {SQLITE_DB_PATH} - 数据库为空，请运行 quantseed sync")
        elif DATA_PROVIDER == "tushare":
            if TUSHARE_TOKEN:
                codes = data.get_all_codes()
                print(f"  Tushare: Token 已设置，可获取 {len(codes)} 只股票")
            else:
                print("  Tushare: Token 未设置")
        elif DATA_PROVIDER == "akshare":
            if verbose:
                codes = data.get_all_codes()
                print(f"  AkShare: 免费数据源，可获取 {len(codes)} 只股票")
            else:
                print("  AkShare: 免费数据源，就绪")
    except Exception as e:
        print(f"  数据源异常: {e}")

    # 策略目录
    from quantseed.config import STRATEGIES_DIR
    print(f"策略目录: {STRATEGIES_DIR}")
    if STRATEGIES_DIR.exists():
        strategies = [d.name for d in STRATEGIES_DIR.iterdir() if d.is_dir()]
        if strategies:
            print(f"  已发现策略: {', '.join(strategies)}")
        else:
            print("  策略目录为空")
    else:
        print("  策略目录不存在")

    # QMT 交易
    from quantseed.config import QMT_USERDATA_PATH
    if QMT_USERDATA_PATH:
        print(f"QMT: {QMT_USERDATA_PATH}")
    else:
        print("QMT: 未配置（QMT_USERDATA_PATH 为空）")


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


if __name__ == "__main__":
    main()