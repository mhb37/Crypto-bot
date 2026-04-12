import requests
import time
from datetime import datetime

TELEGRAM_TOKEN   = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"
CHECK_INTERVAL_MINUTES = 30

COINS = {
    "BTC": ("bitcoin",  "BTC"),
    "XRP": ("ripple",   "XRP"),
    "ETH": ("ethereum", "ETH"),
}

def get_prices(coin_id):
    url = "https://api.coingecko.com/api/v3/coins/" + coin_id + "/market_chart"
    params = {"vs_currency": "usd", "days": "5", "interval": "hourly"}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        prices  = [p[1] for p in data["prices"]]
        volumes = [v[1] for v in data["total_volumes"]]
        return prices, volumes
    except Exception as e:
        print("Erreur CoinGecko " + coin_id + ": " + str(e))
        return None, None

def get_current_price(coin_id):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        price  = data[coin_id]["usd"]
        change = data[coin_id].get("usd_24h_change", 0)
        return price, round(change, 2)
    except:
        return None, None

def ema(prices, period):
    k = 2.0 / (period + 1)
    val = prices[0]
    result = [val]
    for p in prices[1:]:
        val = p * k + val * (1 - k)
        result.append(val)
    return result

def calc_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * (period - 1) + gains[i]) / period
        al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)

def calc_macd(prices):
    e12 = ema(prices, 12)
    e26 = ema(prices, 26)
    macd_line   = [a - b for a, b in zip(e12, e26)]
    signal_line = ema(macd_line, 9)
    histogram   = [a - b for a, b in zip(macd_line, signal_line)]
    return round(macd_line[-1], 2), round(signal_line[-1], 2), round(histogram[-1], 2)

def calc_bollinger(prices, period=20):
    recent = prices[-period:]
    mid    = sum(recent) / period
    std    = (sum((x - mid)**2 for x in recent) / period) ** 0.5
    return round(mid + 2*std, 2), round(mid, 2), round(mid - 2*std, 2)

def calc_atr(prices, period=14):
    trs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
    return sum(trs[-period:]) / period

def calc_stochastic(prices, period=14):
    recent = prices[-period:]
    low14  = min(recent)
    high14 = max(recent)
    if high14 == low14:
        return 50.0
    return round((prices[-1] - low14) / (high14 - low14) * 100, 1)

def calc_volume_trend(volumes):
    if len(volumes) < 10:
        return "neutre"
    avg_recent = sum(volumes[-5:]) / 5
    avg_old    = sum(volumes[-10:-5]) / 5
    if avg_recent > avg_old * 1.2:
        return "en hausse"
    elif avg_recent < avg_old * 0.8:
        return "en baisse"
    return "stable"

def support_resistance(prices, lookback=24):
    recent = prices[-lookback:]
    return round(min(recent), 2), round(max(recent), 2)

def bar(value, min_v, max_v, length=10):
    pct = max(0, min(1, (value - min_v) / (max_v - min_v) if max_v != min_v else 0.5))
    filled = int(pct * length)
    return "[" + "#" * filled + "-" * (length - filled) + "]"

