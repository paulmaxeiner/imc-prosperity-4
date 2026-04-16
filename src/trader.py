from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import json

# Logger
from logger import Logger
logger = Logger()

# Configuration Variables & Symbols
from config import *

# Traders
from static import EmeraldTrader
from dynamic import TomatoTrader



class Trader:
    def run(self, state: TradingState):
        
        product_traders = {
            EMERALD_SYMBOL: EmeraldTrader,
            TOMATO_SYMBOL: TomatoTrader
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
        try: final_trader_data = json.dumps(new_trader_data)
        except: pass
        
        # Debugging / Backtesting
        print_dict(final_trader_data)
        logger.flush(state, result, conversions, final_trader_data)
        
        
        return result, conversions, final_trader_data