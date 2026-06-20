import os
from pathlib import Path


DATA_PROVIDER = os.getenv("QUANTSEED_DATA_PROVIDER", "akshare").lower()
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
QMT_DATA_PATH = os.getenv("QMT_DATA_PATH", "quantseed_data.db")

# QMT 交易相关配置
QMT_USERDATA_PATH = os.getenv("QMT_USERDATA_PATH", "")

try:
    QMT_SESSION_ID = int(os.getenv("QMT_SESSION_ID", "0"))
except ValueError:
    QMT_SESSION_ID = 0

# 兼容旧变量名
SQLITE_DB_PATH = QMT_DATA_PATH

STRATEGIES_DIR = Path(os.getenv("QUANTSEED_STRATEGIES_DIR", "strategies"))
LOG_DIR = Path(os.getenv("QUANTSEED_LOG_DIR", "logs"))
OUTPUT_DIR = Path(os.getenv("QUANTSEED_OUTPUT_DIR", "output"))


def get_data_provider():
    provider_type = DATA_PROVIDER

    if provider_type == "tushare":
        from .data.tushare_provider import TushareProvider
        if not TUSHARE_TOKEN:
            raise ValueError("Tushare token not set. Please set TUSHARE_TOKEN environment variable.")
        return TushareProvider(TUSHARE_TOKEN)
    
    elif provider_type == "sqlite":
        from .data.sqlite_provider import SQLiteProvider
        return SQLiteProvider(QMT_DATA_PATH)
    
    elif provider_type == "akshare":
        from .data.akshare_provider import AkShareProvider
        return AkShareProvider()
    
    else:
        raise ValueError(f"Unknown data provider: {provider_type}. Choose from: akshare, tushare, sqlite")