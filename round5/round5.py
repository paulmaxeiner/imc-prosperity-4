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

# Round 5 position limit per the brief: 10 for ALL 50 products
POS_LIMIT = 10

# EWMA-based mean-reversion target overlay (per product)
EWMA_ALPHA = 0.93   # span ~30 ticks
MR_K = 1.5          # target shift per stddev of deviation
MR_CAP = 8          # max |mr_adj| in position units (don't flip base direction)
MR_MIN_VAR = 4.0

# SNACKPACK pair-trade overlay (multi-product)
PAIR_EWMA_ALPHA = 0.998
PAIR_Z_THRESHOLD = 2.0
PAIR_MAX_LEG_SIZE = 5
PAIR_WARMUP_TICKS = 500
PAIR_MIN_DEV = 5.0  # require this much abs-deviation EWMA before trading

# Cointegrated SNACKPACK pairs: (a, b, op, label)
#   op="+" -> trade the SUM (anticorrelated, sum is stationary)
#   op="-" -> trade the DIFF (positively correlated, diff is stationary)
SNACKPACK_PAIRS = [
    ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA",   "+", "choc_van"),
    ("SNACKPACK_RASPBERRY", "SNACKPACK_STRAWBERRY", "+", "ras_str"),
    ("SNACKPACK_PISTACHIO", "SNACKPACK_RASPBERRY", "+", "pis_ras"),
    ("SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "-", "pis_str"),
]
SNACKPACK_PRODUCTS = {"SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA",
                      "SNACKPACK_RASPBERRY", "SNACKPACK_STRAWBERRY",
                      "SNACKPACK_PISTACHIO"}

# Per-product MM config
# Tier 1 (target=±10, full limit): strong directional drift, ride it
# Tier 2 (target=±5, half limit): smaller drift, half-limit so MM still works
# Pair targets override target_pos for SNACKPACK products at runtime
CFG = {
    # MM-only / trend-ride
    "TRANSLATOR_ECLIPSE_CHARCOAL": {"size": 6, "min_half": 2, "inv_skew": 4,  "target_pos": +10},
    "TRANSLATOR_ASTRO_BLACK":      {"size": 6, "min_half": 2, "inv_skew": 4,  "target_pos": +10},
    "ROBOT_LAUNDRY":               {"size": 6, "min_half": 2, "inv_skew": 4,  "target_pos": -10},
    "SNACKPACK_PISTACHIO":         {"size": 6, "min_half": 4, "inv_skew": 6,  "target_pos":   0},
    "SNACKPACK_RASPBERRY":         {"size": 6, "min_half": 4, "inv_skew": 6,  "target_pos":   0},
    "SNACKPACK_STRAWBERRY":        {"size": 6, "min_half": 4, "inv_skew": 6,  "target_pos":   0},

    # Tier 1 directional
    "PANEL_1X2":                   {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": -10},
    "UV_VISOR_AMBER":              {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": -10},
    "PEBBLES_M":                   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "SLEEP_POD_SUEDE":             {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "MICROCHIP_RECTANGLE":         {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "GALAXY_SOUNDS_SOLAR_FLAMES":  {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "TRANSLATOR_GRAPHITE_MIST":    {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": +10},
    
    # Spread legs (paired)
    "PANEL_4X4":                   {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": +10},
    "PEBBLES_XL":                  {"size": 4, "min_half": 4, "inv_skew": 15, "target_pos": +10},
    "GALAXY_SOUNDS_DARK_MATTER":   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "PANEL_2X2":                   {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": -10},
    "ROBOT_IRONING":               {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "ROBOT_VACUUMING":             {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": +10},
    
    # Diversification tier (mostly tier-1 sized, some tier-2)
    "UV_VISOR_RED":                {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": +10},
    "UV_VISOR_ORANGE":             {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": +10},
    "UV_VISOR_YELLOW":             {"size": 3, "min_half": 2, "inv_skew": 12, "target_pos":  -5},
    "GALAXY_SOUNDS_PLANETARY_RINGS":{"size":4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "PANEL_1X4":                   {"size": 4, "min_half": 2, "inv_skew": 15, "target_pos": -10},
    
    # Trend-following adds (sweeps)
    "SLEEP_POD_COTTON":            {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "PEBBLES_S":                   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "MICROCHIP_OVAL":              {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "UV_VISOR_MAGENTA":            {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "PANEL_2X4":                   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "ROBOT_MOPPING":               {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "MICROCHIP_TRIANGLE":          {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "TRANSLATOR_SPACE_GRAY":       {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "SLEEP_POD_LAMB_WOOL":         {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "MICROCHIP_SQUARE":            {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "OXYGEN_SHAKE_GARLIC":         {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "OXYGEN_SHAKE_MINT":           {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "OXYGEN_SHAKE_MORNING_BREATH": {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "PEBBLES_XS":                  {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "TRANSLATOR_VOID_BLUE":        {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "SLEEP_POD_NYLON":             {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "MICROCHIP_CIRCLE":            {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "SNACKPACK_CHOCOLATE":         {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "OXYGEN_SHAKE_EVENING_BREATH": {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "SLEEP_POD_POLYESTER":         {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": +10},
    "GALAXY_SOUNDS_BLACK_HOLES":   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "PEBBLES_L":                   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "SNACKPACK_VANILLA":           {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
    "GALAXY_SOUNDS_SOLAR_WINDS":   {"size": 4, "min_half": 3, "inv_skew": 15, "target_pos": -10},
}

# Position limits (uniform for round 5)
POSITION_LIMITS = {sym: POS_LIMIT for sym in CFG}


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
        if quantity <= 0: return # don't emit zero-volume orders
        order = Order(self.name, int(price), quantity)
        self.max_allowed_buy_volume -= quantity
        self.orders.append(order)
        
    def ask(self, price, volume):
        quantity = min(abs(volume), self.max_allowed_sell_volume)
        if quantity <= 0: return # don't emit zero-volume orders
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
# MM Trader (universal market-maker, used for all CFG products)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class MmTrader(AbstractTrader):
    # Inventory-skewed MM around microprice fair, with EWMA-based MR target overlay
    # SNACKPACK target_pos is overridden by pair-trade signal (computed in Trader.run)
    def __init__(self, name, state, prints, new_trader_data, base_target):
        super().__init__(name, state, prints, new_trader_data)
        
        cfg = CFG.get(self.name, {})
        self.size = cfg.get("size", 4)
        self.min_half = cfg.get("min_half", 2)
        self.inv_skew = cfg.get("inv_skew", 15)
        self.base_target = base_target # may be the cfg target_pos or pair-derived
        
        self.fair = self.get_micro_price() # fair value (volume-weighted)
        self.book_spread = self.get_spread()
        
        self.ewma_mid, self.ewma_var = self.update_ewma()
        self.target_pos = self.get_target_pos()
    
    
    def update_ewma(self):
        # EWMA of mid + EWMA of squared deviation -> online mean and variance
        prev_m = self.last_traderData.get(self.name + "_em", None)
        prev_v = self.last_traderData.get(self.name + "_ev", 0.0)
        
        if self.fair is None:
            self.new_trader_data[self.name + "_em"] = prev_m
            self.new_trader_data[self.name + "_ev"] = prev_v
            return prev_m, prev_v
        
        if prev_m is None:
            ewma_mid = self.fair
            ewma_var = 0.0
        else:
            ewma_mid = EWMA_ALPHA * prev_m + (1 - EWMA_ALPHA) * self.fair
            ewma_var = EWMA_ALPHA * prev_v + (1 - EWMA_ALPHA) * (self.fair - ewma_mid) ** 2
        
        self.new_trader_data[self.name + "_em"] = ewma_mid
        self.new_trader_data[self.name + "_ev"] = ewma_var
        return ewma_mid, ewma_var
    
    
    def get_target_pos(self):
        # Lean target against deviation from EWMA, bounded so we don't flip the base direction
        if self.fair is None or self.ewma_var is None or self.ewma_var <= MR_MIN_VAR:
            mr_adj = 0.0
        else:
            z = (self.fair - self.ewma_mid) / math.sqrt(self.ewma_var)
            mr_adj = max(-MR_CAP, min(MR_CAP, -MR_K * z))
        
        return max(-POS_LIMIT, min(POS_LIMIT, self.base_target + mr_adj))
    
    
    def get_skewed_fair(self):
        # Push fair AWAY from current position (toward target) so quotes lean toward fills that move us closer
        deviation = self.initial_position - self.target_pos
        inv_shift = self.inv_skew * deviation / POS_LIMIT
        return self.fair - inv_shift
    
    
    def take_cross(self, skewed_fair, half):
        # If the resting book is offering inside our fair, eat it directly
        # Returns (ask_take_qty, bid_take_qty) so we can size residual quotes
        ask_take = bid_take = 0
        
        if self.best_ask is not None and self.best_ask <= skewed_fair - half:
            avail = self.market_sell_orders[self.best_ask]
            qty = min(avail, self.size)
            if qty > 0:
                self.bid(self.best_ask, qty)
                ask_take = qty
        
        if self.best_bid is not None and self.best_bid >= skewed_fair + half:
            avail = self.market_buy_orders[self.best_bid]
            qty = min(avail, self.size)
            if qty > 0:
                self.ask(self.best_bid, qty)
                bid_take = qty
        
        return ask_take, bid_take
    
    
    def quote_residual(self, skewed_fair, half, ask_take, bid_take):
        # Quote symmetrically around skewed fair for whatever size remains after takes
        bid_px = math.floor(skewed_fair - half)
        ask_px = math.ceil(skewed_fair + half)
        if ask_px <= bid_px:
            ask_px = bid_px + 1
        
        quote_buy = max(0, self.size - ask_take)
        quote_sell = max(0, self.size - bid_take)
        
        self.bid(bid_px, quote_buy)
        self.ask(ask_px, quote_sell)
    
    
    def get_orders(self):
        if self.fair is None or self.book_spread is None or self.book_spread <= 0:
            return {self.name: self.orders}
        
        skewed_fair = self.get_skewed_fair()
        half = max(self.min_half, self.book_spread / 4.0)
        
        ask_take, bid_take = self.take_cross(skewed_fair, half)
        self.quote_residual(skewed_fair, half, ask_take, bid_take)
        
        return {self.name: self.orders}



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# SNACKPACK Pair Coordinator (multi-product overlay)
#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
class SnackpackPairs:
    # Computes per-product target_pos contributions from cointegrated SNACKPACK pairs
    # Run once per tick before MmTrader instances are created; results override their base_target
    def __init__(self, state, last_traderData, new_trader_data):
        self.state = state
        self.last_traderData = last_traderData
        self.new_trader_data = new_trader_data
        
        self.tick_count = self.last_traderData.get("_pair_tick", 0) + 1
        self.new_trader_data["_pair_tick"] = self.tick_count
        
        self.targets = self.compute_targets()
    
    
    def get_micro(self, sym):
        # standalone microprice for a product (mirror of MmTrader.get_micro_price but on a different symbol)
        od = self.state.order_depths.get(sym)
        if od is None or not od.buy_orders or not od.sell_orders:
            return None
        bb = max(od.buy_orders.keys())
        ba = min(od.sell_orders.keys())
        bv = od.buy_orders[bb]
        av = abs(od.sell_orders[ba])
        tot = bv + av
        if tot <= 0:
            return (bb + ba) / 2.0
        return (bb * av + ba * bv) / tot
    
    
    def compute_targets(self):
        # For each pair, EWMA-track the spread and abs-deviation, derive z, contribute to per-product target
        targets = {p: 0.0 for p in SNACKPACK_PRODUCTS}
        active = self.tick_count >= PAIR_WARMUP_TICKS
        
        for a, b, op, label in SNACKPACK_PAIRS:
            mid_a = self.get_micro(a)
            mid_b = self.get_micro(b)
            if mid_a is None or mid_b is None:
                continue
            
            spread = (mid_a + mid_b) if op == "+" else (mid_a - mid_b)
            
            prev_m = self.last_traderData.get("_pair_m_" + label, spread)
            prev_ad = self.last_traderData.get("_pair_ad_" + label, 0.0)
            
            new_m = PAIR_EWMA_ALPHA * prev_m + (1 - PAIR_EWMA_ALPHA) * spread
            dev = abs(spread - new_m)
            new_ad = PAIR_EWMA_ALPHA * prev_ad + (1 - PAIR_EWMA_ALPHA) * dev
            
            self.new_trader_data["_pair_m_" + label] = new_m
            self.new_trader_data["_pair_ad_" + label] = new_ad
            
            if not active or new_ad < PAIR_MIN_DEV:
                continue # skip until EWMAs settle
            
            z = (spread - new_m) / new_ad # abs-dev as sigma proxy
            if abs(z) < PAIR_Z_THRESHOLD:
                continue
            
            # Position scales with z above threshold, capped
            leg = min(PAIR_MAX_LEG_SIZE, int(abs(z) - PAIR_Z_THRESHOLD + 1) * 2)
            sign = -1 if z > 0 else +1 # +1 = long, -1 = short
            
            if op == "+":
                # spread too high -> short both; spread too low -> long both
                targets[a] += sign * leg
                targets[b] += sign * leg
            else:
                # diff pair: spread too high -> short a, long b
                targets[a] += sign * leg
                targets[b] -= sign * leg
        
        # clamp to position limit
        for p in targets:
            targets[p] = int(round(max(-POS_LIMIT, min(POS_LIMIT, targets[p]))))
        return targets
    
    
    def get_target(self, sym):
        return self.targets.get(sym, 0)



#–––––––––––––––––––––––––––––––––––––––––––––––––––––––
# Trader Class
#–––––––––––––––––––––––––––––––––––––––––––––––––––––
class Trader:
    
    def bid(self):
        return 0 # round 2 manual auction, irrelevant in round 5
    
    def run(self, state: TradingState):
        
        prints = {}
        def print_dict(dict_to_print: dict):
            try: print(json.dumps(dict_to_print, indent=4))
            except: pass
        
        result = {}
        conversions = 0
        new_trader_data = {}
        
        # Read previous traderData once (each trader also reads it but we need it here for the pair coordinator)
        last_traderData = {}
        try: last_traderData = json.loads(state.traderData) if state.traderData else {}
        except: pass
        
        # Run pair coordinator first; SNACKPACK products will read its target via base_target
        pair_coord = SnackpackPairs(state, last_traderData, new_trader_data)
        
        # Each product runs MmTrader; SNACKPACK uses pair-derived target instead of cfg target_pos
        for symbol in CFG:
            if symbol not in state.order_depths:
                continue
            
            cfg = CFG[symbol]
            if symbol in SNACKPACK_PRODUCTS:
                base_target = pair_coord.get_target(symbol)
            else:
                base_target = cfg.get("target_pos", 0)
            
            trader = MmTrader(symbol, state, prints, new_trader_data, base_target)
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