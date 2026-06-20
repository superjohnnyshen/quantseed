"""临时冒烟测试：直接调用 demo 策略的三个钩子，验证修复后的代码链路。"""
import datetime
import sys
from pathlib import Path

# 确保导入项目根目录
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from quantseed.config import get_data_provider, STRATEGIES_DIR
from quantseed.scheduler import _import_strategy, _find_strategy_class


def main():
    demo_dir = ROOT / "examples" / "demo_strategy"
    print(f"[smoke] 加载策略: {demo_dir}")
    mod = _import_strategy(demo_dir)
    cls = _find_strategy_class(mod)
    if not cls:
        print("[smoke] 未找到策略类")
        return 1
    strategy = cls(demo_dir)
    print(f"[smoke] 策略实例: {strategy.name}")

    print("[smoke] 初始化数据源 ...")
    try:
        data = get_data_provider()
    except Exception as e:
        print(f"[smoke] 数据源初始化失败: {e}")
        return 1
    strategy.data = data
    print(f"[smoke] 数据源: {type(data).__name__}")

    now = datetime.datetime.now()

    print("\n[smoke] === on_open ===")
    try:
        strategy.on_open(now)
    except Exception as e:
        print(f"[smoke] on_open 异常: {e}")

    print("\n[smoke] === on_close ===")
    try:
        strategy.on_close(now)
    except Exception as e:
        print(f"[smoke] on_close 异常: {e}")

    print("\n[smoke] === on_eod ===")
    try:
        strategy.on_eod(now)
    except Exception as e:
        print(f"[smoke] on_eod 异常: {e}")

    print("\n[smoke] 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
