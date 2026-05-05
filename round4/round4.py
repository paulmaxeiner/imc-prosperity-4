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
VEV_5200_SYMBOL = "VEV_5200"

# Symbols handled by ZTakeTrader (Bayesian-blended mean z-score)
Z_TAKE_SYMBOLS = ["VELVETFRUIT_EXTRACT", "VEV_4000", "VEV_4500", "VEV_5000",
                  "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]

# Symbols handled by BuyAndHoldTrader (deep-OTM lottery vouchers)
BUY_AND_HOLD_SYMBOLS = ["VEV_6000", "VEV_6500"]

POSITION_LIMITS = {
    HYDROGEL_SYMBOL: 200,
    VELVETFRUIT_SYMBOL: 200,
    "VEV_4000": 300, "VEV_4500": 300, "VEV_5000": 300, "VEV_5100": 300,
    "VEV_5200": 300, "VEV_5300": 300, "VEV_5400": 300, "VEV_5500": 300,
    "VEV_6000": 300, "VEV_6500": 300,
}

# Per-asset z-take params (mean, sd, z_thresh, take_size, prior)
# Bayesian blend: eff_mean = (prior * mean + sum_obs) / (prior + n_obs)
# prior=10**9 ~= static. VEV_5200 tuned z-take beats anchor-divergence by +$10.8k m+m
Z_TAKE_PARAMS = {
    "VELVETFRUIT_EXTRACT": {"mean": 5247, "sd": 17.091, "z_thresh": 1.0,  "take_size": 25, "prior": 10**9},
    "VEV_4000":            {"mean": 1247, "sd": 17.114, "z_thresh": 1.5,  "take_size": 10, "prior": 10**9},
    "VEV_4500":            {"mean":  747, "sd": 17.105, "z_thresh": 1.5,  "take_size": 10, "prior": 10**9},
    "VEV_5000":            {"mean":  252, "sd": 16.381, "z_thresh": 1.0,  "take_size": 10, "prior": 10000},
    "VEV_5100":            {"mean":  163, "sd": 15.327, "z_thresh": 1.0,  "take_size": 50, "prior": 10000},
    "VEV_5200":            {"mean":   91, "sd": 12.796, "z_thresh": 0.75, "take_size": 10, "prior":  2000},
    "VEV_5300":            {"mean":   43, "sd":  8.976, "z_thresh": 0.5,  "take_size": 10, "prior":   200},
    "VEV_5400":            {"mean":   14, "sd":  4.608, "z_thresh": 0.5,  "take_size": 25, "prior":   500},
    "VEV_5500":            {"mean":    6, "sd":  2.477, "z_thresh": 1.0,  "take_size": 25, "prior":   200},
}

# Hydrogel conviction-based config
HP_FAIR = 10002
HP_STDEV_INIT = 33.0
HP_VAR_ALPHA = 0.005
HP_QSIZE = 35
HP_FLAT_PULL = 1.0
HP_MR_THRESH = 4
HP_MR_BOOST = 1.5
HP_Z_MIN = 0.7
HP_Z_MAX = 2.0
HP_EMA_FAST = 0.20
HP_EMA_SLOW = 0.08
HP_EMA_VSLOW = 0.02
HP_EMA_FULL = 1.5
HP_W_Z = 0.625
HP_W_EMA = 0.375
HP_TAKE_MAX = 25
HP_TAKE_OFFSET = 4
HP_BASE_CAP_PCT = 0.50
HP_FULL_CAP_PCT = 1.00
HP_HARD_CAP_PCT = 0.95
HP_AGGR_Z_THRESH = 2.5
HP_AGGR_MAX_TAKE = 90
HP_MM_BOOST = 1.0

# VEV_5200 (legacy anchor-divergence config — kept for reference, not active in current mix)
VEV_5200_DIVERGE_THRESHOLD = 11
VEV_5200_QSIZE = 30
ANCHOR_TAKE_WIDTH = 1
ANCHOR_WARMUP = 500
DIVERGE_TAKE_SIZE = 30
MAX_DIVERGE_POS = 295


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
# Z-Take Trader (VFE + most VEV strikes)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class ZTakeTrader(AbstractTrader):
    # Bayesian-blended mean: eff_mean = (prior*static + sum_obs) / (prior + n)
    # When |z| >= z_thresh, take liquidity at any level beyond eff_mean
    def __init__(self, name, state, prints, new_trader_data):
        super().__init__(name, state, prints, new_trader_data)
        
        params = Z_TAKE_PARAMS.get(self.name, {})
        self.static_mean = params.get("mean", 0)
        self.sd = params.get("sd", 0)
        self.z_thresh = params.get("z_thresh", 1.0)
        self.take_size = params.get("take_size", 10)
        self.prior = params.get("prior", 10**9)
        
        self.n_obs, self.sum_obs = self.update_running_mean()
        self.eff_mean = self.get_effective_mean()
    
    
    def update_running_mean(self):
        n = self.last_traderData.get(self.name + "_n", 0)
        s = self.last_traderData.get(self.name + "_s", 0.0)
        
        if self.mid_price is not None:
            n += 1
            s += self.mid_price
        
        self.new_trader_data[self.name + "_n"] = n
        self.new_trader_data[self.name + "_s"] = s
        return n, s
    
    
    def get_effective_mean(self):
        # Bayesian blend of static prior and empirical mean
        return (self.prior * self.static_mean + self.sum_obs) / (self.prior + self.n_obs)
    
    
    def get_z_score(self):
        if self.sd <= 0 or self.mid_price is None:
            return None
        return (self.mid_price - self.eff_mean) / self.sd
    
    
    def get_orders(self):
        if len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        z = self.get_z_score()
        if z is None or abs(z) < self.z_thresh:
            return {self.name: self.orders}
        
        if z > 0:
            # mid is rich -> sell at any bid >= eff_mean, capped at take_size
            remaining = self.take_size
            for bp, bv in self.market_buy_orders.items():
                if bp < self.eff_mean or remaining <= 0:
                    break
                volume = min(bv, remaining)
                self.ask(bp, volume)
                remaining -= volume
        else:
            # mid is cheap -> buy at any ask <= eff_mean, capped at take_size
            remaining = self.take_size
            for sp, sv in self.market_sell_orders.items():
                if sp > self.eff_mean or remaining <= 0:
                    break
                volume = min(sv, remaining)
                self.bid(sp, volume)
                remaining -= volume
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Hydrogel / Conviction Trader
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class HydrogelTrader(AbstractTrader):
    # Conviction = w_z * z_strength + w_ema * ema_strength (gated on aligned trend)
    # Layered: hard-cap unwind -> primary conviction take -> aggressive MR -> MM quotes
    def __init__(self, state, prints, new_trader_data):
        super().__init__(HYDROGEL_SYMBOL, state, prints, new_trader_data)
        
        self.fair = HP_FAIR
        self.hard_cap = HP_HARD_CAP_PCT * self.position_limit
        
        self.var = self.update_variance()
        self.stdev = self.get_stdev()
        self.ema_fast, self.ema_slow, self.ema_vslow = self.update_emas()
        
        self.direction, self.conviction = self.get_conviction()
    
    
    def update_variance(self):
        # EWMA of squared deviation from fair
        prev_var = self.last_traderData.get(self.name + "_var", HP_STDEV_INIT ** 2)
        if self.mid_price is None:
            self.new_trader_data[self.name + "_var"] = prev_var
            return prev_var
        
        dev = self.mid_price - self.fair
        var = (1.0 - HP_VAR_ALPHA) * prev_var + HP_VAR_ALPHA * dev * dev
        self.new_trader_data[self.name + "_var"] = var
        return var
    
    
    def get_stdev(self):
        # floor the stdev so a quiet day can't blow conviction up
        return max(HP_STDEV_INIT * 0.15, self.var ** 0.5)
    
    
    def update_emas(self):
        prev_f = self.last_traderData.get(self.name + "_ef", self.mid_price)
        prev_s = self.last_traderData.get(self.name + "_es", self.mid_price)
        prev_vs = self.last_traderData.get(self.name + "_evs", self.mid_price)
        
        if self.mid_price is None:
            return prev_f, prev_s, prev_vs
        
        ef = HP_EMA_FAST * self.mid_price + (1 - HP_EMA_FAST) * prev_f
        es = HP_EMA_SLOW * self.mid_price + (1 - HP_EMA_SLOW) * prev_s
        evs = HP_EMA_VSLOW * self.mid_price + (1 - HP_EMA_VSLOW) * prev_vs
        
        self.new_trader_data[self.name + "_ef"] = ef
        self.new_trader_data[self.name + "_es"] = es
        self.new_trader_data[self.name + "_evs"] = evs
        return ef, es, evs
    
    
    def get_conviction(self):
        # combines z-score strength and EMA trend alignment into a [0, 1] score
        if self.mid_price is None:
            return 0, 0.0
        
        dev = self.mid_price - self.fair
        z = abs(dev / self.stdev)
        
        # z-strength: 0 below z_min, 1 above z_max, linear between
        if z < HP_Z_MIN:
            z_str = 0.0
        else:
            z_str = min(1.0, (z - HP_Z_MIN) / (HP_Z_MAX - HP_Z_MIN))
        
        # direction we want to bet (mean-reverting)
        direction = +1 if dev < 0 else -1
        
        # EMA trend: only counts if short and medium agree with our MR direction
        short = self.ema_fast - self.ema_slow
        medium = self.ema_slow - self.ema_vslow
        s_sign = (short > 0) - (short < 0)
        m_sign = (medium > 0) - (medium < 0)
        
        if s_sign != 0 and s_sign == m_sign == direction:
            ema_str = min(1.0, abs(short) / HP_EMA_FULL)
        else:
            ema_str = 0.0
        
        if z_str > 0:
            conv = HP_W_Z * z_str + HP_W_EMA * ema_str
        else:
            conv = 0.0
        
        return direction, conv
    
    
    def unwind_hard_cap(self):
        # if past the hard cap, peel off half of it back toward zero
        pos = self.initial_position
        if pos > self.hard_cap:
            target = pos - int(self.hard_cap * 0.5)
            remaining = target
            for bp, bv in self.market_buy_orders.items():
                if bp < self.fair - 2 or remaining <= 0:
                    break
                volume = min(bv, remaining)
                self.ask(bp, volume)
                remaining -= volume
        elif pos < -self.hard_cap:
            target = -pos - int(self.hard_cap * 0.5)
            remaining = target
            for sp, sv in self.market_sell_orders.items():
                if sp > self.fair + 2 or remaining <= 0:
                    break
                volume = min(sv, remaining)
                self.bid(sp, volume)
                remaining -= volume
    
    
    def take_primary(self):
        # conviction-sized take, capped by a soft cap that scales with conviction
        if self.conviction <= 0 or self.direction == 0:
            return
        
        primary_target = int(round(HP_TAKE_MAX * self.conviction))
        soft_cap = (HP_BASE_CAP_PCT + (HP_FULL_CAP_PCT - HP_BASE_CAP_PCT) * self.conviction) * self.position_limit
        pos_after = self.initial_position + (self.position_limit - self.max_allowed_buy_volume - (self.position_limit + self.initial_position - self.max_allowed_sell_volume))
        # pos_after = initial + bought - sold; bought = limit-init - max_buy, sold = limit+init - max_sell
        bought = (self.position_limit - self.initial_position) - self.max_allowed_buy_volume
        sold = (self.position_limit + self.initial_position) - self.max_allowed_sell_volume
        pos_after = self.initial_position + bought - sold
        
        if self.direction > 0 and pos_after < soft_cap:
            qty = min(primary_target, int(soft_cap - pos_after))
            remaining = qty
            for sp, sv in self.market_sell_orders.items():
                if sp > self.fair + HP_TAKE_OFFSET or remaining <= 0:
                    break
                volume = min(sv, remaining)
                self.bid(sp, volume)
                remaining -= volume
        elif self.direction < 0 and pos_after > -soft_cap:
            qty = min(primary_target, int(soft_cap + pos_after))
            remaining = qty
            for bp, bv in self.market_buy_orders.items():
                if bp < self.fair - HP_TAKE_OFFSET or remaining <= 0:
                    break
                volume = min(bv, remaining)
                self.ask(bp, volume)
                remaining -= volume
    
    
    def take_aggressive_mr(self):
        # at extreme |z| (>=2.5 sd), fire up to aggr_max_take across the full mean side
        if abs(self.initial_position) >= self.hard_cap:
            return
        if self.mid_price is None:
            return
        
        z = (self.mid_price - self.fair) / HP_STDEV_INIT # static sd source
        if abs(z) < HP_AGGR_Z_THRESH:
            return
        
        if z < 0:
            remaining = HP_AGGR_MAX_TAKE
            for sp, sv in self.market_sell_orders.items():
                if sp > self.fair or remaining <= 0:
                    break
                volume = min(sv, remaining)
                self.bid(sp, volume)
                remaining -= volume
        else:
            remaining = HP_AGGR_MAX_TAKE
            for bp, bv in self.market_buy_orders.items():
                if bp < self.fair or remaining <= 0:
                    break
                volume = min(bv, remaining)
                self.ask(bp, volume)
                remaining -= volume
    
    
    def quote_skewed(self):
        # MM layer with inventory-skewed sizing + MR boost + conviction boost
        if self.best_bid is None or self.best_ask is None or self.mid_price is None:
            return
        
        bought = (self.position_limit - self.initial_position) - self.max_allowed_buy_volume
        sold = (self.position_limit + self.initial_position) - self.max_allowed_sell_volume
        pos_after = self.initial_position + bought - sold
        
        bid_px = min(self.best_bid + 1, self.fair - 1)
        ask_px = max(self.best_ask - 1, self.fair + 1)
        if bid_px >= ask_px:
            return
        
        # inventory pull: if long, smaller bid / bigger ask
        ratio = pos_after / self.position_limit
        bm = max(0.0, 1.0 - HP_FLAT_PULL * ratio)
        sm = max(0.0, 1.0 + HP_FLAT_PULL * ratio)
        
        # mean-reversion boost on the side that pulls back to fair
        if self.mid_price < self.fair - HP_MR_THRESH:
            bm *= HP_MR_BOOST
        elif self.mid_price > self.fair + HP_MR_THRESH:
            sm *= HP_MR_BOOST
        
        # conviction boost on the directional side
        if self.conviction > 0:
            if self.direction > 0:
                bm *= 1.0 + HP_MM_BOOST * self.conviction
            elif self.direction < 0:
                sm *= 1.0 + HP_MM_BOOST * self.conviction
        
        self.bid(bid_px, int(round(HP_QSIZE * bm)))
        self.ask(ask_px, int(round(HP_QSIZE * sm)))
    
    
    def get_orders(self):
        if len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        self.unwind_hard_cap()
        self.take_primary()
        self.take_aggressive_mr()
        self.quote_skewed()
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# VEV_5200 / Anchor-Divergence Trader (legacy, kept for reference)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class Vev5200Trader(AbstractTrader):
    # Not used in the current mix — VEV_5200 is in Z_TAKE_SYMBOLS.
    # Retained so we can A/B back to it without re-importing.
    def __init__(self, state, prints, new_trader_data):
        super().__init__(VEV_5200_SYMBOL, state, prints, new_trader_data)
        
        self.fair_price = self.get_full_depth_mid()
        self.anchor, self.anchor_n = self.update_anchor()
    
    
    def update_anchor(self):
        n = self.last_traderData.get(self.name + "_an", 0)
        s = self.last_traderData.get(self.name + "_as", 0.0)
        
        if self.mid_price is not None:
            n += 1
            s += self.mid_price
        
        self.new_trader_data[self.name + "_an"] = n
        self.new_trader_data[self.name + "_as"] = s
        return (s / n if n > 0 else None), n
    
    
    def take_divergence(self):
        if VEV_5200_DIVERGE_THRESHOLD <= 0 or self.anchor_n < ANCHOR_WARMUP or self.anchor is None:
            return
        
        diverge = self.mid_price - self.anchor
        if abs(diverge) < VEV_5200_DIVERGE_THRESHOLD:
            return
        
        if diverge > 0 and self.initial_position > -MAX_DIVERGE_POS:
            room = self.initial_position + MAX_DIVERGE_POS
            qty = min(DIVERGE_TAKE_SIZE, room)
            remaining = qty
            for bp, bv in self.market_buy_orders.items():
                if remaining <= 0:
                    break
                volume = min(bv, remaining)
                self.ask(bp, volume)
                remaining -= volume
        elif diverge < 0 and self.initial_position < MAX_DIVERGE_POS:
            room = MAX_DIVERGE_POS - self.initial_position
            qty = min(DIVERGE_TAKE_SIZE, room)
            remaining = qty
            for sp, sv in self.market_sell_orders.items():
                if remaining <= 0:
                    break
                volume = min(sv, remaining)
                self.bid(sp, volume)
                remaining -= volume
    
    
    def take_fair(self):
        for sp, sv in self.market_sell_orders.items():
            if sp >= self.fair_price - ANCHOR_TAKE_WIDTH:
                break
            self.bid(sp, sv)
        
        for bp, bv in self.market_buy_orders.items():
            if bp <= self.fair_price + ANCHOR_TAKE_WIDTH:
                break
            self.ask(bp, bv)
    
    
    def quote_midpoint(self):
        if self.best_bid is None or self.best_ask is None:
            return
        bid_px = min(math.floor((self.fair_price + self.best_bid) / 2), self.best_ask - 1)
        ask_px = max(math.ceil((self.fair_price + self.best_ask) / 2), self.best_bid + 1)
        if bid_px < ask_px:
            self.bid(bid_px, VEV_5200_QSIZE)
            self.ask(ask_px, VEV_5200_QSIZE)
    
    
    def get_orders(self):
        if self.fair_price is None or len(self.market_buy_orders) == 0 or len(self.market_sell_orders) == 0:
            return {self.name: self.orders}
        
        self.take_divergence()
        self.take_fair()
        self.quote_midpoint()
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Buy-and-Hold Trader (deep-OTM lottery vouchers)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class BuyAndHoldTrader(AbstractTrader):
    # Mid pinned around 0.5, sd ~= 0 so z-take can't trade them.
    # Just sweep the asks and hold to the position limit.
    def __init__(self, name, state, prints, new_trader_data):
        super().__init__(name, state, prints, new_trader_data)
    
    def get_orders(self):
        self.buy_and_hold()
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Trader Class
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class Trader:
    
    def bid(self):
        return 1 # should hit median
    
    def run(self, state: TradingState):
        
        # Symbol -> trader class. ZTakeTrader and BuyAndHoldTrader take (name, state, ...)
        # because they handle multiple symbols; HydrogelTrader is fixed to its symbol.
        product_traders = {HYDROGEL_SYMBOL: HydrogelTrader}
        for sym in Z_TAKE_SYMBOLS:
            product_traders[sym] = ZTakeTrader
        for sym in BUY_AND_HOLD_SYMBOLS:
            product_traders[sym] = BuyAndHoldTrader
        
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
                # multi-symbol traders take name first; HydrogelTrader does not
                if product_trader in (ZTakeTrader, BuyAndHoldTrader):
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