from AbstractTrader import AbstractTrader
from config import *

class TomatoTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(TOMATO_SYMBOL, state, prints, new_trader_data)
    
    def get_orders(self):
        if self.wall_mid is not None:
            fair_price = self.wall_mid

            self.take_market(fair_price)
            self.make_market(fair_price)
        
        return {self.name: self.orders}