def analyze(ticker):
    coin_id, label = COINS[ticker]
    prices, volumes = get_prices(coin_id)
    if not prices or len(prices) < 50:
        return None
    price, change_24h = get_current_price(coin_id)
    if not price:
        price = prices[-1]
        change_24h = 0
    rsi                    = calc_rsi(prices)
    macd_v, signal_v, hist = calc_macd(prices)
    bb_up, bb_mid, bb_low  = calc_bollinger(prices)
    atr                    = calc_atr(prices)
    stoch                  = calc_stochastic(prices)
    vol_trend              = calc_volume_trend(volumes)
    support, resistance    = support_resistance(prices)
    ema20  = round(ema(prices, 20)[-1], 2)
    ema50  = round(ema(prices, 50)[-1], 2)
    ema100 = round(ema(prices, 100)[-1], 2)
    score = 0
    reasons_long  = []
    reasons_short = []
    if rsi < 25:
        score += 3
        reasons_long.append("RSI survente extreme (" + str(rsi) + ")")
    elif rsi < 35:
        score += 2
        reasons_long.append("RSI survente (" + str(rsi) + ")")
    elif rsi < 45:
        score += 1
    elif rsi > 75:
        score -= 3
        reasons_short.append("RSI surachat extreme (" + str(rsi) + ")")
    elif rsi > 65:
        score -= 2
        reasons_short.append("RSI surachat (" + str(rsi) + ")")
    elif rsi > 55:
        score -= 1
    if hist > 0 and macd_v > signal_v:
        score += 2
        reasons_long.append("MACD croisement haussier")
    elif hist > 0:
        score += 1
    elif hist < 0 and macd_v < signal_v:
        score -= 2
        reasons_short.append("MACD croisement baissier")
    elif hist < 0:
        score -= 1
    if ema20 > ema50 > ema100:
        score += 2
        reasons_long.append("Tendance haussiere (EMA20>50>100)")
    elif ema20 > ema50:
        score += 1
        reasons_long.append("EMA20 au-dessus EMA50")
    elif ema20 < ema50 < ema100:
        score -= 2
        reasons_short.append("Tendance baissiere (EMA20<50<100)")
    elif ema20 < ema50:
        score -= 1
    if price < bb_low:
        score += 2
        reasons_long.append("Prix sous bande Bollinger basse")
    elif price < bb_mid:
        score += 1
    elif price > bb_up:
        score -= 2
        reasons_short.append("Prix sur bande Bollinger haute")
    elif price > bb_mid:
        score -= 1
    if stoch < 20:
        score += 2
        reasons_long.append("Stochastique survente (" + str(stoch) + ")")
    elif stoch > 80:
        score -= 2
        reasons_short.append("Stochastique surachat (" + str(stoch) + ")")
    if abs(price - support) / price < 0.015:
        score += 2
        reasons_long.append("Prix sur support (" + str(support) + ")")
    if abs(price - resistance) / price < 0.015:
        score -= 2
        reasons_short.append("Prix sur resistance (" + str(resistance) + ")")
    if vol_trend == "en hausse" and score > 0:
        score += 1
        reasons_long.append("Volume confirme la hausse")
    elif vol_trend == "en hausse" and score < 0:
        score -= 1
        reasons_short.append("Volume confirme la baisse")
    if score >= 5:
        direction = "LONG"
        force = "TRES FORT"
    elif score >= 3:
        direction = "LONG"
        force = "FORT"
    elif score >= 1:
        direction = "LONG"
        force = "FAIBLE"
    elif score <= -5:
        direction = "SHORT"
        force = "TRES FORT"
    elif score <= -3:
        direction = "SHORT"
        force = "FORT"
    elif score <= -1:
        direction = "SHORT"
        force = "FAIBLE"
    else:
        direction = "NEUTRE"
        force = ""
    atr_mult = 1.5
    if direction == "LONG":
        sl  = round(price - atr * atr_mult, 2)
        tp1 = round(price + atr * 1.5, 2)
        tp2 = round(price + atr * 3.0, 2)
        rr  = round((tp2 - price) / (price - sl), 1) if price != sl else 0
    elif direction == "SHORT":
        sl  = round(price + atr * atr_mult, 2)
        tp1 = round(price - atr * 1.5, 2)
        tp2 = round(price - atr * 3.0, 2)
        rr  = round((price - tp2) / (sl - price), 1) if price != sl else 0
    else:
        sl = tp1 = tp2 = rr = None
    return {
        "ticker": ticker, "price": price, "change_24h": change_24h,
        "rsi": rsi, "macd_hist": hist, "ema20": ema20, "ema50": ema50,
        "bb_up": bb_up, "bb_mid": bb_mid, "bb_low": bb_low,
        "stoch": stoch, "support": support, "resistance": resistance,
        "vol_trend": vol_trend, "direction": direction, "force": force,
        "score": score, "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
        "reasons_long": reasons_long, "reasons_short": reasons_short,
    }

