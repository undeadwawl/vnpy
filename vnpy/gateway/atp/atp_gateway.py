"""
"""

import sys
import pytz
from datetime import datetime
from time import sleep
from typing import Dict

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
from vnpy.trader.utility import get_folder_path, load_json
from vnpy.trader.event import EVENT_TIMER

from .libatptradeapi_py import ATPTradeHandler, ATPTradeAPI
import .ama


CHINA_TZ = pytz.timezone("Asia/Shanghai")


EXCHANGE_VT2ATP = {
    Exchange.SSE: 101,
    Exchange.SZSE: 102
}
EXCHANGE_ATP2VT = {v: k for k, v in EXCHANGE_VT2ATP.items()}

DIRECTION_VT2ATP = {
    Direction.LONG: "1",
    Direction.SHORT: "2"
}
DIRECTION_ATP2VT = {v: k for k, v in DIRECTION_VT2ATP.items()}

OFFSET_VT2ATP = {
    Offset.OPEN: "O",
    Offset.CLOSE: "C"
}
OFFSET_ATP2VT = {v: k for k, v in OFFSET_VT2ATP.items()}

ORDERTYPE_VT2ATP = {
    OrderType.LIMIT: "a",
    OrderType.MARKET: "f"
}
ORDERTYPE_ATP2VT = {v: k for k, v in ORDERTYPE_VT2ATP.items()}

OPTIONTYPE_ATP2VT = {
    1: OptionType.CALL,
    -1: OptionType.PUT
}

STATUS_ATP2VT = {
    "0": Status.SUBMITTING,
    "1": Status.PARTTRADED,
    "2": Status.ALLTRADED,
    "3": Status.CANCELLED,
    "4": Status.CANCELLED,
    "5": Status.CANCELLED,
    "8": Status.REJECTED,
    "9": Status.SUBMITTING,
    "10": Status.SUBMITTING,
    "11": Status.NOTTRADED,
    "12": Status.PARTTRADED,
}


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


class AtpMdApi(ama.IAMDSpi):
    """"""

    def __init__(self, gateway: AtpGateway) -> None:
        """Constructor"""
        super().__init__()

    def OnMDSnapshot(self, snapshot, cnt):
        try:
            for i in range(cnt):
                data = ama.Tools_GetDataByIndex(snapshot, i)
                bidPrice1 = ama.Tools_GetInt64DataByIndex(data.bid_price, 0)
                offerPrice1 = ama.Tools_GetInt64DataByIndex(data.offer_price, 0)
                print("OnMDSnapshot====== security_code = %s, orig_time = %d, bid_price1 = %d, offer_price1 = %d" % (data.security_code, data.orig_time, bidPrice1, offerPrice1))
        except Exception as error:
            print("OnMDSnapshot")
            print(error)
            pass

        ama.Tools_FreeMemory(snapshot)

    def connect(self, address: str, userid: str, password: str) -> None:
        """"""
        cfg = ama.Cfg()
        cfg.min_log_level = ama.LogLevel.kInfo
        cfg.polling = False
        cfg.queue_size = 8192
        cfg.is_thread_safe = False
        cfg.ha_mode = ama.HighAvailableMode.kRegularDataFilter
        cfg.keep_order = False
        cfg.username = userid
        cfg.password = password
        cfg.is_subscribe_full = False
        cfg.channel_mode = ama.ChannelMode.kTCP
        cfg.ex_cfg_cnt = 0
        cfg.ums_server_cnt = 1

        ip, port = address.split(":")
        item = ama.UMSItem()
        item.server_ip = ip
        item.server_port = port
        ama.Tools_SetUMSServers(cfg.ums_servers, 0, item)

        return ama.IAMDApi_Init(self, cfg)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        item = ama.Tools_CreateSubscribeItem(1)

        if req.exchange == Exchange.SSE:
            item.market = ama.MarketType.kSZSE
        else:
            item.market = ama.MarketType.kSSE

        item.flag = ama.SubscribeDataType.kNone
        item.security_code = req.symbol

        ama.IAMDApi_SubscribeData(ama.SubscribeType.kSet, item, 1)
        ama.Tools_DestroySubscribeItem(item)

    def close(self) -> None:
        """"""
        ama.IAMDApi_Release()


