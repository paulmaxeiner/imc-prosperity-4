from config import *
from datamodel import Listing, Symbol, ConversionObservation, Observation, Order, OrderDepth, Trade, TradingState, ProsperityEncoder
import json
import string
from typing import Any, Dict, List

class AbstractTrader:
    def __init__(self, name, state, prints, new_trader_data):
        self.name = name # symbol the trader is working with
        self.state = state # state object passed from Trader()
        self.prints = prints # blank dictionary passed by reference to print
        self.new_trader_data = new_trader_data # blank dictionary passed by reference to return
        
        self.position_limit = POSITION_LIMITS.get(self.name, 0)
        
        self.orders = [] # empty array to hold this trader's orders
        
        self.last_traderData = self.get_trader_data()
        
        self.initial_position = self.state.position.get(self.name, 0)
        
        self.market_buy_orders, self.market_sell_orders = self.get_order_depth()
        self.best_bid, self.best_ask = self.get_best_bid_ask()
        self.bid_wall, self.wall_mid, self.ask_wall = self.get_walls()
        
        self.max_allowed_buy_volume, self.max_allowed_sell_volume = self.get_max_allowed_volume()


    
    def bid(self, price, volume):
        # submits the quantity only if it does not violate the limit, in which it will place the max allowable order
        quantity = min(abs(volume), self.max_allowed_buy_volume)
        order = Order(self.name, int(price), quantity)
        self.max_allowed_buy_volume -= quantity
        self.orders.append(order)
        
    def ask(self, price, volume):
        quantity = min(abs(volume), self.max_allowed_sell_volume)
        order = Order(self.name, int(price), -quantity)
        self.max_allowed_sell_volume -= quantity
        self.orders.append(order)
 
    def get_trader_data(self):
        last_traderData = {}
        
        try: last_traderData = json.loads(self.state.traderData) if self.state.traderData else {}
        except: logger.print("td err")
        
        return last_traderData
        
    def get_best_bid_ask(self):
        best_bid = best_ask = None
        try:
            if len(self.market_buy_orders) > 0:
                best_bid = max(self.market_buy_orders.keys())
            if len(self.market_sell_orders) > 0:
                best_ask = min(self.market_sell_orders.keys())
        except: pass
        return best_bid, best_ask
    


    def get_walls(self):
        bid_wall = wall_mid = ask_wall = None
        
        try: bid_wall = min([x for x,_ in self.market_buy_orders.items()])
        except: pass
        
        try: ask_wall = max([x for x,_ in self.market_sell_orders.items()])
        except: pass
        
        try: wall_mid = (bid_wall + ask_wall)/2
        except: pass

        return bid_wall, wall_mid, ask_wall
    
    def get_max_allowed_volume(self):
        max_allowed_buy_volume = self.position_limit - self.initial_position
        max_allowed_sell_volume = self.position_limit + self.initial_position # holding positive inventory means we can sell the limit + what we have
        return max_allowed_buy_volume, max_allowed_sell_volume
    
    def get_order_depth(self):
        order_depth = {}
        try:
            order_depth: OrderDepth = self.state.order_depths[self.name]
        except: pass
        
        try:
            buy_orders = {bp: abs(bv)
                            for bp, bv in 
                            sorted(order_depth.buy_orders.items(),
                                    key=lambda x: x[0], # sort based on price (at index=0)
                                    reverse=True)} # reverses for buy order (sorts from high price -> low price)
            sell_orders = {sp: abs(sv) # important: sell quantity will become positive
                            for sp, sv in
                            sorted(order_depth.sell_orders.items(),
                                    key=lambda x: x[0])} # sorts from high price -> low price
        except: pass
        return buy_orders, sell_orders
    
    def take_market(self, fair_price):
        for sp, sv in self.market_sell_orders.items():
            if sp <= fair_price - 1:
                self.bid(sp, sv)
            elif sp <= fair_price and self.initial_position < 0:
                volume = min(sv, abs(self.initial_position))
                self.bid(sp, volume)
                
        for bp, bv in self.market_buy_orders.items():
            if bp >= fair_price + 1:
                self.ask(bp, bv)
            elif bp >= fair_price and self.initial_position > 0:
                volume = min(bv, self.initial_position)
                self.ask(bp, volume)
    
    def make_market(self, fair_price):
        bid_price = self.bid_wall + 1
        ask_price = self.ask_wall - 1
        
        for bp, bv in self.market_buy_orders.items():
            overbidding_price = bp + 1 # we beat them by 1
            if bv > 1 and overbidding_price < fair_price:
                bid_price = max(bid_price, overbidding_price)
                break
            elif bp < fair_price: # we bid if we are still under
                bid_price = max(bid_price, bp)
                break
        
        for sp, sv in self.market_sell_orders.items():
            underbidding_price = sp - 1 # we beat them by 1
            if sv > 1 and underbidding_price > fair_price:
                ask_price = min(ask_price, underbidding_price)
                break
            elif sp > fair_price: # we bid if we are still under
                ask_price = min(ask_price, sp)
                break
        
        self.bid(bid_price, self.max_allowed_buy_volume)
        self.ask(ask_price, self.max_allowed_sell_volume)
    
    
    def get_orders(self):
        return {}

