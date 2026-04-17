
'''
Functions to help with graphing during data capsule EDA
'''


import matplotlib.pyplot as plt

def time_series_plot(prices, trades, title="", show_trades=True):
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(prices['timestamp'], prices['mid_price'], label='Price')
    ax.plot(prices['timestamp'], prices['bid_price_1'], label='bid_price_3')
    ax.scatter(trades['timestamp'], trades['price'], color='red', label='Trades', s=10)
    if title:
        ax.set_title(title)
    else:
        ax.set_title('Time Series Plot of '+prices['product'].iloc[0])
    
    
    
    
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price')
    plt.ylim(9955,10050)
    ax.legend()
    plt.show()
    

COLORS = {
    "ask_price_3": "#9B0F06",
    "ask_price_2": "#FF5555",
    "ask_price_1": "#FF937E",
    "bid_price_1": "#C1E59F",
    "bid_price_2": "#A3D78A",
    "bid_price_3": "#346739",
    "mid_price": "#0011FF",
    "wall_mid": "#FF00FF"
}

def get_wall_mid(prices):
    bid_wall = max(prices['bid_price_2'] * prices['bid_volume_2'], prices['bid_price_3'] * prices['bid_volume_3'])
    ask_wall = max(prices['ask_price_2'] * prices['ask_volume_2'], prices['ask_price_3'] * prices['ask_volume_3'])
    mid_price = (bid_wall + ask_wall) / (bid_wall + ask_wall) * (prices['bid_price_1'] + prices['ask_price_1']) / 2
    return mid_price
    

def order_book_plot(prices, trades, xmin=0, xmax=20000, title="", show_trades=True):
    fig, ax = plt.subplots(figsize=(12, 6))
    for i in COLORS:
        ax.scatter(
            prices['timestamp'],
            prices[i],
            label=i,
            s=prices[i.replace("price", "volume")].abs().fillna(0) * 10,
            alpha=0.4,
            color=COLORS[i]
        )
        
        
    
    if title:
        ax.set_title(title)
    else:
        ax.set_title('Time Series Plot of '+prices["product"].iloc[0])
        
    filled_marker_style = dict(linestyle=':',
                           color='darkgrey',
                           markerfacecolor='tab:blue',
                           markerfacecoloralt='lightsteelblue',
                           markeredgecolor='black')
        
    if show_trades:
        for trade in trades.itertuples():
            time = trade.timestamp
            price = trade.price
            prices_df = prices[prices['timestamp']==time]
            mark = None
            fill_style = 'none'
            #print(prices['timestamp'])
            if trade.price < int(prices_df['mid_price'].iloc[0]):
                mark = 'v'
            else:
                mark = '^'
            ax.plot(time, price, marker = mark, markersize=trade.quantity*3, fillstyle=fill_style, **filled_marker_style)

    


    #plt.axhline(10000, color='gray', linestyle='--', label='Reference Price')
    ax.plot(prices['timestamp'], prices['mid_price'], color='blue', linestyle='--', label='Mid Price')
    #ax.plot(prices['timestamp'], prices['mid_price'].rolling(window=7).mean(), color='purple', linestyle='-', label='Mid Price (Rolling)')
    #ax.plot(prices['timestamp'], prices.apply(get_wall_mid, axis=1), color='orange', linestyle='-', label='Wall Mid Price')
    
    
    
    
    ax.set_xlabel('Timestamp')
    ax.set_ylabel('Price')
    plt.xlim(xmin, xmax)

    plt.ylim(prices.iloc[int(xmin/100):int(xmax/100)]['mid_price'].min()-5, prices.iloc[int(xmin/100):int(xmax/100)]['mid_price'].max()+5)
    ax.legend()
    plt.show()
