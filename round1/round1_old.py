class PepperTrader(AbstractTrader):
    def __init__(self, state, prints, new_trader_data):
        super().__init__(PEPPER_SYMBOL, state, prints, new_trader_data)
    
    def get_orders(self):
        # # try to buy as much as possible at beginning
        
        fair_price = None
        if self.last_traderData:
            fair_price = self.last_traderData["fp"] + 0.1
            self.new_trader_data["fp"] = fair_price
        else:
            if self.wall_mid:
                fair_price = round(self.wall_mid,-3)
                self.new_trader_data["fp"] = fair_price
        
        if self.market_sell_orders is not None:
            if self.initial_position < self.position_limit:
                for sp, sv in self.market_sell_orders.items():
                    self.bid(sp, sv)
                
                if self.best_ask:
                    if self.best_ask > fair_price+1:
                        self.ask(self.best_ask-1, 20)
                    
            
        if fair_price is not None:
            for bp, bv in self.market_buy_orders.items():
                if bp > fair_price+5 and self.initial_position-bv > 0:
                    self.ask(bp, bv)
                    if self.best_ask:
                        self.bid(self.best_ask, bv)
        
        # ts = self.state.timestamp
        # fair_price = 0.001*ts + 10000
        
        # if self.wall_mid is not None:
        #     self.take_market(fair_price)
        #     self.make_market(fair_price)


        return {self.name: self.orders}