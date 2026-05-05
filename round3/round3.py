from datamodel import Listing, Symbol, ConversionObservation, Observation, Order, OrderDepth, Trade, TradingState, ProsperityEncoder
import json
import math
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

HYDROGEL_SYMBOL = "HYDROGEL_PACK"
VELVETFRUIT_SYMBOL = "VELVETFRUIT_EXTRACT"

VEV_SYMBOLS = ["VEV_4000", "VEV_4500", "VEV_5000", "VEV_5100",
               "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]

POSITION_LIMITS = {
    HYDROGEL_SYMBOL: 200,
    VELVETFRUIT_SYMBOL: 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
}

# Kalman-MR fair anchors (mean + offset across 3 days)
HYDROGEL_FAIR_STATIC = 10030
VELVETFRUIT_FAIR_STATIC = 5275

# VEV divergence thresholds (per-strike)
VEV_DIVERGE_THRESHOLDS = {
    "VEV_4000": 18, "VEV_4500": 18, "VEV_5000": 15, "VEV_5100": 13,
    "VEV_5200": 10, "VEV_5300": 7, "VEV_5400": 4, "VEV_5500": 2
}

# VFE informed-flow signal: size>=11 prints predict +4.5 mid over 500 ticks
INFORMED_SIZE_VFE = 11
INFORMED_GAIN_S = 10
INFORMED_DECAY = 0.998

TAKE_WIDTH = 1
ANCHOR_WARMUP = 100
DIVERGE_TAKE_SIZE = 30


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
    
    def get_micro_price(self):
        # volume-weighted top-of-book micro-price
        micro = None
        try:
            bv_tob = self.market_buy_orders[self.best_bid]
            av_tob = self.market_sell_orders[self.best_ask]
            tot = bv_tob + av_tob
            if tot > 0:
                micro = (self.best_bid * av_tob + self.best_ask * bv_tob) / tot
            else:
                micro = self.mid_price
        except: pass
        return micro
    
    def get_full_depth_mid(self):
        # average of volume-weighted bid side and volume-weighted ask side
        fdm = None
        try:
            bids = list(self.market_buy_orders.items())
            asks = list(self.market_sell_orders.items())
            bv = sum(v for _, v in bids)
            av = sum(v for _, v in asks)
            if bv <= 0 or av <= 0:
                fdm = (self.best_bid + self.best_ask) / 2
            else:
                bid_vwap = sum(p * v for p, v in bids) / bv
                ask_vwap = sum(p * v for p, v in asks) / av
                fdm = (bid_vwap + ask_vwap) / 2
        except: pass
        return fdm
    
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
        buy_orders = {}
        sell_orders = {}
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
# Hydrogel / Kalman-MR Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class HydrogelTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(HYDROGEL_SYMBOL, state, prints, new_trader_data)
        
        self.fair_static = HYDROGEL_FAIR_STATIC
        self.k_ss = 0.02
        self.mr_gain = 1000
        self.sigma_init = 30.0
        self.take_max_pay = -6 # only cross when offer is >=6 ticks below fair
        self.quote_edge = 3
        self.quote_size = 30
        
        self.fair = self.update_kalman_fair()
        self.sigma = self.update_sigma()
    
    
    def update_kalman_fair(self):
        # Kalman-track fair on volume-weighted micro-price
        micro = self.get_micro_price()
        if micro is None:
            return None
        
        fair = self.last_traderData.get(self.name + "_f", micro)
        err_ema = self.last_traderData.get(self.name + "_err", abs(micro - fair))
        
        innov = micro - fair
        err_ema += self.k_ss * (abs(innov) - err_ema)
        fair += (self.k_ss / (1.0 + err_ema)) * innov
        
        self.new_trader_data[self.name + "_f"] = fair
        self.new_trader_data[self.name + "_err"] = err_ema
        return fair
    
    
    def update_sigma(self):
        # Online sigma estimate from (mid - fair) variance
        if self.fair is None or self.mid_price is None:
            return self.sigma_init
        
        n = self.last_traderData.get(self.name + "_n", 0) + 1
        s2 = self.last_traderData.get(self.name + "_s2", 0.0) + (self.mid_price - self.fair) ** 2
        
        self.new_trader_data[self.name + "_n"] = n
        self.new_trader_data[self.name + "_s2"] = s2
        
        if n > 50:
            return max(1.0, (s2 / n) ** 0.5)
        return self.sigma_init
    
    
    def get_target_position(self, target_bias=0):
        # target = mr_gain * (anchor - mid) / sigma + bias, clamped to +/- limit
        if self.mid_price is None or self.sigma is None:
            return 0
        raw = round(self.mr_gain * (self.fair_static - self.mid_price) / self.sigma) + target_bias
        return max(-self.position_limit, min(self.position_limit, raw))
    
    
    def take_to_target(self, target):
        # cross the book to move toward target, only if price is favorable vs fair
        delta = target - self.initial_position
        
        if delta > 0:
            for sp, sv in self.market_sell_orders.items():
                if sp > self.fair + self.take_max_pay:
                    break
                volume = min(sv, delta)
                if volume <= 0:
                    break
                self.bid(sp, volume)
                delta -= volume
        elif delta < 0:
            need = -delta
            for bp, bv in self.market_buy_orders.items():
                if bp < self.fair - self.take_max_pay:
                    break
                volume = min(bv, need)
                if volume <= 0:
                    break
                self.ask(bp, volume)
                need -= volume
    
    
    def quote_inside(self):
        # quote 1 tick inside the deepest level still outside [fair-edge, fair+edge]
        bid_anchor = max((p for p in self.market_buy_orders if p <= self.fair - self.quote_edge), default=None)
        ask_anchor = min((p for p in self.market_sell_orders if p >= self.fair + self.quote_edge), default=None)
        
        if bid_anchor is not None:
            self.bid(bid_anchor + 1, self.quote_size)
        if ask_anchor is not None:
            self.ask(ask_anchor - 1, self.quote_size)
    
    
    def get_orders(self):
        if self.fair is None or len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        target = self.get_target_position()
        self.take_to_target(target)
        self.quote_inside()
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Velvetfruit / Kalman-MR + Informed-Flow Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class VelvetfruitTrader(HydrogelTrader):
    # inherits Kalman-MR mechanics; overrides params + adds informed-flow target bias
    def __init__(self, state, prints, new_trader_data):
        # bypass HydrogelTrader.__init__ and go straight to AbstractTrader to set our own params
        AbstractTrader.__init__(self, VELVETFRUIT_SYMBOL, state, prints, new_trader_data)
        
        self.fair_static = VELVETFRUIT_FAIR_STATIC
        self.k_ss = 0.02
        self.mr_gain = 3000
        self.sigma_init = 15.0
        self.take_max_pay = -2 # only cross when offer is >=2 ticks below fair
        self.quote_edge = 1
        self.quote_size = 30
        
        self.fair = self.update_kalman_fair()
        self.sigma = self.update_sigma()
        self.informed_signal = self.update_informed_signal()
    
    
    def update_informed_signal(self):
        # decayed signed-volume EMA of size>=11 trades that lift the offer or hit the bid
        sig = self.last_traderData.get(self.name + "_inf", 0.0) * INFORMED_DECAY
        
        market_trades = self.state.market_trades.get(self.name, []) or []
        if self.best_bid is not None and self.best_ask is not None:
            for t in market_trades:
                if t.quantity < INFORMED_SIZE_VFE:
                    continue
                if t.price >= self.best_ask:
                    sig += t.quantity
                elif t.price <= self.best_bid:
                    sig -= t.quantity
        
        self.new_trader_data[self.name + "_inf"] = sig
        return sig
    
    
    def get_orders(self):
        if self.fair is None or len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        target_bias = int(round(INFORMED_GAIN_S * self.informed_signal))
        target = self.get_target_position(target_bias=target_bias)
        self.take_to_target(target)
        self.quote_inside()
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# VEV / Anchor-Divergence + MM Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class VevTrader(AbstractTrader):
    def __init__(self, name, state, prints, new_trader_data):
        super().__init__(name, state, prints, new_trader_data)
        
        self.quote_size = 30
        self.diverge_threshold = VEV_DIVERGE_THRESHOLDS.get(self.name, 0)
        self.max_diverge_position = 295
        
        self.fair_price = self.get_full_depth_mid() # vol-weighted full-book mid
        self.anchor = self.update_anchor()
        self.anchor_n = self.new_trader_data.get(self.name + "_an", 0)
    
    
    def update_anchor(self):
        # rolling cumulative-mean anchor of the top-of-book mid
        if self.mid_price is None:
            n = self.last_traderData.get(self.name + "_an", 0)
            s = self.last_traderData.get(self.name + "_as", 0.0)
            self.new_trader_data[self.name + "_an"] = n
            self.new_trader_data[self.name + "_as"] = s
            return s / n if n > 0 else None
        
        n = self.last_traderData.get(self.name + "_an", 0) + 1
        s = self.last_traderData.get(self.name + "_as", 0.0) + self.mid_price
        
        self.new_trader_data[self.name + "_an"] = n
        self.new_trader_data[self.name + "_as"] = s
        return s / n
    
    
    def take_divergence(self):
        # if mid has drifted away from anchor, take liquidity in the reverting direction
        if self.diverge_threshold <= 0 or self.anchor_n < ANCHOR_WARMUP or self.anchor is None:
            return 0, 0
        
        diverge = self.mid_price - self.anchor
        if abs(diverge) < self.diverge_threshold:
            return 0, 0
        
        bought = sold = 0
        
        if diverge > 0 and self.initial_position > -self.max_diverge_position:
            # mid is rich vs anchor -> sell
            room = self.initial_position + self.max_diverge_position
            for bp, bv in self.market_buy_orders.items():
                cap = min(DIVERGE_TAKE_SIZE - sold, room - sold, self.max_allowed_sell_volume)
                if cap <= 0:
                    break
                volume = min(bv, cap)
                self.ask(bp, volume)
                sold += volume
        elif diverge < 0 and self.initial_position < self.max_diverge_position:
            # mid is cheap vs anchor -> buy
            room = self.max_diverge_position - self.initial_position
            for sp, sv in self.market_sell_orders.items():
                cap = min(DIVERGE_TAKE_SIZE - bought, room - bought, self.max_allowed_buy_volume)
                if cap <= 0:
                    break
                volume = min(sv, cap)
                self.bid(sp, volume)
                bought += volume
        
        return bought, sold
    
    
    def take_fair(self, fair_price):
        # cross the book against any level beyond fair +/- TAKE_WIDTH
        for sp, sv in self.market_sell_orders.items():
            if sp >= fair_price - TAKE_WIDTH:
                break
            self.bid(sp, sv)
        
        for bp, bv in self.market_buy_orders.items():
            if bp <= fair_price + TAKE_WIDTH:
                break
            self.ask(bp, bv)
    
    
    def quote_midpoint(self, fair_price):
        # quote at the midpoint between fair and the touch on each side
        if self.best_bid is None or self.best_ask is None:
            return
        
        bid_px = min(math.floor((fair_price + self.best_bid) / 2), self.best_ask - 1)
        ask_px = max(math.ceil((fair_price + self.best_ask) / 2), self.best_bid + 1)
        
        if bid_px < ask_px:
            self.bid(bid_px, self.quote_size)
            self.ask(ask_px, self.quote_size)
    
    
    def get_orders(self):
        if self.fair_price is None or len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        self.take_divergence()
        self.take_fair(self.fair_price)
        self.quote_midpoint(self.fair_price)
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Trader Class
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class Trader:
    
    def bid(self):
        return 1 # should hit median
    
    def run(self, state: TradingState):
        
        product_traders = {
            HYDROGEL_SYMBOL: HydrogelTrader,
            VELVETFRUIT_SYMBOL: VelvetfruitTrader,
        }
        # VEV strikes share a single trader class, dispatched by symbol
        for vev in VEV_SYMBOLS:
            product_traders[vev] = VevTrader
        
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
                # VevTrader takes (name, state, ...); others take (state, ...)
                if product_trader is VevTrader:
                    trader = product_trader(symbol, state, prints, new_trader_data)
                else:
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