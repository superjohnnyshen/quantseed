"""Mini QMT 交易接口封装。

封装 xtquant 的下单 / 撤单 / 查询持仓与资产。
所有策略共享同一 trader 实例。需要在 Mini QMT 客户端运行的环境中使用。

注意：此模块是可选的，仅 QMT 用户需要。
"""
import logging
from quantseed.config import QMT_USERDATA_PATH, QMT_SESSION_ID

logger = logging.getLogger(__name__)


class TradingAPI:
    """封装 XtQuantTrader 的下单接口。

    - connect() 建立连接
    - order_buy/order_sell 下单
    - cancel_order 撤单
    - query_positions/query_asset 查询

    使用前需要 Mini QMT 客户端正在运行。
    """

    def __init__(self):
        self.xt_trader = None
        self.account = None
        self._connected = False

    def connect(self, account_id=None):
        """建立 QMT 连接。"""
        try:
            from xtquant.xttrader import XtQuantTrader
        except ImportError:
            logger.warning("xtquant 未安装，QMT 交易不可用。pip install quantseed[qmt]")
            return False

        try:
            self.xt_trader = XtQuantTrader(QMT_USERDATA_PATH, QMT_SESSION_ID)
            self.xt_trader.start()
            connect_result = self.xt_trader.connect()
            if connect_result == 0:
                self.account = account_id or self._subscribe_account()
                if self.account is None:
                    logger.error("订阅账户失败，QMT 交易不可用")
                    self._connected = False
                    return False
                self._connected = True
                return True
            return False
        except Exception as e:
            logger.error("QMT 连接失败: %s", e)
            self._connected = False
            return False

    def _subscribe_account(self):
        """订阅账户。"""
        try:
            from xtquant.xttype import StockAccount
            acc = StockAccount("")
            self.xt_trader.subscribe(acc)
            return acc
        except Exception as e:
            logger.warning("订阅账户失败: %s", e)
            return None

    @property
    def is_connected(self):
        return self._connected

    def order_buy(self, code, price, qty, strategy="quantseed"):
        """限价买入。返回 (order_id, error_msg)。"""
        if not self._connected:
            return None, "not connected"
        try:
            from xtquant import xtconstant
            order_id = self.xt_trader.order_stock(
                self.account, code, xtconstant.STOCK_BUY,
                qty, xtconstant.FIX_PRICE, price, strategy, "",
            )
            return order_id, None
        except Exception as e:
            logger.error("买入下单失败 %s: %s", code, e)
            return None, str(e)

    def order_sell(self, code, price, qty, strategy="quantseed"):
        """限价卖出。"""
        if not self._connected:
            return None, "not connected"
        try:
            from xtquant import xtconstant
            order_id = self.xt_trader.order_stock(
                self.account, code, xtconstant.STOCK_SELL,
                qty, xtconstant.FIX_PRICE, price, strategy, "",
            )
            return order_id, None
        except Exception as e:
            logger.error("卖出下单失败 %s: %s", code, e)
            return None, str(e)

    def cancel_order(self, order_id):
        """撤单。"""
        try:
            return self.xt_trader.cancel_order_stock(self.account, order_id)
        except Exception as e:
            logger.warning("撤单失败 %s: %s", order_id, e)
            return None

    def query_positions(self):
        """查询当前持仓。"""
        if not self._connected:
            return []
        try:
            return self.xt_trader.query_stock_positions(self.account)
        except Exception as e:
            logger.warning("查询持仓失败: %s", e)
            return []

    def query_asset(self):
        """查询账户资产。"""
        if not self._connected:
            return None
        try:
            return self.xt_trader.query_stock_asset(self.account)
        except Exception as e:
            logger.warning("查询资产失败: %s", e)
            return None


# 全局共享的交易 API 实例
trader = TradingAPI()