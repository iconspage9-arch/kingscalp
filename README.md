# 🤖 Claude AI Trading Bot — Multi-Pair Funded Challenge

Fully automated trading bot powered by Claude AI.
Runs 24/7 on Render. Trades a $5,000 funded challenge account across 20+ pairs.

---

## What It Does
- Checks every 15 minutes
- Scans **20+ pairs**: Gold, Silver, Forex majors/minors, Indices
- Full top-down analysis: 4H bias → 1H structure → 15M entry
- Indicators: EMA20/50/200, RSI14, ATR14, MACD, Bollinger Bands, Stochastic RSI
- Claude scores each setup out of 10 — only trades confidence 7+
- Picks the **best setup** across all pairs each cycle
- Minimum 1:2 Risk:Reward on every trade
- Halts automatically when challenge is passed ($5,500)
- Enforces:
  - ✅ $250 max daily loss
  - ✅ $500 max total drawdown
  - ✅ $500 profit target (auto-halt when hit)
  - ✅ 1% risk per trade
  - ✅ Only 1 trade open at a time

---

## Pairs Traded
| Category | Pairs |
|----------|-------|
| Metals | XAU/USD (Gold), XAG/USD (Silver) |
| Forex Majors | EUR/USD, GBP/USD, USD/JPY, USD/CHF, AUD/USD, USD/CAD, NZD/USD |
| Forex Minors | EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/AUD, GBP/AUD |
| Indices | US30, NAS100, SPX500, UK100, DE30 |

---

## Step 1 — Open OANDA Demo Account

1. Go to https://www.oanda.com
2. Click "Try a Free Demo"
3. Sign up (no deposit needed)
4. Set starting balance to **$5,000**
5. Go to **Manage API Access** → Generate a **Personal Access Token**
6. Copy your **Account ID** (top left of dashboard — looks like: 001-001-1234567-001)

---

## Step 2 — Get Anthropic API Key

1. Go to https://platform.anthropic.com
2. Sign up → **API Keys** → Create new key
3. Copy it — you only see it once

> At ~$0.003 per 20-pair scan cycle, $5 credit = ~1,600 cycles (~16 days of 15-min checks)

---

## Step 3 — Deploy to Render

1. Go to https://render.com → sign up free
2. Click **New** → **Background Worker**
3. Upload these files (or push to a GitHub repo and connect it)
4. Render detects `render.yaml` automatically

### Environment Variables (set in Render dashboard):
| Key | Value |
|-----|-------|
| `OANDA_API_KEY` | Your OANDA personal access token |
| `OANDA_ACCOUNT_ID` | Your OANDA account ID |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `OANDA_ENV` | `practice` (default) or `live` |

All other settings are pre-configured in `render.yaml`.

---

## Step 4 — Monitor on Your Phone

1. Download the **OANDA** app (iOS or Android)
2. Log in with your demo account
3. See every trade Claude places in real time
4. Check balance, open trades, P&L history — all there

---

## Challenge Rules Summary
| Rule | Value |
|------|-------|
| Starting balance | $5,000 |
| Profit target | +$500 (auto-halt at $5,500) |
| Max total drawdown | -$500 (halt at $4,500) |
| Max daily loss | -$250 |
| Risk per trade | 1% of balance |
| Min Risk:Reward | 1:2 |

---

## Files Explained
| File | Purpose |
|------|---------|
| `main.py` | Bot loop — scans pairs every 15 min, places best trade |
| `oanda_connector.py` | OANDA API — data, indicators, order placement |
| `analyst.py` | Claude analysis — scores setups, picks best pair |
| `risk_manager.py` | Enforces all challenge rules, tracks daily P&L |
| `requirements.txt` | Python packages |
| `render.yaml` | Render deployment config |

---

## ⚠️ Important Notes

- Defaults to **demo account** — `OANDA_ENV=practice`
- To use live: set `OANDA_ENV=live` in Render (your responsibility)
- Past performance does not guarantee future results
- Claude will say NO_TRADE often — that's good, it's protecting the account
- Each 15-min cycle scans all pairs and picks only the best setup
- Bot logs every scan, every decision, every trade

---

## Viewing Logs

In Render dashboard → click your service → click **Logs**

You'll see:
```
⏱  Cycle started at 2026-03-27 14:00:00 UTC
💰 Balance: $5,042.00 | Profit: +$42.00 / $500 target | Daily loss: $0 / $250 ...
🔍 Scanning 20 pairs for setups...
   XAU_USD: BUY | Confidence: 8/10 | RR: 2.4 | Pattern: BOS retest + MACD cross
   EUR_USD: NO TRADE — ranging, no clear structure break
   ...
✅ Trade placed! | XAU_USD BUY | ID: 12345 | Price: 3241.500 | Units: 15
```
