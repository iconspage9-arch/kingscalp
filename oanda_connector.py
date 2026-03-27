"""
OANDA Connector — handles all communication with OANDA API
Pulls candle data, calculates indicators, places and manages trades
Supports multi-pair scanning
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime

OANDA_API_KEY    = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")

# ✅ FIXED: Demo (practice) URL is now the default
# To use live trading, set OANDA_ENV=live in your environment variables
OANDA_ENV      = os.environ.get("OANDA_ENV", "practice")
OANDA_BASE_URL = (
    "https://api-fxtrade.oanda.com/v3"
    if OANDA_ENV == "live"
    else "https://api-fxpractice.oanda.com/v3"
)

HEADERS = {
    "Authorization": f"Bearer {OANDA_API_KEY}",
    "Content-Type":  "application/json"
}

# All pairs the bot can trade — it will scan all and pick the best setup
TRADEABLE_PAIRS = [
    # Gold & Silver
    "XAU_USD", "XAG_USD",
    # Forex Majors
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD",
    # Forex Minors
    "EUR_GBP", "EUR_JPY", "GBP_JPY", "AUD_JPY", "EUR_AUD", "GBP_AUD",
    # Indices (via CFD on OANDA)
    "US30_USD", "NAS100_USD", "SPX500_USD", "UK100_GBP", "DE30_EUR",
]

GRANULARITY_MAP = {
    "15M": "M15",
    "1H":  "H1",
    "4H":  "H4",
    "1D":  "D"
}


# ─────────────────────────────────────────────
# ACCOUNT
# ─────────────────────────────────────────────

def get_account_info():
    url = f"{OANDA_BASE_URL}/accounts/{OANDA_ACCOUNT_ID}/summary"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    acc = r.json()["account"]
    return {
        "balance":     float(acc["balance"]),
        "equity":      float(acc["NAV"]),
        "unrealized":  float(acc["unrealizedPL"]),
        "margin_used": float(acc["marginUsed"]),
    }


# ─────────────────────────────────────────────
# MARKET DATA + INDICATORS
# ─────────────────────────────────────────────

def get_candles(symbol, timeframe="1H", count=100):
    gran = GRANULARITY_MAP.get(timeframe, "H1")
    url  = f"{OANDA_BASE_URL}/instruments/{symbol}/candles"
    params = {
        "granularity": gran,
        "count":       count,
        "price":       "M"  # midpoint
    }
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    candles = r.json()["candles"]

    rows = []
    for c in candles:
        if c["complete"]:
            rows.append({
                "time":   c["time"],
                "open":   float(c["mid"]["o"]),
                "high":   float(c["mid"]["h"]),
                "low":    float(c["mid"]["l"]),
                "close":  float(c["mid"]["c"]),
                "volume": int(c["volume"])
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"])
    return df


def calculate_indicators(df):
    """Add EMA20, EMA50, RSI14, ATR14, MACD, BB to dataframe"""
    if len(df) < 50:
        return df

    # EMAs
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI 14
    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    # ATR 14
    high_low   = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close  = (df["low"]  - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"]  = true_range.ewm(com=13, adjust=False).mean()

    # MACD (12, 26, 9)
    ema12        = df["close"].ewm(span=12, adjust=False).mean()
    ema26        = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]   = ema12 - ema26
    df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["hist"]   = df["macd"] - df["signal"]

    # Bollinger Bands (20, 2)
    rolling_mean  = df["close"].rolling(20).mean()
    rolling_std   = df["close"].rolling(20).std()
    df["bb_upper"] = rolling_mean + (2 * rolling_std)
    df["bb_lower"] = rolling_mean - (2 * rolling_std)
    df["bb_mid"]   = rolling_mean

    # Stochastic RSI (14)
    rsi_min = df["rsi"].rolling(14).min()
    rsi_max = df["rsi"].rolling(14).max()
    df["stoch_rsi"] = (df["rsi"] - rsi_min) / (rsi_max - rsi_min + 1e-10) * 100

    # Higher highs / lower lows (last 20 candles) for structure detection
    df["swing_high"] = df["high"].rolling(5, center=True).max() == df["high"]
    df["swing_low"]  = df["low"].rolling(5, center=True).min() == df["low"]

    # Trend
    df["trend"] = df["ema20"] > df["ema50"]

    return df


def get_market_summary(symbol):
    """Pull multi-timeframe data + indicators for Claude to analyze"""
    summary = {}
    for tf in ["4H", "1H", "15M"]:
        try:
            df = get_candles(symbol, tf, 200)
            if df.empty or len(df) < 52:
                return None
            df = calculate_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # Recent swing highs/lows for structure context
            recent = df.tail(30)
            swing_highs = recent[recent["swing_high"]]["high"].tolist()[-3:]
            swing_lows  = recent[recent["swing_low"]]["low"].tolist()[-3:]

            summary[tf] = {
                "time":           str(last["time"]),
                "open":           round(last["open"], 5),
                "high":           round(last["high"], 5),
                "low":            round(last["low"], 5),
                "close":          round(last["close"], 5),
                "prev_close":     round(prev["close"], 5),
                "ema20":          round(last["ema20"], 5),
                "ema50":          round(last["ema50"], 5),
                "ema200":         round(last["ema200"], 5),
                "rsi":            round(float(last["rsi"]), 2),
                "atr":            round(float(last["atr"]), 5),
                "macd":           round(float(last["macd"]), 6),
                "macd_signal":    round(float(last["signal"]), 6),
                "macd_hist":      round(float(last["hist"]), 6),
                "bb_upper":       round(float(last["bb_upper"]), 5),
                "bb_lower":       round(float(last["bb_lower"]), 5),
                "bb_mid":         round(float(last["bb_mid"]), 5),
                "stoch_rsi":      round(float(last["stoch_rsi"]), 2),
                "trend":          "BULLISH" if last["trend"] else "BEARISH",
                "candles_above_ema20": int((df["close"].tail(10) > df["ema20"].tail(10)).sum()),
                "swing_highs":    [round(x, 5) for x in swing_highs],
                "swing_lows":     [round(x, 5) for x in swing_lows],
            }
        except Exception as e:
            return None  # Skip this pair if data fetch fails

    return summary


# ─────────────────────────────────────────────
# OPEN POSITIONS
# ─────────────────────────────────────────────

def get_open_trades(symbol=None):
    url = f"{OANDA_BASE_URL}/accounts/{OANDA_ACCOUNT_ID}/openTrades"
    r   = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    trades = r.json().get("trades", [])
    if symbol:
        return [t for t in trades if t["instrument"] == symbol]
    return trades


def get_closed_trades_today():
    """Get trades closed today to update P&L tracking"""
    from datetime import date, timezone
    today_str = date.today().isoformat() + "T00:00:00Z"
    url = f"{OANDA_BASE_URL}/accounts/{OANDA_ACCOUNT_ID}/trades"
    params = {"state": "CLOSED", "count": 50}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    trades = r.json().get("trades", [])
    today_trades = [
        t for t in trades
        if t.get("closeTime", "") >= today_str
    ]
    return today_trades


# ─────────────────────────────────────────────
# PLACE ORDER
# ─────────────────────────────────────────────

def place_order(symbol, direction, units, sl_price, tp_price):
    """
    direction: 'buy' or 'sell'
    units: will be made positive for buy, negative for sell
    """
    units = abs(units) if direction == "buy" else -abs(units)

    order_body = {
        "order": {
            "type":       "MARKET",
            "instrument": symbol,
            "units":      str(units),
            "stopLossOnFill": {
                "price": str(round(sl_price, 5))
            },
            "takeProfitOnFill": {
                "price": str(round(tp_price, 5))
            },
            "timeInForce":  "FOK",
            "positionFill": "DEFAULT"
        }
    }

    url = f"{OANDA_BASE_URL}/accounts/{OANDA_ACCOUNT_ID}/orders"
    r   = requests.post(url, headers=HEADERS, json=order_body, timeout=15)

    if r.status_code not in [200, 201]:
        return {"success": False, "error": r.text}

    data = r.json()
    fill = data.get("orderFillTransaction", {})
    return {
        "success":   True,
        "trade_id":  fill.get("tradeOpened", {}).get("tradeID"),
        "price":     fill.get("price"),
        "units":     units,
        "direction": direction,
        "sl":        sl_price,
        "tp":        tp_price,
    }
