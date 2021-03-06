#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import argparse
import logging
from logging.handlers import RotatingFileHandler

import sys

import time

from quant.datafeed import DataFeed
from quant.observers.t_bfx_lq_new import TriangleArbitrage as TriangleArbitrageBfxLq
from quant.observers.t_binance import TriangleArbitrage as TriangleArbitrageBinance
from quant.observers.t_lq_bn import TriangleArbitrage as TriangleArbitrageLqBn
from quant.observers.t_gate import TriangleArbitrage as TriangleArbitrageGate
from quant.observers.t_bitflyer import TriangleArbitrage as TriangleArbitrageBitflyer
from quant.observers.t_kraken import TriangleArbitrage as TriangleArbitrageKraken

from quant.observers.t_bfx_btc_usd import Arbitrage as ArbitrageBfxBtcUsd
from quant.observers.t_bfx_btc import Arbitrage as ArbitrageBfxBtc

from quant.brokers import broker_factory
from quant.snapshot import Snapshot


class CLI(object):
    def __init__(self):
        super(CLI, self).__init__()
        self.data_feed = None

    @classmethod
    def init_logger(cls, args):
        level = logging.INFO
        if args.verbose:
            level = logging.INFO
        if args.debug:
            level = logging.DEBUG

        logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                            level=level)
        if args.file:
            filename = args.file
            if '.log' not in filename:
                filename = filename + '.log'
            filename_logging = "log/" + filename
        else:
            filename_logging = "log/quant.log"

        rt_handler = RotatingFileHandler(filename_logging, maxBytes=100 * 1024 * 1024, backupCount=10)
        rt_handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)-12s [%(levelname)s] %(message)s')
        rt_handler.setFormatter(formatter)
        logging.getLogger('').addHandler(rt_handler)

        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def exec_command(self, args):
        logging.debug('exec_command:%s' % args)

        # if "replay-history" in args.command:
        #     self.create_arbitrer(args)
        #     self.arbitrer.replay_history(args.replay_history)
        #     return
        # if "get-balance" in args.command:
        #     self.get_balance(args)
        #     return
        # if "list-public-markets" in args.command:
        #     self.list_markets()
        #     return
        # if "get-broker-balance" in args.command:
        #     self.get_broker_balance(args)
        #     return
        # if "test_pub" in args.command:
        #     self.test_pub(args)
        #     return
        # if "test_pri" in args.command:
        #     self.test_pri(args)
        #     return

        # if "b-watch" in args.command:
        #     self.create_arbitrer(args)
        # else:
        #     self.create_datafeed(args)
        #
        #     # special tranglar observer
        #     if "t-watch-viabtc-bcc" in args.command:
        #         self.register_t_viabtc_bcc(args)
        #
        #     if "t-watch-binance-wtc" in args.command:
        #         self.register_t_binance_wtc(args)
        #
        #     if "t-watch-binance-bnb" in args.command:
        #         self.register_t_binance_bnb(args)
        #
        #     if "t-watch-binance-mco" in args.command:
        #         self.register_t_binance_mco(args)
        #
        #     if "t-watch-binance-qtum" in args.command:
        #         self.register_t_binance_qtum(args)

        if "get-balance" in args.command:
            self.get_balance(args)
            return

        if "b-watch" in args.command:
            pass
        else:
            self.create_data_feed(args)
            if "t-watch-bitfinex-liqui-usd-bch-btc" in args.command:
                self.register_t_bitfinex_liqui('USD', 'BCH', 'BTC')
            if "t-watch-liqui-bn-btc-bcc-eth" in args.command:
                self.register_t_liqui_binance('BTC', 'BCC', 'ETH')
            if "t-watch-binance-wtc" in args.command:
                self.register_t_binance_wtc(args)
            if "t-watch-binance-bnb" in args.command:
                self.register_t_binance_bnb(args)
            if "t-watch-binance-mco" in args.command:
                self.register_t_binance_mco(args)
            if "t-watch-binance-qtum" in args.command:
                self.register_t_binance_qtum(args)
            if "t-watch-binance-neo" in args.command:
                self.register_t_binance_neo(args)
            if "t-watch-bfx-btc-usd" in args.command:
                self.register_t_bitfinex_btc_usd(args)
            if "t-watch-bfx-btc" in args.command:
                self.register_t_bitfinex_btc(args)
            if "t-watch-gate-bcc" in args.command:
                self.register_t_gate(args)
            if "t-watch-bitflyer-bch" in args.command:
                self.register_t_bitflyer_bch(args)
            if "t-watch-bitflyer-eth" in args.command:
                self.register_t_bitflyer_eth(args)
            if "t-watch-kraken-bch" in args.command:
                self.register_t_kraken_bch(args)
            if "t-watch-kraken-eth" in args.command:
                self.register_t_kraken_eth(args)

        self.data_feed.run_loop()

    @classmethod
    def get_balance(cls, args):
        if not args.markets:
            logging.error("You must use --markets argument to specify markets")
            sys.exit(2)
        p_markets = args.markets.split(",")
        brokers = broker_factory.create_brokers(p_markets)

        snapshot = Snapshot()

        while True:
            total_btc = 0.
            total_bch = 0.
            total_eth = 0.
            total_zrx = 0.
            for market in brokers.values():
                market.get_balances()
                print(market)
                total_btc += market.btc_balance
                total_bch += market.bch_balance
                total_eth += market.eth_balance
                total_zrx += market.zrx_balance
                snapshot.snapshot_balance(market.name, market.btc_balance, market.bch_balance, market.eth_balance,
                                          market.zrx_balance)

            snapshot.snapshot_balance('ALL', total_btc, total_bch, total_eth, total_zrx)

            time.sleep(60 * 10)

    def register_t_binance_wtc(self, args):
        _observer = TriangleArbitrageBinance(base_pair='Binance_WTC_BTC',
                                             pair1='Binance_WTC_ETH',
                                             pair2='Binance_ETH_BTC',
                                             monitor_only=True)
        self.data_feed.register_observer(_observer)

    def register_t_binance_bnb(self, args):
        _observer = TriangleArbitrageBinance(base_pair='Binance_BNB_BTC',
                                             pair1='Binance_BNB_ETH',
                                             pair2='Binance_ETH_BTC',
                                             monitor_only=True)
        self.data_feed.register_observer(_observer)

    def register_t_binance_mco(self, args):
        _observer = TriangleArbitrageBinance(base_pair='Binance_MCO_BTC',
                                             pair1='Binance_MCO_ETH',
                                             pair2='Binance_ETH_BTC',
                                             monitor_only=True)
        self.data_feed.register_observer(_observer)

    def register_t_binance_qtum(self, args):
        _observer = TriangleArbitrageBinance(base_pair='Binance_QTUM_BTC',
                                             pair1='Binance_QTUM_ETH',
                                             pair2='Binance_ETH_BTC',
                                             monitor_only=True)
        self.data_feed.register_observer(_observer)

    def register_t_binance_neo(self, args):
        _observer = TriangleArbitrageBinance(base_pair='Binance_NEO_BTC',
                                             pair1='Binance_NEO_ETH',
                                             pair2='Binance_ETH_BTC',
                                             monitor_only=True)
        self.data_feed.register_observer(_observer)

    def register_t_bitfinex_liqui(self, base_currency, market_currency, mid_currency):
        base_pair = "Bitfinex_%s_%s" % (market_currency, base_currency)
        pair1 = "Liqui_%s_%s" % ('BCC' if market_currency == 'BCH' else market_currency, mid_currency)
        pair2 = "Bitfinex_%s_%s" % (mid_currency, base_currency)

        kwargs = {
            "precision": 8,
            "fee_base": 0.002,
            "fee_pair1": 0.0025,
            "fee_pair2": 0.002,
            "min_amount_market": 0.001,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.001,
        }

        _observer = TriangleArbitrageBfxLq(base_pair=base_pair,
                                           pair1=pair1,
                                           pair2=pair2,
                                           monitor_only=True,
                                           **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_liqui_binance(self, base_currency, market_currency, mid_currency):
        base_pair = "Liqui_%s_%s" % (market_currency, base_currency)
        pair1 = "Liqui_%s_%s" % (market_currency, mid_currency)
        pair2 = "Binance_%s_%s" % (mid_currency, base_currency)
        kwargs = {
            "precision": 8,
            "fee_base": 0.0025,
            "fee_pair1": 0.001,
            "fee_pair2": 0.001,
            "min_amount_market": 0.001,
            "min_amount_mid": 0.0001,
            "max_trade_amount": 5,
            "min_trade_amount": 0.001,
        }
        _observer = TriangleArbitrageLqBn(base_pair=base_pair,
                                          pair1=pair1,
                                          pair2=pair2,
                                          monitor_only=True,
                                          **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_bitfinex_btc_usd(self, args):
        _observer = ArbitrageBfxBtcUsd(monitor_only=False)
        self.data_feed.register_observer(_observer)

    def register_t_bitfinex_btc(self, args):
        _observer = ArbitrageBfxBtc(monitor_only=False)
        self.data_feed.register_observer(_observer)

    def register_t_gate(self, args):
        base_pair = "Bitfinex_BCH_USD"
        pair1 = "Gate_BCC_BTC"
        pair2 = "Bitfinex_BTC_USD"
        kwargs = {
            "precision": 2,
            "fee_base": 0.002,
            "fee_pair1": 0.002,
            "fee_pair2": 0.0015,
            "min_amount_market": 0.001,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.001,
        }
        _observer = TriangleArbitrageGate(base_pair=base_pair,
                                          pair1=pair1,
                                          pair2=pair2,
                                          monitor_only=True,
                                          **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_bitflyer_bch(self, args):
        base_pair = "Bitfinex_BCH_USD"
        pair1 = "Bitflyer_BCH_BTC"
        pair2 = "Bitflyer_BTC_JPY"
        kwargs = {
            "precision": 2,
            "fee_base": 0.002,
            "fee_pair1": 0.002,
            "fee_pair2": 0.0015,
            "min_amount_market": 0.005,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.001,
        }
        _observer = TriangleArbitrageBitflyer(base_pair=base_pair,
                                              pair1=pair1,
                                              pair2=pair2,
                                              monitor_only=True,
                                              **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_bitflyer_eth(self, args):
        base_pair = "Bitfinex_ETH_USD"
        pair1 = "Bitflyer_ETH_BTC"
        pair2 = "Bitflyer_BTC_JPY"
        kwargs = {
            "precision": 2,
            "fee_base": 0.002,
            "fee_pair1": 0.002,
            "fee_pair2": 0.002,
            "min_amount_market": 0.01,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.01,
        }
        _observer = TriangleArbitrageBitflyer(base_pair=base_pair,
                                              pair1=pair1,
                                              pair2=pair2,
                                              monitor_only=True,
                                              **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_kraken_bch(self, args):
        base_pair = "Kraken_BCH_USD"
        pair1 = "Bitfinex_BCH_BTC"
        pair2 = "Kraken_XBT_USD"
        kwargs = {
            "precision": 2,
            "fee_base": 0.0026,
            "fee_pair1": 0.002,
            "fee_pair2": 0.0026,
            "min_amount_market": 0.001,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.001,
        }
        _observer = TriangleArbitrageKraken(base_pair=base_pair,
                                            pair1=pair1,
                                            pair2=pair2,
                                            monitor_only=True,
                                            **kwargs)
        self.data_feed.register_observer(_observer)

    def register_t_kraken_eth(self, args):
        base_pair = "Kraken_ETH_USD"
        pair1 = "Bitfinex_ETH_BTC"
        pair2 = "Kraken_XBT_USD"
        kwargs = {
            "precision": 2,
            "fee_base": 0.0026,
            "fee_pair1": 0.002,
            "fee_pair2": 0.0026,
            "min_amount_market": 0.01,
            "min_amount_mid": 0.005,
            "max_trade_amount": 5,
            "min_trade_amount": 0.01,
        }
        _observer = TriangleArbitrageKraken(base_pair=base_pair,
                                            pair1=pair1,
                                            pair2=pair2,
                                            monitor_only=True,
                                            **kwargs)
        self.data_feed.register_observer(_observer)

    def create_data_feed(self, args):
        self.data_feed = DataFeed()
        self.init_observers_and_markets(args)

    def init_observers_and_markets(self, args):
        if args.observers:
            self.data_feed.init_observers(args.observers.split(","))
        if args.markets:
            self.data_feed.init_markets(args.markets.split(","))

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-f", "--file", type=str,
                            help="logging file name, example: -fbtc")
        parser.add_argument("-d", "--debug", help="debug verbose mode",
                            action="store_true")
        parser.add_argument("-v", "--verbose", help="info verbose mode",
                            action="store_true")
        parser.add_argument("-o", "--observers", type=str,
                            help="observers, example: -oLogger,Emailer")
        parser.add_argument("-m", "--markets", type=str,
                            help="markets, example: -mHaobtcCNY,Bitstamp")
        parser.add_argument("-s", "--status", help="status", action="store_true")
        parser.add_argument("command", nargs='*', default="watch",
                            help='verb: "watch|replay-history|get-balance|list-public-markets|get-broker-balance"')
        args = parser.parse_args()
        self.init_logger(args)
        self.exec_command(args)
        print('main end')
        exit(-1)


def main():
    cli = CLI()
    cli.main()


if __name__ == "__main__":
    main()
