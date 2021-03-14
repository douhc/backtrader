#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import time
from datetime import datetime, timedelta

from backtrader.feed import DataBase
from backtrader import TimeFrame, date2num, num2date
from backtrader.utils.py3 import (integer_types, queue, string_types,
                                  with_metaclass)
from backtrader.metabase import MetaParams
from backtrader.ctp import ctpstore

from .object import TickData

class MetaCtpData(DataBase.__class__):
    def __init__(cls, name, bases, dct):
        '''Class has already been created ... register'''
        # Initialize the class
        super(MetaCtpData, cls).__init__(name, bases, dct)

        # Register with the store
        ctpstore.CtpStore.DataCls = cls


class CtpData(with_metaclass(MetaCtpData, DataBase)):
    '''Ctp Data Feed.

    Params:

      - ``qcheck`` (default: ``0.5``)

        Time in seconds to wake up if no data is received to give a chance to
        resample/replay packets properly and pass notifications up the chain

      - ``historical`` (default: ``False``)

        If set to ``True`` the data feed will stop after doing the first
        download of data.

        The standard data feed parameters ``fromdate`` and ``todate`` will be
        used as reference.

        The data feed will make multiple requests if the requested duration is
        larger than the one allowed by IB given the timeframe/compression
        chosen for the data.

      - ``backfill_start`` (default: ``True``)

        Perform backfilling at the start. The maximum possible historical data
        will be fetched in a single request.

      - ``backfill`` (default: ``True``)

        Perform backfilling after a disconnection/reconnection cycle. The gap
        duration will be used to download the smallest possible amount of data

      - ``backfill_from`` (default: ``None``)

        An additional data source can be passed to do an initial layer of
        backfilling. Once the data source is depleted and if requested,
        backfilling from IB will take place. This is ideally meant to backfill
        from already stored sources like a file on disk, but not limited to.

      - ``bidask`` (default: ``True``)

        If ``True``, then the historical/backfilling requests will request
        bid/ask prices from the server

        If ``False``, then *midpoint* will be requested

      - ``useask`` (default: ``False``)

        If ``True`` the *ask* part of the *bidask* prices will be used instead
        of the default use of *bid*

      - ``includeFirst`` (default: ``True``)

        Influence the delivery of the 1st bar of a historical/backfilling
        request by setting the parameter directly to the Ctp API calls

      - ``reconnect`` (default: ``True``)

        Reconnect when network connection is down

      - ``reconnections`` (default: ``-1``)

        Number of times to attempt reconnections: ``-1`` means forever

      - ``reconntimeout`` (default: ``5.0``)

        Time in seconds to wait in between reconnection attemps

    This data feed supports only this mapping of ``timeframe`` and
    ``compression``, which comply with the definitions in the CTP API
    Developer's Guid::

        (TimeFrame.Seconds, 5): 'S5',
        (TimeFrame.Seconds, 10): 'S10',
        (TimeFrame.Seconds, 15): 'S15',
        (TimeFrame.Seconds, 30): 'S30',
        (TimeFrame.Minutes, 1): 'M1',
        (TimeFrame.Minutes, 2): 'M3',
        (TimeFrame.Minutes, 3): 'M3',
        (TimeFrame.Minutes, 4): 'M4',
        (TimeFrame.Minutes, 5): 'M5',
        (TimeFrame.Minutes, 10): 'M10',
        (TimeFrame.Minutes, 15): 'M15',
        (TimeFrame.Minutes, 30): 'M30',
        (TimeFrame.Minutes, 60): 'H1',
        (TimeFrame.Minutes, 120): 'H2',
        (TimeFrame.Minutes, 180): 'H3',
        (TimeFrame.Minutes, 240): 'H4',
        (TimeFrame.Minutes, 360): 'H6',
        (TimeFrame.Minutes, 480): 'H8',
        (TimeFrame.Days, 1): 'D',
        (TimeFrame.Weeks, 1): 'W',
        (TimeFrame.Months, 1): 'M',

    Any other combination will be rejected
    '''
    params = (
        ('qcheck', 0.5),
        ('historical', False),  # do backfilling at the start
        ('backfill_start', True),  # do backfilling at the start
        ('backfill', True),  # do backfilling when reconnecting
        ('backfill_from', None),  # additional data source to do backfill from
        ('bidask', True),
        ('useask', False),
        ('includeFirst', True),
        ('reconnect', True),
        ('reconnections', -1),  # forever
        ('reconntimeout', 5.0),
    )

    _store = ctpstore.CtpStore

    # States for the Finite State Machine in _load
    _ST_FROM, _ST_START, _ST_LIVE, _ST_HISTORBACK, _ST_OVER = range(5)

    _TOFFSET = timedelta()

    def _timeoffset(self):
        # Effective way to overcome the non-notification?
        return self._TOFFSET

    def islive(self):
        '''Returns ``True`` to notify ``Cerebro`` that preloading and runonce
        should be deactivated'''
        return True

    def __init__(self, **kwargs):
        self.o = self._store(**kwargs)
        self._candleFormat = 'bidask' if self.p.bidask else 'midpoint'
        self.qlive = queue.Queue()

    def setenvironment(self, env):
        '''Receives an environment (cerebro) and passes it over to the store it
        belongs to'''
        super(CtpData, self).setenvironment(env)
        env.addstore(self.o)

    def start(self):
        '''Starts the Ctp connecction and gets the real contract and
        contractdetails if it exists'''
        super(CtpData, self).start()

        # Create attributes as soon as possible
        self._statelivereconn = False  # if reconnecting in live state
        self._storedmsg = dict()  # keep pending live message (under None)
        self._state = self._ST_OVER

        # Kickstart store and get queue to wait on
        self.o.start(data=self)

        # check if the granularity is supported
        otf = self.o.get_granularity(self._timeframe, self._compression)
        if otf is None:
            self.put_notification(self.NOTSUPPORTED_TF)
            self._state = self._ST_OVER
            return
        try_count = 5
        while try_count > 0:
            self.contractdetails = cd = self.o.get_instrument(self.p.dataname)
            if cd:
                break
            try_count -= 1
            print('Can not get instrument detail. try again...')
            time.sleep(1)

        if self.contractdetails is None:
            print(f"*******Can not get instrument {self.p.dataname} detail info")
        else:
            print(f"----- Get instrument: {self.p.dataname} detail info: {self.contractdetails} ----------")
        self._start_finish()
        self._state = self._ST_START  # initial state for _load
        self._st_start()

        self._reconns = 0

    def _st_start(self, instart=True, tmout=None):
        self.o.subscribe(self.p.dataname)
        self._state = self._ST_LIVE
        if instart:
            self._reconns = self.p.reconnections

        return True  # no return before - implicit continue

    def stop(self):
        '''Stops and tells the store to stop'''
        super(CtpData, self).stop()
        self.o.stop()

    def haslivedata(self):
        return bool(self._storedmsg or self.qlive)  # do not return the objs

    def on_tick(self, tick: TickData):
        self.qlive.put(tick)

    def _load(self):
        if self._state == self._ST_OVER:
            return False

        while True:
            if self._state == self._ST_LIVE:
                last_msg: TickData = self._storedmsg.get(None)
                if last_msg != None:
                    print(f'[ctpfeed] last msg: {last_msg.datetime}, instrument: {last_msg.symbol} status: {self._state}')
                try:
                    msg = self.qlive.get(timeout=self._qcheck)
                except queue.Empty:
                    self.put_notification(self.CONNBROKEN)
                    # Try to reconnect
                    if not self.p.reconnect or self._reconns == 0:
                        # Can no longer reconnect
                        self.put_notification(self.DISCONNECTED)
                        self._state = self._ST_OVER
                        return False  # failed

                    self._reconns -= 1
                    self._st_start(instart=False, tmout=self.p.reconntimeout)
                    continue

                self._reconns = self.p.reconnections
                self._storedmsg[None] = msg  # keep the msg
                self._load_tick(msg)

    def _load_tick(self, tick: TickData):
        dt = date2num(tick.datetime)
        if dt <= self.lines.datetime[-1]:
            return False  # time already seen

        # Common fields
        self.lines.datetime[0] = dt

        # Put the prices into the bar
        price = float(tick.ask_price_1) if self.p.useask else float(tick.bid_price_1)
        self.lines.open[0] = price
        self.lines.high[0] = price
        self.lines.low[0] = price
        self.lines.close[0] = price
        self.lines.volume[0] = tick.volume
        self.lines.openinterest[0] = tick.open_interest

        return True

    def _load_history(self, msg):
        # TODO
        return True