class AtpTdApi(ATPTradeHandler):
    """"""

    # ATP API对象只需初始化一次
    ATPTradeAPI.Init()

    def __init__(self, gateway: AtpGateway) -> None:
        """Constructor"""
        super().__init__()

        self.gateway: AtpGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.api: ATPTradeAPI = ATPTradeAPI()
        self.seq_id: int = 0

        self.cust_id: int = 0
        self.account_id: int = 0
        self.branch_id: int = 0
        self.fund_id: int = 0

        self.local_id: int = 0
        self.local_sys_map: Dict[str, int] = {}
        self.sys_local_map: Dict[int, str] = {}

    def OnClosed(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器连接已关闭，原因：{reason}")

    def OnConnected(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器连接成功")

    def OnLogout(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器登出，原因：{reason}")

    def OnLogin(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器登录，原因：{reason}")
        self.login()

    def OnEndOfConnection(self, reason: str) -> None:
        """"""
        pass

    def OnConnectFailure(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器连接失败，原因：{reason}")

    def OnConnectTimeOut(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器连接超时，原因：{reason}")

    def OnHeartbeatTimeout(self, reason: str) -> None:
        """"""
        self.gateway.write_log(f"交易服务器心跳超时，原因：{reason}")

    def OnError(self, reason: str) -> None:
        """"""
        pass

    def OnLog(self, level: int, reason: str) -> None:
        """"""
        print("log", level, reason)

    def OnRspOrderStatusInternalAck(self, data: dict) -> None:
        """"""
        local_id: str = data["user_info"]
        sys_id: int = data["cl_ord_no"]

        if local_id:
            orderid = local_id
            self.local_sys_map[local_id] = sys_id
            self.sys_local_map[sys_id] = local_id
        else:
            orderid = str(sys_id)

        order = OrderData(
            symbol=data["security_id"],
            exchange=EXCHANGE_ATP2VT[data["market_id"]],
            orderid=orderid,
            type=ORDERTYPE_ATP2VT[data["order_type"]],
            direction=DIRECTION_ATP2VT[data["side"]],
            offset=OFFSET_ATP2VT[data["position_effect"]],
            price=data["price"] / 10000,
            volume=data["order_qty"] / 100,
            traded=data["cum_qty"] / 100,
            status=STATUS_ATP2VT[data["ord_status"]],
            datetime=datetime.strptime(str(data["transact_time"]), "%Y%m%d%H%M%S"),
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)

    def OnRspOrderStatusAck(self, data: dict) -> None:
        """"""
        local_id: str = data["user_info"]
        sys_id: int = data["cl_ord_no"]

        if local_id:
            orderid = local_id
            self.local_sys_map[local_id] = sys_id
            self.sys_local_map[sys_id] = local_id
        else:
            orderid = str(sys_id)

        order = OrderData(
            symbol=data["security_id"],
            exchange=EXCHANGE_ATP2VT[data["market_id"]],
            orderid=orderid,
            type=ORDERTYPE_ATP2VT[data["order_type"]],
            direction=DIRECTION_ATP2VT[data["side"]],
            offset=OFFSET_ATP2VT[data["position_effect"]],
            price=data["price"] / 10000,
            volume=data["order_qty"] / 100,
            traded=data["cum_qty"] / 100,
            status=STATUS_ATP2VT[data["ord_status"]],
            datetime=datetime.strptime(str(data["transact_time"]), "%Y%m%d%H%M%S"),
            gateway_name=self.gateway_name
        )
        self.gateway.on_order(order)

    def OnRspOptionAuctionTradeER(self, data: dict) -> None:
        """"""
        local_id: str = data["user_info"]
        sys_id: int = data["cl_ord_no"]

        if local_id:
            orderid = local_id
        else:
            orderid = str(sys_id)

        trade = TradeData(
            symbol=data["security_id"],
            exchange=EXCHANGE_ATP2VT[data["market_id"]],
            orderid=orderid,
            tradeid=data["exec_id"],
            direction=DIRECTION_ATP2VT[data["side"]],
            offset=OFFSET_ATP2VT[data["position_effect"]],
            price=data["last_px"] / 10000,
            volume=data["last_qty"] / 100,
            gateway_name=self.gateway_name
        )
        self.gateway.on_trade(trade)

    def OnRspCustLoginResp(self, data: dict) -> None:
        """"""
        self.cust_id = data["cust_id"]
        print(data)

        self.gateway.write_log("交易服务器账户登录成功")
        self.query_contract()

    def OnRspExternalQueryOptionSecurityInfoMsg(self, data: dict) -> None:
        """"""
        print(data)

        contract = ContractData(
            symbol=data["security_id"],
            exchange=EXCHANGE_ATP2VT[data["market_id"]],
            name=data["contract_symbol"],
            size=data["buy_qty_unit"],
            pricetick=data["price_tick"],
            min_volume=1,
            gateway_name=self.gateway_name
        )

        contract.option_strike = data["exercise_price"]
        contract.option_underlying = (
            data["underlying_security"]
            + "-"
            + str(data["last_trade_day"])[:6]
        )
        contract.option_type = OPTIONTYPE_ATP2VT[data["call_or_put"]]
        contract.option_expiry = datetime.strptime(str(data["last_trade_day"]), "%Y%m%d")
        contract.option_portfolio = data["underlying_security"]+ "_O"
        contract.option_index = get_option_index(contract.option_strike, contract.name)

        self.gateway.on_contract(contract)

    def OnRspAccountContractFundQueryResult(self, data: dict) -> None:
        """"""
        account = AccountData(
            accountid=data["fund_account_id"],
            balance=data["total_amt"] / 10000,
            frozen=data["frozen_amt"] / 10000,
            gateway_name=self.gateway_name
        )
        self.gateway.on_account(account)

    def OnRspAccountContractShareQueryResult(self, data: dict) -> None:
        """"""
        for d in data["contract_array"]:
            position = PositionData(
                symbol=d["security_id"],
                exchange=EXCHANGE_ATP2VT[d["market_id"]],
                direction=DIRECTION_ATP2VT[d["position_side"]],
                volume=d["total_position_value"] / 100,
                frozen=(d["total_position_value"] - d["position_value"]) / 100,
                profit=d["profit"] / 10000,
                gateway_name=self.gateway_name
            )
            self.gateway.on_position(position)

    def connect(self, address: str, userid: str, password: str) -> None:
        """"""
        self.address = address
        self.userid = userid
        self.password = password

        property = {
            "user": userid,
            "password": password,
            "locations": [address],
            "heartbeat_interval_milli": 5000,
            "connect_timeout_milli": 5000,
            "reconnect_time": 10,
            "client_name": "vn.py",
            "client_version": "v2.0",
            "mode": 0,
            "report_sync": {}
        }

        result = self.api.Connect(property, self)
        print(result)

    def login(self) -> None:
        """"""
        self.seq_id += 1

        req = {
            "client_seq_id": self.seq_id,
            "cust_id": self.userid,
            "password": self.password,
            "login_mode": 1,
        }
        self.api.ReqCustLoginOther(req)

    def send_order(self, req: OrderRequest) -> str:
        """"""
        self.local_id += 1
        orderid = str(self.local_id)

        req = self.new_req()
        req["security_id"] = req.symbol
        req["market_id"] = EXCHANGE_VT2ATP[req.exchange]
        req["side"] = DIRECTION_VT2ATP[req.direction]
        req["order_qty"] = req.volume
        req["price"] = int(req.price * 10000)
        req["order_type"] = ORDERTYPE_VT2ATP[req.type]
        req["position_effect"] = OFFSET_VT2ATP[req.offset]
        req["covered_or_uncovered"] = 1
        req["user_info"] = orderid
        self.api.ReqOptionAuctionOrder(req)

        order = req.create_order_data(self.gateway_name, orderid)
        self.gateway.on_order(order)

        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        sys_id = self.local_sys_map.get(req.orderid, None)
        if not sys_id:
            return

        req = self.new_req()
        req["orig_cl_ord_no"] = sys_id
        self.api.ReqOptionCancelOrder(req)

    def query_account(self) -> None:
        """"""
        req = self.new_req()
        req["security_id"] = ""
        req["market_id"] = 0
        self.api.ReqAccountContractFundQuery(req)

    def query_position(self) -> None:
        """"""
        req = self.new_req()
        req["security_id"] = ""
        req["market_id"] = 0
        self.api.ReqAccountContractShareQuery(req)

    def query_contract(self) -> None:
        """"""
        req = self.new_req()
        req["security_id"] = ""
        req["market_id"] = 0
        self.api.ReqExternalQueryOptionSecurityInfoMsg(req)

    def close(self) -> None:
        """"""
        self.api.Close()

    def new_req(self) -> dict:
        """"""
        self.seq_id += 1

        req = {
            "cust_id": self.cust_id,
            "account_id": self.account_id,
            "branch_id": self.branch_id,
            "fund_account_id": self.fund_id,
            "client_seq_id": self.seq_id,
        }
        return req


def get_option_index(strike_price: float, exchange_instrument_id: str) -> str:
    """"""
    exchange_instrument_id = exchange_instrument_id.replace(" ", "")

    if "M" in exchange_instrument_id:
        n = exchange_instrument_id.index("M")
    elif "A" in exchange_instrument_id:
        n = exchange_instrument_id.index("A")
    elif "B" in exchange_instrument_id:
        n = exchange_instrument_id.index("B")
    else:
        return str(strike_price)

    index = exchange_instrument_id[n:]
    option_index = f"{strike_price:.3f}-{index}"

    return option_index
