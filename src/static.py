from AbstractTrader import AbstractTrader
from config import *

class EmeraldTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(EMERALD_SYMBOL, state, prints, new_trader_data) # inherits functions from AbstractTrader
        
        
    def get_orders(self):
        if self.wall_mid is not None:
            fair_price = 10000

            # MARKET TAKING
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
            
            # MARKET MAKING
            # Base Cases
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
        
        return {self.name: self.orders}