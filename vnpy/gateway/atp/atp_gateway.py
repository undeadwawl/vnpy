"""
"""

import sys
import pytz
from datetime import datetime
from time import sleep

from vnpy.trader.constant import (
    Direction,
    Offset,
    Exchange,
    OrderType,
    Product,
    Status,
    OptionType
)
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    AccountData,
    ContractData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
)
from vnpy.trader.utility import get_folder_path
from vnpy.trader.event import EVENT_TIMER


CHINA_TZ = pytz.timezone("Asia/Shanghai")


class AtpGateway(BaseGateway):
    """"""

    default_setting = {
        "用户名": "",
        "密码": "",
        "交易服务器": "",
        "行情服务器": ""
    }

    exchanges = [Exchange.SSE, Exchange.SZSE]

    def __init__(self, event_engine):
        """Constructor"""
        super().__init__(event_engine, "ATP")

        self.td_api = AtpTdApi(self)
        self.md_api = AtpMdApi(self)

    def connect(self, setting: dict):
        """"""
        userid = setting["用户名"]
        password = setting["密码"]
        td_address = setting["交易服务器"]
        md_address = setting["行情服务器"]

        self.td_api.connect(td_address, userid, password)
        self.md_api.connect(md_address, userid, password)

        self.init_query()

    def subscribe(self, req: SubscribeRequest):
        """"""
        self.md_api.subscribe(req)

    def send_order(self, req: OrderRequest):
        """"""
        return self.td_api.send_order(req)

    def cancel_order(self, req: CancelRequest):
        """"""
        self.td_api.cancel_order(req)

    def query_account(self):
        """"""
        self.td_api.query_account()

    def query_position(self):
        """"""
        self.td_api.query_position()

    def close(self):
        """"""
        self.td_api.close()
        self.md_api.close()

    def write_error(self, msg: str, error: dict):
        """"""
        error_id = error["ErrorID"]
        error_msg = error["ErrorMsg"]
        msg = f"{msg}，代码：{error_id}，信息：{error_msg}"
        self.write_log(msg)

    def process_timer_event(self, event):
        """"""
        self.count += 1
        if self.count < 2:
            return
        self.count = 0

        func = self.query_functions.pop(0)
        func()
        self.query_functions.append(func)

        self.md_api.update_date()

    def init_query(self):
        """"""
        self.count = 0
        self.query_functions = [self.query_account, self.query_position]
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)


class AtpMdApi:
    """"""

    def __init__(self, gateway: AtpGateway) -> None:
        """Constructor"""
        super().__init__()

    def connect(self, address: str, userid: str, password: str) -> None:
        """"""
        pass

    def login(self) -> None:
        """"""
        pass

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        pass

    def close(self) -> None:
        """"""
        pass


class AtpTdApi:
    """"""

    def __init__(self, gateway: AtpGateway) -> None:
        """Constructor"""
        super().__init__()

    def OnClosed(self, reason: str) -> None:
        """"""
        pass

    def OnConnected(self, reason: str) -> None:
        """"""
        pass

    def OnLogout(self, reason: str) -> None:
        """"""
        pass

    def OnLogin(self, reason: str) -> None:
        """"""
        pass

    def OnEndOfConnection(self, reason: str) -> None:
        """"""
        pass

    def OnConnectFailure(self, reason: str) -> None:
        """"""
        pass

    def OnConnectTimeOut(self, reason: str) -> None:
        """"""
        pass

    def OnHeartbeatTimeout(self, reason: str) -> None:
        """"""
        pass

    def OnError(self, reason: str) -> None:
        """"""
        pass

    def OnLog(self, level: int, reason: str) -> None:
        """"""
        pass

    def OnRspOrderStatusInternalAck(self, data: dict) -> None:
        """"""
        pass

    def OnRspOrderStatusAck(self, data: dict) -> None:
        """"""
        pass

    def OnRspCashAuctionTradeER(self, data: dict) -> None:
        """"""
        pass

    def OnRspOrderQueryResult(self, data: dict) -> None:
        """"""
        pass

    def OnRspCustLoginResp(self, data: dict) -> None:
        """"""
        pass

    def OnRspCustLogoutResp(self, data: dict) -> None:
        """"""
        pass

    def OnRspCustPasswdModifyResult(self, data: dict) -> None:
        """"""
        pass

    def OnRspQueryContractSpecificationsQueryResult(self, data: dict) -> None:
        """"""
        pass

    def OnRspTradeOrderQueryResult(self, data: dict) -> None:
        """"""
        pass

    def connect(self, address: str, userid: str, password: str) -> None:
        """"""
        pass

    def login(self):
        """"""
        pass

    def send_order(self, req: OrderRequest) -> str:
        """"""
        pass

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        pass

    def query_account(self) -> None:
        """"""
        pass

    def query_position(self) -> None:
        """"""
        pass

    def close(self) -> None:
        """"""
        pass
