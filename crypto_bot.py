"""
╔══════════════════════════════════════════════════════════════╗
║          CRYPTO SIGNAL BOT - BTC / XRP / ETH               ║
║     Analyse technique + Alertes Telegram 24/7               ║
║                                                              ║
║  CONFIGURATION REQUISE (Section CONFIG ci-dessous) :        ║
║  1. TELEGRAM_TOKEN  → Token de ton bot Telegram             ║
║  2. TELEGRAM_CHAT_ID → Ton Chat ID Telegram                 ║
╚══════════════════════════════════════════════════════════════╝
"""

import requests
import time
import json
from datetime import datetime

# ──────────────────────────────────────────────
#  ⚙️  CONFIG — MODIFIE CES DEUX VALEURS
# ──────────────────────────────────────────────
TELEGRAM_TOKEN  = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"

CHECK_INTERVAL_MINUTES = 30
# ──────────────────────────────────────────────

SYMBOLS = {
    "BTC": "bitcoin",
    "XRP": "ripple",
    "ETH": "ethereum",
}

BINANCE_SYMBOLS = {
    "BTC": "BTCUSDT",
    "XRP": "XRPUSDT",
    "ETH": "ETHUSDT",
}

COINGECKO_IDS = {
    "BTCUSDT": "bitcoin",
    "XRPUSDT": "ripple",
    "ETHUSDT": "ethereum",
}

def get_klines(symbol, interval="1h", limit=100):
    cg_id = COINGECKO_IDS.get(symbol)
    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart"
    params = {"vs_currency": "usd", "days": "4", "interval": "hourly"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        prices = [p[1] for p in data["prices"]]
        closes = prices
        highs  = prices
        lows   = prices
        volumes = [v[1] for v in data["total_volumes"]]
        return closes, highs, lows, volumes
    except Exception as e:
        print(f"Erreur CoinGecko {symbol}: {e}")
        return None, None, None, None


def ema(prices, period):
    k = 2 / (period + 1)
    ema_values = [prices[0]]
    for p in prices[1:]:
        ema_values.append(p * k + ema_values[-1] * (1 - k))
    return ema_values

def calculate_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_macd(closes):
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd_line = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
    signal_line = ema(macd_line, 9)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line[-1], signal_line[-1], histogram[-1]

def calculate_bollinger(closes, period=20):
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    mid = sum(recent) / period
    std = (sum((x - mid) ** 2 for x in recent) / period) ** 0.5
    return round(mid + 2 * std, 4), round(mid, 4), round(mid - 2 * std, 4)

def calculate_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return sum(trs[-period:]) / period

def support_resistance(highs, lows, lookback=20):
    resistance = max(highs[-lookback:])
    support    = min(lows[-lookback:])
    return round(support, 4), round(resistance, 4)

def generate_signal(ticker):
    closes, highs, lows, volumes = get_klines(BINANCE_SYMBOLS[ticker])
    if closes is None:
        return None

    price   = closes[-1]
    rsi     = calculate_rsi(closes)
    macd_v, signal_v, hist = calculate_macd(closes)
    bb_up, bb_mid, bb_low  = calculate_bollinger(closes)
    atr     = calculate_atr(highs, lows, closes)
    support, resistance = support_resistance(highs, lows)

    ema20 = ema(closes, 20)[-1]
    ema50 = ema(closes, 50)[-1]

    score = 0
    if rsi < 30: score += 2
    elif rsi < 40: score += 1
    elif rsi > 70: score -= 2
    elif rsi > 60: score -= 1

    if hist > 0 and macd_v > signal_v: score += 1
    elif hist < 0 and macd_v < signal_v: score -= 1

    if ema20 > ema50: score += 1
    else: score -= 1

    if bb_low and price < bb_low: score += 2
    elif bb_up and price > bb_up: score -= 2

    if abs(price - support) / price < 0.02: score += 1
    if abs(price - resistance) / price < 0.02: score -= 1

    if score >= 3:
        direction = "🟢 LONG"
        strength  = "FORT" if score >= 5 else "MODÉRÉ"
    elif score <= -3:
        direction = "🔴 SHORT"
        strength  = "FORT" if score <= -5 else "MODÉRÉ"
    else:
        direction = "⚪ NEUTRE"
        strength  = "FAIBLE"

    atr_mult = 1.5
    if "LONG" in direction:
        sl = round(price - atr * atr_mult, 4)
        tp = round(price + atr * atr_mult * 2, 4)
    elif "SHORT" in direction:
        sl = round(price + atr * atr_mult, 4)
        tp = round(price - atr * atr_mult * 2, 4)
    else:
        sl = tp = None

    return {
        "ticker": ticker, "price": price, "rsi": rsi,
        "macd": round(macd_v, 4), "macd_hist": round(hist, 4),
        "ema20": round(ema20, 4), "ema50": round(ema50, 4),
        "bb_up": bb_up, "bb_mid": bb_mid, "bb_low": bb_low,
        "support": support, "resistance": resistance,
        "atr": round(atr, 4), "direction": direction,
        "strength": strength, "score": score, "sl": sl, "tp": tp,
    }

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Erreur Telegram: {e}")
        return False

def format_message(s):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    sl_tp = ""
    if s["sl"] and s["tp"]:
        sl_tp = f"\n🎯 <b>TP :</b> {s['tp']} USDT\n🛑 <b>SL :</b> {s['sl']} USDT"
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{s['ticker']}/USDT</b> — {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Prix :</b> {s['price']} USDT\n"
        f"\n{s['direction']} ({s['strength']})\n"
        f"\n📈 <b>Indicateurs :</b>\n"
        f"  • RSI(14)    : {s['rsi']}\n"
        f"  • MACD hist  : {s['macd_hist']}\n"
        f"  • EMA20/50   : {s['ema20']} / {s['ema50']}\n"
        f"  • BB Low/Up  : {s['bb_low']} / {s['bb_up']}\n"
        f"\n📐 <b>Niveaux :</b>\n"
        f"  • Support    : {s['support']}\n"
        f"  • Résistance : {s['resistance']}"
        f"{sl_tp}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def run():
    print("🤖 Bot démarré — analyse toutes les", CHECK_INTERVAL_MINUTES, "minutes")
    send_telegram("🤖 <b>Crypto Signal Bot démarré !</b>\nSurveillance : BTC | XRP | ETH\n📊 Analyse toutes les " + str(CHECK_INTERVAL_MINUTES) + " minutes.")
    last_signals = {"BTC": None, "XRP": None, "ETH": None}
        


    while True:
        print(f"\n[{datetime.now().strftime('%H:%M')}] Analyse en cours...")
        for ticker in SYMBOLS:
            signal = generate_signal(ticker)
            if signal is None:
                continue
            print(f"  {ticker}: {signal['direction']} (score={signal['score']}, RSI={signal['rsi']})")
            if "NEUTRE" not in signal["direction"]:
                if signal["direction"] != last_signals[ticker]:
                    send_telegram(format_message(signal))
                    last_signals[ticker] = signal["direction"]
                    time.sleep(2)
        print(f"  ✅ Prochain check dans {CHECK_INTERVAL_MINUTES} min")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run()
