"""pytest 共享 fixture。"""
import sys
from pathlib import Path

import pytest

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def tmp_strategy_dir(tmp_path: Path) -> Path:
    """临时策略目录，含 equity.csv / trades.csv / state.json 路径。"""
    d = tmp_path / "my_strategy"
    d.mkdir()
    return d