def format_message(s):
    now = datetime.now().strftime("%d/%m %H:%M")
    if s["direction"] == "LONG":
        header  = "SIGNAL LONG " + s["force"]
        reasons = s["reasons_long"]
    elif s["direction"] == "SHORT":
        header  = "SIGNAL SHORT " + s["force"]
        reasons = s["reasons_short"]
    else:
        header  = "NEUTRE"
        reasons = []
    change_arrow = "+" if s["change_24h"] >= 0 else ""
    score_bar = bar(s["score"] + 8, 0, 16)
    msg = (
        "================================\n"
        " " + s["ticker"] + "/USDT   " + now + "\n"
        "================================\n"
        "\n"
        " " + header + "\n"
        "\n"
        "Prix   : " + str(s["price"]) + " USD\n"
        "24h    : " + change_arrow + str(s["change_24h"]) + "%\n"
        "Score  : " + score_bar + " " + str(s["score"]) + "/8\n"
    )
    if s["sl"] and s["tp1"]:
        msg += (
            "\n"
            "--------------------------------\n"
            " NIVEAUX DE TRADE\n"
            "--------------------------------\n"
            "Entree : " + str(s["price"]) + "\n"
            "TP1    : " + str(s["tp1"]) + "\n"
            "TP2    : " + str(s["tp2"]) + "\n"
            "SL     : " + str(s["sl"]) + "\n"
            "R/R    : 1:" + str(s["rr"]) + "\n"
        )
    msg += (
        "\n"
        "--------------------------------\n"
        " INDICATEURS\n"
        "--------------------------------\n"
        "RSI    " + bar(s["rsi"], 0, 100) + " " + str(s["rsi"]) + "\n"
        "Stoch  " + bar(s["stoch"], 0, 100) + " " + str(s["stoch"]) + "\n"
        "MACD   : " + ("+" if s["macd_hist"] > 0 else "") + str(s["macd_hist"]) + "\n"
        "EMA20  : " + str(s["ema20"]) + "\n"
        "EMA50  : " + str(s["ema50"]) + "\n"
        "BB bas : " + str(s["bb_low"]) + "\n"
        "BB haut: " + str(s["bb_up"]) + "\n"
        "\n"
        "--------------------------------\n"
        " NIVEAUX CLES\n"
        "--------------------------------\n"
        "Support    : " + str(s["support"]) + "\n"
        "Resistance : " + str(s["resistance"]) + "\n"
        "Volume     : " + s["vol_trend"] + "\n"
    )
    if reasons:
        msg += (
            "\n"
            "--------------------------------\n"
            " RAISONS DU SIGNAL\n"
            "--------------------------------\n"
        )
        for r in reasons[:5]:
            msg += "- " + r + "\n"
    msg += (
        "\n"
        "================================\n"
        "Pas un conseil financier\n"
        "================================"
    )
    return msg

def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("Telegram: " + str(r.status_code))
        return r.status_code == 200
    except Exception as e:
        print("Erreur Telegram: " + str(e))
        return False

def run():
    print("Bot demarre")
    send_telegram(
        "================================\n"
        " CRYPTO SIGNAL BOT DEMARRE\n"
        "================================\n"
        "Surveillance : BTC / XRP / ETH\n"
        "Intervalle   : " + str(CHECK_INTERVAL_MINUTES) + " min\n"
        "Indicateurs  : RSI, MACD, EMA,\n"
        "Bollinger, Stochastique\n"
        "================================"
    )
    last_signals = {"BTC": None, "XRP": None, "ETH": None}
    while True:
        print("[" + datetime.now().strftime("%H:%M") + "] Analyse...")
        for ticker in COINS:
            signal = analyze(ticker)
            if signal is None:
                continue
            print(ticker + ": " + signal["direction"] + " score=" + str(signal["score"]) + " RSI=" + str(signal["rsi"]))
            if signal["force"] in ("FORT", "TRES FORT"):
                key = signal["direction"] + signal["force"]
                if key != last_signals[ticker]:
                    send_telegram(format_message(signal))
                    last_signals[ticker] = key
                    time.sleep(2)
        print("Prochain check dans " + str(CHECK_INTERVAL_MINUTES) + " min")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run()
