"""准备 demo 策略的测试数据。

复用 dual_ma_strategy 的数据生成逻辑，生成 SQLite 数据库。
如已存在 dual_ma 的数据，可直接复用，无需重新生成。

用法:
    python examples/demo_strategy/prepare_data.py
    # 生成 examples/demo_strategy/data/demo.db

    # 或直接复用 dual_ma 的数据（推荐）:
    quantseed backtest examples/demo_strategy/ --data examples/dual_ma_strategy/data/demo.db
"""
import shutil
import sys
from pathlib import Path

# 复用 dual_ma 的数据生成
DUAL_MA_DATA = Path(__file__).resolve().parent.parent / "dual_ma_strategy" / "data" / "demo.db"
TARGET = Path(__file__).parent / "data" / "demo.db"


def main():
    if DUAL_MA_DATA.exists():
        # 复用 dual_ma 的数据
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DUAL_MA_DATA, TARGET)
        print(f"已复用 dual_ma_strategy 的数据: {TARGET}")
        print(f"  (源: {DUAL_MA_DATA})")
        return

    # dual_ma 数据不存在，先运行 dual_ma 的 prepare_data
    print("dual_ma_strategy 的数据不存在，先运行其 prepare_data.py...")
    dual_ma_prepare = Path(__file__).resolve().parent.parent / "dual_ma_strategy" / "prepare_data.py"
    import subprocess
    result = subprocess.run([sys.executable, str(dual_ma_prepare)])
    if result.returncode != 0:
        print("生成数据失败")
        sys.exit(1)
    # 复制过来
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DUAL_MA_DATA, TARGET)
    print(f"数据已生成并复制: {TARGET}")


if __name__ == "__main__":
    main()
