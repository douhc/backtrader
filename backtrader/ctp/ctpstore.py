#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from backtrader.ctp.ctpbroker import CtpBroker

import collections
from datetime import datetime, timedelta
import time as _time
import json
import threading

import backtrader as bt
from backtrader.metabase import MetaParams
from backtrader.utils.py3 import queue, with_metaclass
from backtrader.utils import AutoDict
from backtrader.order import Order

from backtrader.ctp.ctp_gateway import CtpTdApi, CtpMdApi
from .object import *
from .constant import *


class MetaSingleton(MetaParams):
    '''Metaclass to make a metaclassed class a singleton'''
    def __init__(cls, name, bases, dct):
        super(MetaSingleton, cls).__init__(name, bases, dct)
        cls._singleton = None

    def __call__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = (
                super(MetaSingleton, cls).__call__(*args, **kwargs))

        return cls._singleton


class CtpStore(with_metaclass(MetaSingleton, object)):
    '''Singleton class wrapping to control the connections to Ctp.

    Params:

      - ``userid``: 用户名
      - ``password``: 密码
      - ``brokerid``: 经纪商代码
      - ``td_address``: 交易服务器
      - ``md_address``: 行情服务器
      - ``appid``: 产品名称
      - ``auth_code``: 授权编码
      - ``product_info``: 产品信息
      - ``practice`` (default: ``False``): use the test environment

    '''

    BrokerCls = None  # broker class will autoregister
    DataCls = None  # data class will auto register

    params = (
        ('userid', ''),
        ('password', ''),
        ('brokerid', ''),
        ('td_address', ''),
        ('md_address', ''),
        ('appid', ''),
        ('auth_code', ''),
        ('product_info', ''),
        ('practice', False),
    )

    _DTEPOCH = datetime(1970, 1, 1)
    _ENVPRACTICE = 'practice'
    _ENVLIVE = 'live'

    @classmethod
    def getdata(cls, *args, **kwargs):
        '''Returns ``DataCls`` with args, kwargs'''
        return cls.DataCls(*args, **kwargs)

    @classmethod
    def getbroker(cls, *args, **kwargs):
        '''Returns broker with *args, **kwargs from registered ``BrokerCls``'''
        return cls.BrokerCls(*args, **kwargs)

    def __init__(self):
        super(CtpStore, self).__init__()

        self.notifs = collections.deque()  # store notifications for cerebro

        self._env = None  # reference to cerebro for general notifications
        self.broker: CtpBroker = None  # broker instance
        # key: dataname, val: feed
        self.datas = collections.OrderedDict()  # datas that have registered over start

        # self._orders = collections.OrderedDict()  # map order.ref to oid
        self._ordersrev = collections.OrderedDict()  # map oid to order.ref
        self._oenv = self._ENVPRACTICE if self.p.practice else self._ENVLIVE
        # 合约信息: inst -> ContractData
        self._contracts = collections.OrderedDict()
        # 仓位信息
        self._positions = collections.OrderedDict()

        self._cash = 0.0
        self._value = 0.0

        # Setup Api
        self.mdapi = CtpMdApi(self)
        self.mdapi.connect(self.p.md_address, self.p.userid, self.p.password, self.p.brokerid)
        self.tdapi = CtpTdApi(self)
        self.tdapi.connect(self.p.td_address, self.p.userid, self.p.password, self.p.brokerid, self.p.auth_code, self.p.appid, self.p.product_info)

        trynum = 5
        while trynum > 0:
            if self.tdapi.login_status and self.mdapi.login_status:
                print("TD & MD server both login success!")
                break
            else:
                print(f"MD login status: {self.mdapi.login_status}, TD login status: {self.tdapi.login_status}")
                _time.sleep(0.5)
                trynum -= 1
        
        # 查询账号信息
        if self.tdapi.login_status:
            self.tdapi.query_account()

    def start(self, data=None, broker=None):
        # Datas require some processing to kickstart data reception
        if data is None and broker is None:
            self.cash = None
            return

        if data is not None:
            self._env = data._env
            # For datas simulate a queue with None to kickstart co
            self.datas[data.p.dataname] = data

            if self.broker is not None:
                self.broker.data_started(data)

        elif broker is not None:
            self.broker = broker

    def stop(self):
        pass

    def put_notification(self, msg, *args, **kwargs):
        self.notifs.append((msg, args, kwargs))

    def get_notifications(self):
        '''Return the pending "store" notifications'''
        self.notifs.append(None)  # put a mark / threads could still append
        return [x for x in iter(self.notifs.popleft, None)]

    # Ctp supported granularities
    _GRANULARITIES = {
        (bt.TimeFrame.Ticks, 1): 'TICK',
        (bt.TimeFrame.Seconds, 1): 'S1',
        (bt.TimeFrame.Seconds, 5): 'S5',
        (bt.TimeFrame.Seconds, 10): 'S10',
        (bt.TimeFrame.Seconds, 15): 'S15',
        (bt.TimeFrame.Seconds, 30): 'S30',
        (bt.TimeFrame.Minutes, 1): 'M1',
        (bt.TimeFrame.Minutes, 2): 'M3',
        (bt.TimeFrame.Minutes, 3): 'M3',
        (bt.TimeFrame.Minutes, 4): 'M4',
        (bt.TimeFrame.Minutes, 5): 'M5',
        (bt.TimeFrame.Minutes, 10): 'M5',
        (bt.TimeFrame.Minutes, 15): 'M5',
        (bt.TimeFrame.Minutes, 30): 'M5',
        (bt.TimeFrame.Minutes, 60): 'H1',
        (bt.TimeFrame.Minutes, 120): 'H2',
        (bt.TimeFrame.Minutes, 180): 'H3',
        (bt.TimeFrame.Minutes, 240): 'H4',
        (bt.TimeFrame.Minutes, 360): 'H6',
        (bt.TimeFrame.Minutes, 480): 'H8',
        (bt.TimeFrame.Days, 1): 'D',
        (bt.TimeFrame.Weeks, 1): 'W',
        (bt.TimeFrame.Months, 1): 'M',
    }

    def on_tick(self, tick: TickData):
        print(f"[on_tick] dataname: {tick.symbol}")
        data = self.datas.get(tick.symbol)
        if data != None:
            data.on_tick(tick)

    def on_account(self, account: AccountData):
        self._cash = account.available
        self._value = account.balance
        print(f"[on_account] cash: {self._cash} value: {self._value}")

    def on_position(self, position: PositionData):
        key = f"{position.symbol, position.direction}"
        self._positions[key] = position
        print(f"[on_position] {key}")

    def on_contract(self, contract: ContractData):
        self._contracts[contract.symbol] = contract
        print(f"[on_contract] dataname: {contract.symbol}")

    def on_order(self, order: OrderData):
        print(f"[on_order] orderid: {order.vt_orderid} status: {order.status}")
        ord: Order = self._ordersrev[order.vt_orderid]
        oref = ord.ref
        if order.status == Status.REJECTED:
            self.broker._reject(oref)
        elif order.status == Status.SUBMITTING:
            self.broker._submit(oref)
        elif order.status == Status.CANCELLED:
            self.broker._cancel(oref)
        elif order.status == Status.PARTTRADED:
            # TODO
            # self.broker._fill(oref, order.traded, order.price)
            pass
        elif order.status == Status.ALLTRADED:
            # TODO
            # self.broker._fill(oref, order.traded, order.price)
            pass
        else:
            print(f"order status {order.status}")

    def on_trade(self, trade: TradeData):
        print(f"[on_trade] orderid:{trade.vt_orderid}, volume:{trade.volume}, price:{trade.price}")
        oref = self._ordersrev[trade.vt_orderid]        
        self.broker._fill(oref, trade.volume, trade.price)

    def subscribe(self, dataname):
        req = SubscribeRequest(
            symbol=dataname,
            exchange=Exchange.SHFE,
        )
        self.mdapi.subscribe(req)

    def get_positions(self):
        # 字段结构， key: ("ag2103", "多"), value: PositionData()
        return self._positions

    def get_granularity(self, timeframe, compression):
        return self._GRANULARITIES.get((timeframe, compression), None)

    def get_instrument(self, dataname):
        return self._contracts.get(dataname)

    def get_cash(self):
        return self._cash

    def get_value(self):
        return self._value

    def candles(self, dataname, dtbegin, dtend, timeframe, compression,
                candleFormat, includeFirst):
        # TODO
        return queue.Queue()

    _ORDEREXECS = {
        bt.Order.Market: OrderType.MARKET,
        bt.Order.Limit: OrderType.LIMIT,
        bt.Order.Stop: OrderType.STOP,
        bt.Order.StopLimit: OrderType.STOP
    }

    def order_create(self, order: Order, stopside=None, takeside=None, **kwargs):
        req = OrderRequest(
            symbol=order.data._dataname,
            direction= Direction.LONG if order.isbuy() else Direction.SHORT,
            exchange=Exchange.SHFE,
            type=self._ORDEREXECS[order.exectype],
            volume=abs(order.created.size),
            price=order.created.price,
        )
        oid = self.tdapi.send_order(req)
        order.addinfo(orderid=oid)
        self._ordersrev[oid] = order
        return order

    def order_cancel(self, order: Order):
        oid = order.info["orderid"]
        oid = oid[(len(self.mdapi.gateway_name)+1):]
        req = CancelRequest(
            orderid=oid,
            symbol=order.data._dataname,
            exchange=Exchange.SHFE,
        )
        self.tdapi.cancel_order(req)
        return order

