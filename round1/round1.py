from datamodel import Listing, Symbol, ConversionObservation, Observation, Order, OrderDepth, Trade, TradingState, ProsperityEncoder
import json
import string
from typing import Any, Dict, List

# Logger
class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing.symbol, listing.product, listing.denomination])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        lo, hi = 0, min(len(value), max_length)
        out = ""

        while lo <= hi:
            mid = (lo + hi) // 2

            candidate = value[:mid]
            if len(candidate) < len(value):
                candidate += "..."

            encoded_candidate = json.dumps(candidate)

            if len(encoded_candidate) <= max_length:
                out = candidate
                lo = mid + 1
            else:
                hi = mid - 1

        return out

logger = Logger()


#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Variables
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––

# Volatile but more stable
OSMIUM_SYMBOL = "ASH_COATED_OSMIUM"

# Increasing
# INTARIAN_PEPPER_ROOT
PEPPER_SYMBOL = "INTARIAN_PEPPER_ROOT"

POSITION_LIMITS = {
    OSMIUM_SYMBOL: 80,
    PEPPER_SYMBOL: 80
}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Abstract Trader / Base Class
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
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
        self.mid_price = self.get_mid_price()
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
    
    def get_mid_price(self):
        mid = None
        try: mid = (self.best_ask+self.best_bid)/2
        except: pass
        return mid
    
    def get_spread(self):
        spread = None
        try: spread = self.best_ask-self.best_bid
        except: pass
        return spread
    
    def update_last_traded_price(self):
        if self.name in self.state.market_trades and len(self.state.market_trades[self.name])>0:
            p = self.state.market_trades[self.name][0].price # update so it shows max/min
            self.new_trader_data[self.name+"_ltp"] = p
    
    def get_last_traded_price(self):
        ltp = None
        try: ltp = self.last_traderData[self.name + "_ltp"]
        except: pass
        return ltp


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
        
    def buy_and_hold(self):
        '''
        This strategy involves clearing the asks / buying as much as possible and holding.
        '''
        
        if self.ask_wall is not None and self.initial_position < self.position_limit:
            for sp, sv in self.market_sell_orders.items():
                self.bid(sp, sv) # buy all sell orders
        
    
    
    def get_orders(self):
        return {}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Emerald / Static Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class OsmiumTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(OSMIUM_SYMBOL, state, prints, new_trader_data) # inherits functions from AbstractTrader
        
        
    def get_orders(self):
        if self.wall_mid is not None:
            fair_price = self.wall_mid
            self.take_market(fair_price)
            self.make_market(fair_price)
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Tomato / Dynamic Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class PepperTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(PEPPER_SYMBOL, state, prints, new_trader_data)
        
        self.fair_price = self.get_fair_price()
        
    
    def get_orders(self):
        # Here, the strategy lies in the optimal way to get maximized position at the beginning
        
        # 1) Aggressively Buy at the Beginning
        
        MAX_PREMIUM = 7 # the most above our fair value we will pay to get a fill now (about 1/2 of the spread)
            # This is key to an optimal initial fill, reducing our initial drawdown and maximizing PnL
        if self.max_allowed_buy_volume > 0 and self.fair_price is not None and self.ask_wall is not None:
            for sp, sv in self.market_sell_orders.items():
                if sp < self.fair_price + MAX_PREMIUM:
                    volume = min(sv, self.max_allowed_buy_volume)
                    self.bid(sp, volume) # Buy
    
        if self.best_bid is not None:
            self.bid(self.best_bid +1, self.max_allowed_buy_volume)
        
        
        # if self.max_allowed_buy_volume > 0:
        #     if self.best_ask is not None:
        #         self.bid(self.best_ask, self.max_allowed_buy_volume)
        #     if self.best_bid is not None:
        #         self.bid(self.best_bid + 1, self.max_allowed_buy_volume)
        #     else:
        #         self.bid(self.get_fair_price(), self.max_allowed_buy_volume)
        
    
        return {self.name: self.orders}
    
    
    def get_fair_price(self):
        SLOPE = 0.001
        ts = self.state.timestamp
        
        if not self.last_traderData or 'start_price' not in self.last_traderData:
            start_price = self.wall_mid or self.mid_price or self.best_ask or self.best_bid
            self.new_trader_data["start_price"] = start_price
        else:
            start_price = self.last_traderData["start_price"]
        
        fp = start_price + 0.001 * ts
        self.new_trader_data["start_price"] = start_price
        self.new_trader_data["fp"] = fp
        return fp
            


# RUNNING PNL: 290,137
# NEW: 290,385
# BETTER: 290,509 (only take below FV + max_premium)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Trader Class
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class Trader:
    def run(self, state: TradingState):
        
        product_traders = {
            OSMIUM_SYMBOL: OsmiumTrader,
            PEPPER_SYMBOL: PepperTrader
        }
        
        prints = {}
        def print_dict(dict_to_print: dict):
            try: print(json.dumps(dict_to_print, indent=4))
            except: pass

        result = {}
        conversions = 0
        new_trader_data = {}
        
        # Each trader submits orders
        for symbol, product_trader in product_traders.items():
            if symbol in state.order_depths:
                trader = product_trader(state, prints, new_trader_data)
                orders = trader.get_orders()
                result.update(orders)
        
        
        
        # Save Final Data
        final_trader_data = {}
        try:
            final_trader_data = json.dumps(new_trader_data)
        except: final_trader_data = ''
        
        # Debugging / Backtesting
        print_dict(final_trader_data)
        logger.flush(state, result, conversions, final_trader_data)
        
        
        return result, conversions, final_trader_data
    
