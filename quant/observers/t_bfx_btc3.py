#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from __future__ import division
import logging

import time

from .basicbot import BasicBot
from quant.brokers import broker_factory


class Arbitrage(BasicBot):
    """
    btc和bt1 bt2的合成与分解套利
    兑换比例1btc=1bt1+1bt2
    python -m quant.cli -mBitfinex_BTC_USD,Bitfinex_BT1_USD,Bitfinex_BT2_USD t-watch-bfx-btc -v
    """

    def __init__(self, monitor_only=False):
        super(Arbitrage, self).__init__()
        self.base_pair = "Bitfinex_BTC_USD"
        self.pair_1 = "Bitfinex_BT1_USD"
        self.pair_2 = "Bitfinex_BT2_USD"

        self.monitor_only = monitor_only
        self.precision = 2

        self.fee_base = 0.002
        self.fee_pair1 = 0.002
        self.fee_pair2 = 0.002
        """交易所限制的最小交易量，由交易所和币种共同决定"""
        self.min_amount_market = 0.005
        """单次交易的最大量和最小量"""
        self.max_trade_amount = 0.1
        self.min_trade_amount = 0.005

        # 赢利触发点，差价，百分比更靠谱?
        self.profit_trigger = 1.5
        self.last_trade = 0
        self.skip = False
        if not monitor_only:
            self.brokers = broker_factory.create_brokers([self.base_pair, self.pair_1, self.pair_2])

    def is_depths_available(self, depths):
        res = self.base_pair in depths and self.pair_1 in depths and self.pair_2 in depths
        if not res:
            return False
        pair1_bid_price = depths[self.pair_1]['bids'][0]['price']
        pair1_ask_price = depths[self.pair_1]['asks'][0]['price']
        if pair1_ask_price <= 0 or pair1_bid_price <= 0:
            return False

        pair2_bid_price = depths[self.pair_2]['bids'][0]['price']
        pair2_ask_price = depths[self.pair_2]['asks'][0]['price']
        if pair2_ask_price <= 0 or pair2_bid_price <= 0:
            return False

        return True

    def handle_order(self, depths):
        """处理历史订单，如果未成交，则cancel掉并重新下单"""
        if self.is_selling():
            orders_sell = self.get_orders("sell")
            for order in orders_sell:
                order_id = order['order_id']
                market = order['market']
                retry_count = 0
                while True:
                    order_status = self.brokers[market].get_order(order_id)
                    if order_status:
                        break
                    else:
                        if retry_count > 1:
                            break
                        retry_count += 1
                        time.sleep(0.5)
                if not order_status:
                    # 找了3次都找不到，就当不在了
                    self.remove_order(order_id)
                    continue

                if order_status['status'] == 'CLOSE' or order_status['status'] == 'CANCELED':
                    self.remove_order(order_id)
                    continue
                else:
                    # is pending order
                    remaining_amount = order_status['amount'] - order_status['deal_amount']
                    if remaining_amount <= self.min_amount_market:
                        # 未成交部分小于min_stock, 所以算完成了
                        self.remove_order(order_id)
                        continue
                    price_sell = depths[market]['bids'][0]['price']
                    if price_sell < 0.0:
                        # depth异常，直接return, 下次处理
                        continue
                    retry_count = 0
                    while True:
                        # 先cancel再下单
                        cancel_res = self.brokers[market].cancel_order(order_id)
                        if not cancel_res:
                            if retry_count > 1:
                                self.remove_order(order_id)
                                break
                            retry_count += 1
                            time.sleep(0.5)
                            continue

                        logging.info("handle_order======>cancel order %s, place new sell order amount:%s, price: %s" %
                                     (order_id, remaining_amount, price_sell))
                        self.remove_order(order_id)
                        self.new_order(market=market, order_type='sell', amount=remaining_amount,
                                       price=price_sell)
                        break

            return True

        if self.is_buying():
            orders_sell = self.get_orders("buy")
            for order in orders_sell:
                order_id = order['order_id']
                market = order['market']
                retry_count = 0
                while True:
                    order_status = self.brokers[market].get_order(order_id)
                    if order_status:
                        break
                    else:
                        if retry_count > 1:
                            break
                        retry_count += 1
                        time.sleep(0.5)
                if not order_status:
                    # 找了3次都找不到，就当不在了
                    self.remove_order(order_id)
                    continue
                if order_status['status'] == 'CLOSE' or order_status['status'] == 'CANCELED':
                    self.remove_order(order_id)
                    continue
                else:
                    # is pending order
                    remaining_amount = order_status['amount'] - order_status['deal_amount']
                    if remaining_amount <= self.min_amount_market:
                        # 未成交部分小于min_stock, 所以算完成了
                        self.remove_order(order_id)
                        continue
                    price_buy = depths[market]['asks'][0]['price']
                    if price_buy < 0.0:
                        # depth异常，直接return, 下次处理
                        continue
                    retry_count = 0
                    while True:
                        # 先cancel再下单
                        cancel_res = self.brokers[market].cancel_order(order_id)
                        if not cancel_res:
                            if retry_count > 1:
                                self.remove_order(order_id)
                                break
                            retry_count += 1
                            time.sleep(0.5)
                            continue
                        logging.info("handle_order======>cancel order %s, place new buy order amount:%s, price: %s" %
                                     (order_id, remaining_amount, price_buy))
                        self.remove_order(order_id)
                        self.new_order(market=market, order_type='buy', amount=remaining_amount,
                                       price=price_buy)
                        break

            return True

        return False

    def tick(self, depths):
        if not self.monitor_only:
            self.update_balance()
        if not self.is_depths_available(depths):
            return

        if self.handle_order(depths):
            """如果需要处理历史订单，则放弃该次机会直接return"""
            return

        self.skip = False
        self.forward(depths)
        self.reverse(depths)

    def forward(self, depths):
        logging.info("==============正循环, base买，bt1 bt2卖==============")
        base_pair_ask_amount = depths[self.base_pair]['asks'][0]['amount']
        base_pair_ask_price = depths[self.base_pair]['asks'][0]['price']
        base_pair_ask_price_real = base_pair_ask_price * (1 + self.fee_base)

        logging.info("forward======>base_pair: %s ask_price:%s" % (self.base_pair, base_pair_ask_price))

        """所有的real都是带手续费的价格"""
        pair1_bid_amount = depths[self.pair_1]['bids'][0]['amount']
        pair1_bid_price = depths[self.pair_1]['bids'][0]['price']
        pair1_bid_price_real = pair1_bid_price * (1 - self.fee_pair1)

        pair2_bid_amount = depths[self.pair_2]['bids'][0]['amount']
        pair2_bid_price = depths[self.pair_2]['bids'][0]['price']
        pair2_bid_price_real = pair2_bid_price * (1 - self.fee_pair2)

        synthetic_bid_price = round(pair1_bid_price + pair2_bid_price, self.precision)
        synthetic_bid_price_real = round(pair1_bid_price_real + pair2_bid_price_real, self.precision)

        """价差， diff=卖－买"""
        p_diff = round(synthetic_bid_price - base_pair_ask_price, self.precision)
        logging.info("forward======>%s bid_price: %s,  %s bid_price: %s" %
                     (self.pair_1, pair1_bid_price, self.pair_2, pair2_bid_price))
        logging.info("forward======>synthetic_bid_price: %s,   p_diff: %s" % (synthetic_bid_price, p_diff))

        """数量限制"""
        hedge_btc_amount_market = min(pair1_bid_amount, pair2_bid_amount)
        hedge_btc_amount_market = min(hedge_btc_amount_market, base_pair_ask_amount)
        hedge_btc_amount_market = min(self.max_trade_amount, hedge_btc_amount_market)
        hedge_btc_amount_market = hedge_btc_amount_market / 2

        if self.monitor_only:
            hedge_btc_amount = hedge_btc_amount_market
            if hedge_btc_amount < self.min_amount_market:
                logging.info("forward======>hedge_btc_amount is too small! %s" % hedge_btc_amount)
                return
        else:
            can_sell = round(min(self.brokers[self.base_pair].bt1_available,
                                 self.brokers[self.base_pair].bt2_available), 8)
            can_buy = round(self.brokers[self.base_pair].usd_available / base_pair_ask_price_real, 8)
            logging.info("forward======>can_sell: %s, can_buy: %s" % (can_sell, can_buy))

            hedge_btc_amount_balance = round(min(can_buy, can_sell), 8)
            hedge_btc_amount = min(hedge_btc_amount_market, hedge_btc_amount_balance, self.min_trade_amount)
            logging.info("forward======>balance allow btc: %s, market allow btc: %s " %
                         (hedge_btc_amount_balance, hedge_btc_amount_market))
            if hedge_btc_amount < self.min_amount_market:
                logging.info("forward======>hedge_btc_amount is too small! %s" % hedge_btc_amount)
                return

        logging.info("forward======>synthetic_bid_price_real: %s, [%s, %s]" %
                     (synthetic_bid_price_real, pair1_bid_price_real, pair2_bid_price_real))
        t_price = round(synthetic_bid_price_real - base_pair_ask_price_real, self.precision)
        profit = round(t_price * hedge_btc_amount, self.precision)
        logging.info("forward======>t_price: %s, profit: %s" % (t_price, profit))
        if profit > 0:
            logging.info("forward======>find profit!!!: profit:%s,  quote amount: %s,  t_price: %s" %
                         (profit, hedge_btc_amount, t_price))

            current_time = time.time()
            if current_time - self.last_trade < 1:
                logging.warn("forward======>Can't automate this trade, last trade " +
                             "occured %.2f seconds ago" %
                             (current_time - self.last_trade))
                return

            if not self.monitor_only:
                logging.info("forward======>prepare to trade")

                r_sell1 = self.new_order(market=self.pair_1, order_type='sell', amount=hedge_btc_amount,
                                         price=pair1_bid_price)
                if r_sell1 and 'order_id' in r_sell1:
                    r_sell2 = self.new_order(market=self.pair_2, order_type='sell', amount=hedge_btc_amount,
                                             price=pair2_bid_price)
                    if r_sell2 and 'order_id' in r_sell2:
                        buy_amount_base = round(hedge_btc_amount * (1 + self.fee_base), 8)
                        self.new_order(market=self.base_pair, order_type='buy', amount=buy_amount_base,
                                       price=base_pair_ask_price)
                self.skip = True

            self.last_trade = time.time()

    def reverse(self, depths):
        if self.skip and (not self.monitor_only):
            return
        logging.info("==============逆循环, base卖，bt1 bt2买==============")
        base_pair_bid_amount = depths[self.base_pair]['bids'][0]['amount']
        base_pair_bid_price = depths[self.base_pair]['bids'][0]['price']
        base_pair_bid_price_real = base_pair_bid_price * (1 - self.fee_base)

        logging.info("reverse======>base_pair: %s bid_price:%s" % (self.base_pair, base_pair_bid_price))

        pair1_ask_amount = depths[self.pair_1]['asks'][0]['amount']
        pair1_ask_price = depths[self.pair_1]['asks'][0]['price']
        pair1_ask_price_real = pair1_ask_price * (1 + self.fee_pair1)

        pair2_ask_amount = depths[self.pair_2]['asks'][0]['amount']
        pair2_ask_price = depths[self.pair_2]['asks'][0]['price']
        pair2_ask_price_real = pair2_ask_price * (1 + self.fee_pair2)

        synthetic_ask_price = round(pair1_ask_price + pair2_ask_price, self.precision)
        synthetic_ask_price_real = round(pair1_ask_price_real + pair2_ask_price_real, self.precision)
        p_diff = round(base_pair_bid_price - synthetic_ask_price, self.precision)

        logging.info("reverse======>%s ask_price: %s,  %s ask_price: %s" %
                     (self.pair_1, pair1_ask_price, self.pair_2, pair2_ask_price))
        logging.info("reverse======>synthetic_ask_price: %s,   p_diff: %s" % (synthetic_ask_price, p_diff))

        """数量限制"""
        hedge_btc_amount_market = min(pair2_ask_amount, pair1_ask_amount)
        hedge_btc_amount_market = min(hedge_btc_amount_market, base_pair_bid_amount)
        hedge_btc_amount_market = min(self.max_trade_amount, hedge_btc_amount_market)
        hedge_btc_amount_market = hedge_btc_amount_market / 2

        if self.monitor_only:
            hedge_btc_amount = hedge_btc_amount_market
            if hedge_btc_amount < self.min_amount_market:
                logging.info("reverse======>hedge_btc_amount is too small! %s" % hedge_btc_amount)
                return
        else:
            # usd买bt1 bt2
            usd_amount_balance = round(self.brokers[self.base_pair].usd_available, 8)

            can_buy_bt1 = round(usd_amount_balance / pair1_ask_price_real, 8)
            can_buy_bt2 = round(usd_amount_balance / pair2_ask_price_real, 8)
            can_buy = min(can_buy_bt1, can_buy_bt2)

            can_sell = round(self.brokers[self.base_pair].btc_available, 8)
            logging.info("reverse======>can_sell: %s, can_buy: %s" % (can_sell, can_buy))

            hedge_btc_amount_balance = round(min(can_buy, can_sell), 8)

            hedge_btc_amount = min(hedge_btc_amount_market, hedge_btc_amount_balance, self.min_trade_amount)
            logging.info("reverse======>balance allow btc: %s, market allow btc: %s " %
                         (hedge_btc_amount_balance, hedge_btc_amount_market))

            # 买bt1和bt2总共消耗的usd总和
            hedge_usd_total = round(hedge_btc_amount * (pair1_ask_price_real + pair2_ask_price_real), 8)

            if (hedge_btc_amount < self.min_amount_market) or (hedge_usd_total > usd_amount_balance):
                logging.warn("reverse======>hedge_btc_amount is too small! %s, or usd total %s large than balance %s" %
                             (hedge_btc_amount, hedge_usd_total, usd_amount_balance))
                return
        logging.info("reverse======>synthetic_ask_price_real: %s, [%s, %s]" %
                     (synthetic_ask_price_real, pair1_ask_price_real, pair2_ask_price_real))
        t_price = round(base_pair_bid_price_real - synthetic_ask_price_real, self.precision)
        profit = round(t_price * hedge_btc_amount, self.precision)
        logging.info("reverse======>t_price: %s, profit: %s" % (t_price, profit))
        if profit > 0:
            logging.info("reverse======>find profit!!!: profit:%s,  quote amount: %s ,  t_price: %s" %
                         (profit, hedge_btc_amount, t_price))

            current_time = time.time()
            if current_time - self.last_trade < 3:
                logging.warn("reverse======>Can't automate this trade, last trade " +
                             "occured %.2f seconds ago" %
                             (current_time - self.last_trade))
                return

            if not self.monitor_only:
                logging.info("reverse======>prepare to trade")
                amount_buy = hedge_btc_amount * (1 + self.fee_pair1)
                r_sell = self.new_order(market=self.base_pair, order_type='sell', amount=hedge_btc_amount,
                                        price=base_pair_bid_price)
                if r_sell and 'order_id' in r_sell:
                    self.new_order(market=self.pair_1, order_type='buy', amount=amount_buy, price=pair1_ask_price)
                    self.new_order(market=self.pair_2, order_type='buy', amount=amount_buy, price=pair2_ask_price)
                    self.skip = True

            self.last_trade = time.time()

    def update_balance(self):
        self.brokers[self.base_pair].get_balances()