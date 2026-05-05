# IMC Prosperity 4 Challenge
## Team Name: AndromedaAlpha
## Final Position: TBD

This repository contains code for my submissions to the IMC Prosperity 4 trading competition, organized by round.

Big thanks to IMC for organizing such a fun competition! I learned a lot about market making, order book structure, asset pricing strategies, and game theory. I look forward to coming back next year!

### Leaderboard

| Round | Overall | Algorithmic | Manual | Country (US) |
|-|-|-|-|-|
| 1 | 562 | 735 | 1 | 158 |
| 2 | 721 | 320 | 375 | 175 |
| 3 | 543 | 448 | 669 | 167 |
| 4 |  | ~587 | ~1800 | 98 |

## Round 0 (Tutorial Round)
This challenge involed EMERALDS and TOMATOES. EMERALDS followed a static price of 10000 XIRECS, while TOMATOES was more volatile. I employed a strategy of first market taking any arbitrage prices, then market making to tighten the spread and capture any profitable trades from other bots. The fair price for EMERALDS was set at exactly 10000, while the fair price for TOMATOES was determined by the mid wall price (i.e. the mid of the outermost bid/asks, that stays more constant and reduces volatility).

## Round 1


This challenge involved two products: ASH_COATED_OSMIUM and INTARIAN_PEPPER_ROOT. 

---
**INTARIAN_PEPPER_ROOT**

INTARIAN_PEPPER_ROOT followed a stricly positive linear pattern:
![](assets/pepper_price.png)
Assuming this trend would continue, buying and holding would be far more profitable than trying to scalp as a market maker. I tried to find a way to do market-making while holding >80% of the position limit, but the performance was not improving. I shifted my focus to find a way to optimize the initial purchase to get the best possible price at the beginning of each trading day. I found that buying at a premium of no more than 7 (MAX_PREMIUM) at the beginning of the trading day yielded the best performance per the backtester, rather than arbitrarily taking every ask at t=0.

---
**ASH_COATED_OSMIUM**

ASH_COATED_OSMIUM was noisy, and mean-reverting around a price of 10000:
<div align="center">
    <img src="assets/osmium_price.png" alt="osmium price" width="750">
</div>

Similar to the strategy for TOMATOES, I used the wall mid price to first market take, then market make, rather than trying to guess the next movement. In retrospect, I probably should've implemented some sort of inventory management system to mitigate the risk, but the core strategy worked pretty well.