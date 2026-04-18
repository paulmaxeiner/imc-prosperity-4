
import numpy as np
import pandas as pd

def research(x):
    return 200_000 * np.log(1+x) / np.log(1 + 100)

def scale(x):
    return (7/100)*x

RANKS = {
    1: (100, 100),
    2: (95, 100),
    3: (80, 95),
    4: ()
    
}

def get_rank(x):
    #data = {'Score': [0,0,0, 1, 2, 2, 3, 4, 49, 50, 51, 52, 52, 53, 96, 85, 90, 100, 100]}
    rng = np.random.default_rng()
    samples = rng.normal(loc=50, scale=5.0, size=10000)
    #samples = np.concatenate([samples,[0,0,0,0,0,0,49,49,49,50,51,52,52,52,52,52,52,53,53,53,54,55,56,99,99,99,100,100,100]])
    samples = np.concatenate([samples,
                              [0]*10,
                              [49]*10,
                              [50]*500,
                              [51]*250,
                              [52]*300,
                              [98]*1
                              [99]*29,
                              [100]*100])
    samples = np.concatenate([samples,[x]])
    data = {'Score': sorted(samples)}
    df = pd.DataFrame(data)

    # Default ranking (average method, ascending)
    df['Default_Rank'] = df['Score'].rank()

    # Dense ranking (no gaps, descending)
    df['Min_Rank'] = df['Score'].rank(method='min', ascending=False)
    max_rank = df['Min_Rank'].max()
    min_rank = df['Min_Rank'].min()
    rank = df.query(f'Score=={x}')["Min_Rank"].max()
    return rank, max_rank
    

def speed(x):
    # highest speed = 0.9
    # lowest receives 0.1
    # Goal: slightly beat avg Nash
    # If equal investments get same rank, we need to predict the Nash equilibrium and invest slightly more in one category to get a higher rank and thus a higher return on that category.
    # returns not nescessarily to scale
    if x==0:
        return 0.1
    if x==100:
        return 0.9
    
    rank, max_rank = get_rank(x)
    #return rank
    return 0.8*((max_rank+1-rank)/max_rank) + 0.1


def PnL(pct_research, pct_scale, pct_speed):
    budget_used = ((pct_research+pct_scale+pct_speed)/100)*50_000
    res = research(pct_research)
    sca = scale(pct_scale)
    spe = speed(pct_speed)
    
    #print(f"Testing: ({pct_research,pct_scale,pct_speed})  | PnL = {int((res*sca*spe)-budget_used)}")
    
    return (res*sca*spe)-budget_used

#df = pd.DataFrame()

best = -1
best_d = (0,0,0)
# for r in range(1,100):
#     for sc in range (1, 100-r):
#         for sp in range(0,100-r-sc):
            
#             #nr = pd.DataFrame([{'pct_research': r, 'pct_scale': sc, 'pct_speed': sp, 'PnL': }])
            
#             profit = PnL(r,sc,sp)
            
#             # nr = pd.DataFrame([{'pct_research': r, 'pct_scale': sc, 'pct_speed': sp, 'PnL': profit}])
#             # df = pd.concat([df,nr], ignore_index=True)
#             #print(f"Testing: ({r,sc,sp})  | PnL = {int(PnL(r,sc,sp))}")
#             #print(profit)
#             if profit > best:
#                 best = profit
#                 best_d = (r,sp,sc)
#df.to_csv("manual_round.csv")
# print(best)
# print(best_d)


#print(speed(0))
print(get_rank(100)[0])

# prev = 0
# pnl_pr = 0
# for i in range(40,60):
#     sp_i = round(speed(i),2)
#     diff = round(sp_i - prev,2)
#     print(f"speed = {i} | rank = {get_rank(i)[0]} | speed_mult = {sp_i} | DIFF = {diff} PNL_d={round(PnL(10,10,sp_i)-pnl_pr,2)}")
#     prev = speed(i)
#     pnl_pr = PnL(10,10,speed(i))