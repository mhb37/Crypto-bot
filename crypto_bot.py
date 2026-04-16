import requests
import time
from datetime import datetime

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════
TELEGRAM_TOKEN   = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"

LEVIER           = 5
RISQUE_PCT       = 2.0

CHECK_INTERVAL_MINUTES = 30
PAUSE_WEEKEND    = True
HEURE_DEBUT      = 5    # 5h UTC = 7h Paris
HEURE_FIN        = 21   # 21h UTC = 23h Paris
# ═══════════════════════════════════════════

COINS = {
    "BTC": "bitcoin",
    "XRP": "ripple",
    "ETH": "ethereum",
}

def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("Telegram: " + str(r.status_code))
        return r.status_code == 200
    except Exception as e:
        print("Erreur Telegram: " + str(e))
        return False

def is_weekend():
    return datetime.now().weekday() >= 5

def is_heure_creuse():
    h = datetime.utcnow().hour
    return h < HEURE_DEBUT or h >= HEURE_FIN

def get_prices(coin_id, days=7):
    url = "https://api.coingecko.com/api/v3/coins/" + coin_id + "/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": "hourly"}
    for tentative in range(3):
        try:
            time.sleep(15)
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            if "prices" not in data:
                print("CoinGecko rate limit " + coin_id + " tentative " + str(tentative+1))
                time.sleep(60)
                continue
            prices  = [p[1] for p in data["prices"]]
            volumes = [v[1] for v in data["total_volumes"]]
            return prices, volumes
        except Exception as e:
            print("Erreur " + coin_id + ": " + str(e))
            time.sleep(30)
    return None, None

def get_current(coin_id):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data[coin_id]["usd"], round(data[coin_id].get("usd_24h_change", 0), 2)
    except:
        return None, None

def check_mouvement_brusque(coin_id, ticker, seuil_1h=2.0, seuil_4h=5.0):
    """Detecte les mouvements brusques de prix."""
    prices, _ = get_prices(coin_id, days=1)
    if not prices or len(prices) < 5:
        return None
    price_now = prices[-1]
    price_1h  = prices[-2]  if len(prices) >= 2  else price_now
    price_4h  = prices[-5]  if len(prices) >= 5  else price_now
    var_1h = round((price_now - price_1h) / price_1h * 100, 2)
    var_4h = round((price_now - price_4h) / price_4h * 100, 2)
    alertes = []
    if abs(var_1h) >= seuil_1h:
        direction = "HAUSSE" if var_1h > 0 else "BAISSE"
        alertes.append(("1H", var_1h, direction))
    if abs(var_4h) >= seuil_4h:
        direction = "HAUSSE" if var_4h > 0 else "BAISSE"
        alertes.append(("4H", var_4h, direction))
    if not alertes:
        return None
    return {
        "ticker":    ticker,
        "price":     price_now,
        "var_1h":    var_1h,
        "var_4h":    var_4h,
        "alertes":   alertes,
    }

def format_mouvement(m):
    now  = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    sign_1h = "+" if m["var_1h"] >= 0 else ""
    sign_4h = "+" if m["var_4h"] >= 0 else ""
    emoji_1h = "HAUSSE" if m["var_1h"] >= 0 else "BAISSE"
    emoji_4h = "HAUSSE" if m["var_4h"] >= 0 else "BAISSE"
    msg = (
        "================================\n"
        "  MOUVEMENT BRUSQUE DETECTE\n"
        "================================\n"
        "" + m["ticker"] + "/USDT   " + now + "\n"
        "Prix : " + str(m["price"]) + " USD\n"
        "\n"
        "1H : " + emoji_1h + " " + sign_1h + str(m["var_1h"]) + "%\n"
        "4H : " + emoji_4h + " " + sign_4h + str(m["var_4h"]) + "%\n"
        "\n"
    )
    for periode, var, direction in m["alertes"]:
        if abs(var) >= 8:
            msg += "ALERTE EXTREME sur " + periode + " !\n"
            msg += "Verifier les news immediatement.\n"
        elif abs(var) >= 5:
            msg += "Mouvement fort sur " + periode + ".\n"
            msg += "Opportunite ou risque a surveiller.\n"
        else:
            msg += "Mouvement notable sur " + periode + ".\n"
    msg += (
        "\n"
        "================================\n"
        "Pas un conseil financier\n"
        "================================"
    )
    return msg


def ema(prices, period):
    k = 2.0 / (period + 1)
    v = prices[0]
    res = [v]
    for p in prices[1:]:
        v = p * k + v * (1 - k)
        res.append(v)
    return res

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
    ml  = [a - b for a, b in zip(e12, e26)]
    sl  = ema(ml, 9)
    h   = [a - b for a, b in zip(ml, sl)]
    return round(ml[-1], 4), round(sl[-1], 4), round(h[-1], 4)

def calc_bollinger(prices, period=20):
    recent = prices[-period:]
    mid    = sum(recent) / period
    std    = (sum((x - mid)**2 for x in recent) / period) ** 0.5
    return round(mid + 2*std, 4), round(mid, 4), round(mid - 2*std, 4)

def calc_atr(prices, period=14):
    trs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
    return sum(trs[-period:]) / period

def calc_stoch(prices, period=14):
    recent = prices[-period:]
    lo, hi = min(recent), max(recent)
    if hi == lo:
        return 50.0
    return round((prices[-1] - lo) / (hi - lo) * 100, 1)

def calc_adx(prices, period=14):
    if len(prices) < period * 2:
        return 0
    pdm, mdm, trl = [], [], []
    for i in range(1, len(prices)):
        up   = prices[i] - prices[i-1]
        down = prices[i-1] - prices[i]
        pdm.append(up   if up > down and up > 0   else 0)
        mdm.append(down if down > up and down > 0 else 0)
        trl.append(abs(prices[i] - prices[i-1]))
    def smooth(d, p):
        s = sum(d[:p])
        r = [s]
        for v in d[p:]:
            s = s - s/p + v
            r.append(s)
        return r
    at = smooth(trl, period)
    ps = smooth(pdm, period)
    ms = smooth(mdm, period)
    dx = []
    for i in range(len(at)):
        if at[i] == 0:
            continue
        pdi = 100 * ps[i] / at[i]
        mdi = 100 * ms[i] / at[i]
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) != 0 else 0)
    if not dx:
        return 0
    return round(sum(dx[-period:]) / period, 1)

def calc_rsi_divergence(prices):
    if len(prices) < 40:
        return None
    rsi_recent = calc_rsi(prices[-20:])
    rsi_old    = calc_rsi(prices[-40:-20])
    price_now  = prices[-1]
    price_old  = prices[-21]
    if price_now < price_old and rsi_recent > rsi_old + 5:
        return "HAUSSIERE"
    if price_now > price_old and rsi_recent < rsi_old - 5:
        return "BAISSIERE"
    return None

def calc_fibonacci(prices, lookback=50):
    recent = prices[-lookback:]
    high   = max(recent)
    low    = min(recent)
    diff   = high - low
    return {
        "0.236": round(high - diff * 0.236, 4),
        "0.382": round(high - diff * 0.382, 4),
        "0.500": round(high - diff * 0.500, 4),
        "0.618": round(high - diff * 0.618, 4),
    }

def calc_volume_trend(volumes):
    if len(volumes) < 10:
        return "stable"
    ar = sum(volumes[-5:]) / 5
    ao = sum(volumes[-10:-5]) / 5
    if ar > ao * 1.2:
        return "en hausse"
    if ar < ao * 0.8:
        return "en baisse"
    return "stable"

def detect_pattern(prices):
    if len(prices) < 3:
        return None
    c1, c2, c3 = prices[-3], prices[-2], prices[-1]
    if c1 > c2 and c3 > c2 and (c3 - c2) > (c1 - c2) * 0.5:
        return "Marteau (rebond probable)"
    if c1 < c2 and c3 < c2 and (c2 - c3) > (c2 - c1) * 0.5:
        return "Etoile filante (retournement probable)"
    if c1 > c2 and c3 > c1:
        return "Englobante haussiere"
    if c1 < c2 and c3 < c1:
        return "Englobante baissiere"
    return None

def support_resistance(prices, lookback=24):
    recent = prices[-lookback:]
    return round(min(recent), 4), round(max(recent), 4)

def analyze_tf(prices, volumes):
    if not prices or len(prices) < 50:
        return None
    price              = prices[-1]
    rsi                = calc_rsi(prices)
    mv, sv, hist       = calc_macd(prices)
    bb_up, bb_mid, bbl = calc_bollinger(prices)
    stoch              = calc_stoch(prices)
    adx                = calc_adx(prices)
    vol                = calc_volume_trend(volumes)
    sup, res           = support_resistance(prices)
    e20                = ema(prices, 20)[-1]
    e50                = ema(prices, 50)[-1]
    score = 0
    if rsi < 25:   score += 3
    elif rsi < 35: score += 2
    elif rsi < 45: score += 1
    elif rsi > 75: score -= 3
    elif rsi > 65: score -= 2
    elif rsi > 55: score -= 1
    if hist > 0 and mv > sv:   score += 2
    elif hist > 0:              score += 1
    elif hist < 0 and mv < sv: score -= 2
    elif hist < 0:              score -= 1
    if e20 > e50:   score += 1
    elif e20 < e50: score -= 1
    if price < bbl:      score += 2
    elif price < bb_mid: score += 1
    elif price > bb_up:  score -= 2
    elif price > bb_mid: score -= 1
    if stoch < 20:   score += 2
    elif stoch > 80: score -= 2
    if abs(price - sup) / price < 0.015: score += 2
    if abs(price - res) / price < 0.015: score -= 2
    if vol == "en hausse" and score > 0: score += 1
    elif vol == "en hausse" and score < 0: score -= 1
    return {
        "score": score, "rsi": rsi, "hist": round(hist, 4),
        "stoch": stoch, "adx": adx, "e20": round(e20, 4),
        "e50": round(e50, 4), "bb_up": bb_up, "bb_low": bbl,
        "sup": sup, "res": res, "vol": vol, "price": price,
    }

def analyze(ticker):
    coin_id = COINS[ticker]
    p1h, v1h = get_prices(coin_id, days=5)
    p4h, v4h = get_prices(coin_id, days=14)
    p1d, v1d = get_prices(coin_id, days=60)
    if not p1h:
        return None
    p4h_s = p4h[::4]  if p4h else None
    v4h_s = v4h[::4]  if v4h else None
    p1d_s = p1d[::24] if p1d else None
    v1d_s = v1d[::24] if v1d else None
    tf1h = analyze_tf(p1h, v1h)
    tf4h = analyze_tf(p4h_s, v4h_s)
    tf1d = analyze_tf(p1d_s, v1d_s)
    if not tf1h:
        return None
    s1h = tf1h["score"] if tf1h else 0
    s4h = tf4h["score"] if tf4h else 0
    s1d = tf1d["score"] if tf1d else 0
    score_global = round(s1d * 0.40 + s4h * 0.35 + s1h * 0.25, 1)
    confluence = (s1h > 0 and s4h > 0 and s1d > 0) or (s1h < 0 and s4h < 0 and s1d < 0)
    adx = tf1h["adx"]
    tendance = adx >= 20
    divergence = calc_rsi_divergence(p1h)
    if divergence == "HAUSSIERE" and score_global > 0:
        score_global = round(score_global + 1, 1)
    elif divergence == "BAISSIERE" and score_global < 0:
        score_global = round(score_global - 1, 1)
    pattern = detect_pattern(p1h)
    fibs    = calc_fibonacci(p1h)
    confiance = min(100, int(abs(score_global) / 8 * 100))
    if not confluence: confiance = int(confiance * 0.6)
    if not tendance:   confiance = int(confiance * 0.7)
    if divergence:     confiance = min(100, confiance + 10)
    if score_global >= 3 and confluence and tendance:
        direction, force = "LONG",  "TRES FORT" if confiance >= 75 else "FORT"
    elif score_global >= 2 and confluence:
        direction, force = "LONG",  "FORT"
    elif score_global >= 1:
        direction, force = "LONG",  "FAIBLE"
    elif score_global <= -3 and confluence and tendance:
        direction, force = "SHORT", "TRES FORT" if confiance >= 75 else "FORT"
    elif score_global <= -2 and confluence:
        direction, force = "SHORT", "FORT"
    elif score_global <= -1:
        direction, force = "SHORT", "FAIBLE"
    else:
        direction, force = "NEUTRE", ""
    price, change = get_current(coin_id)
    if not price:
        price  = p1h[-1]
        change = 0
    atr = calc_atr(p1h)
    if direction == "LONG":
        sl  = round(price - atr * 1.5, 4)
        tp1 = round(price + atr * 1.5, 4)
        tp2 = round(price + atr * 3.0, 4)
        rr  = round((tp2 - price) / (price - sl), 1) if price != sl else 0
    elif direction == "SHORT":
        sl  = round(price + atr * 1.5, 4)
        tp1 = round(price - atr * 1.5, 4)
        tp2 = round(price - atr * 3.0, 4)
        rr  = round((price - tp2) / (sl - price), 1) if price != sl else 0
    else:
        sl = tp1 = tp2 = rr = None
    return {
        "ticker": ticker, "price": price, "change": change,
        "direction": direction, "force": force,
        "score": score_global, "confiance": confiance,
        "confluence": confluence, "tendance": tendance, "adx": adx,
        "divergence": divergence, "pattern": pattern, "fibs": fibs,
        "tf1h": tf1h, "tf4h": tf4h, "tf1d": tf1d,
        "s1h": s1h, "s4h": s4h, "s1d": s1d,
        "sl": sl, "tp1": tp1, "tp2": tp2, "rr": rr,
    }

def pbar(v, lo=0, hi=100, n=8):
    pct = max(0, min(1, (v - lo) / (hi - lo) if hi != lo else 0.5))
    f = int(pct * n)
    return "[" + "=" * f + "-" * (n - f) + "]"

def tf_label(score):
    if score >= 2:    return "LONG  "
    elif score <= -2: return "SHORT "
    else:             return "RANGE "

def format_signal(s):
    now  = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    sign = "+" if s["change"] >= 0 else ""
    h    = s["tf1h"]
    top  = (
        "================================\n"
        "  " + s["direction"] + " " + s["force"] + "\n"
        "================================\n"
    )
    conf_bar = pbar(s["confiance"], 0, 100, 10)
    msg = top
    msg += (
        s["ticker"] + "/USDT   " + now + "\n"
        "Prix  : " + str(s["price"]) + " USD\n"
        "24h   : " + sign + str(s["change"]) + "%\n"
        "\n"
        "Confiance  " + conf_bar + " " + str(s["confiance"]) + "%\n"
        "Confluence : " + ("OUI" if s["confluence"] else "NON") + "\n"
        "ADX        : " + str(s["adx"]) + " (" + ("Fort" if s["adx"] >= 25 else "Moyen" if s["adx"] >= 20 else "Faible") + ")\n"
    )
    if s["divergence"]:
        msg += "Divergence : " + s["divergence"] + " (signal fort!)\n"
    if s["pattern"]:
        msg += "Pattern    : " + s["pattern"] + "\n"
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
            "Risque : " + str(RISQUE_PCT) + "% de ton capital\n"
        )
    msg += (
        "\n"
        "--------------------------------\n"
        " MULTI-TIMEFRAME\n"
        "--------------------------------\n"
        "1D : " + tf_label(s["s1d"]) + " score=" + str(s["s1d"]) + " RSI=" + str(s["tf1d"]["rsi"] if s["tf1d"] else "?") + "\n"
        "4H : " + tf_label(s["s4h"]) + " score=" + str(s["s4h"]) + " RSI=" + str(s["tf4h"]["rsi"] if s["tf4h"] else "?") + "\n"
        "1H : " + tf_label(s["s1h"]) + " score=" + str(s["s1h"]) + " RSI=" + str(h["rsi"]) + "\n"
    )
    if h:
        msg += (
            "\n"
            "--------------------------------\n"
            " INDICATEURS 1H\n"
            "--------------------------------\n"
            "RSI    " + pbar(h["rsi"]) + " " + str(h["rsi"]) + "\n"
            "Stoch  " + pbar(h["stoch"]) + " " + str(h["stoch"]) + "\n"
            "MACD   : " + ("+" if h["hist"] > 0 else "") + str(h["hist"]) + "\n"
            "EMA20  : " + str(h["e20"]) + "\n"
            "EMA50  : " + str(h["e50"]) + "\n"
            "BB bas : " + str(h["bb_low"]) + "\n"
            "BB haut: " + str(h["bb_up"]) + "\n"
            "Volume : " + h["vol"] + "\n"
            "\n"
            "Support    : " + str(h["sup"]) + "\n"
            "Resistance : " + str(h["res"]) + "\n"
        )
    if s["fibs"]:
        fibs = s["fibs"]
        msg += (
            "\n"
            "--------------------------------\n"
            " FIBONACCI\n"
            "--------------------------------\n"
            "0.236 : " + str(fibs["0.236"]) + "\n"
            "0.382 : " + str(fibs["0.382"]) + "\n"
            "0.500 : " + str(fibs["0.500"]) + "\n"
            "0.618 : " + str(fibs["0.618"]) + "\n"
        )
    if not s["confluence"]:
        msg += "\n! Timeframes non alignes\n  Signal moins fiable\n"
    if not s["tendance"]:
        msg += "\n! Tendance faible (ADX<20)\n  Eviter levier eleve\n"
    msg += (
        "\n"
        "================================\n"
        "Pas un conseil financier\n"
        "================================"
    )
    return msg

def format_range_alert(ticker, adx, price):
    now = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    return (
        "================================\n"
        "  ALERTE MARCHE EN RANGE\n"
        "================================\n"
        "" + ticker + "/USDT   " + now + "\n"
        "Prix : " + str(price) + " USD\n"
        "ADX  : " + str(adx) + " (trop faible)\n"
        "\n"
        "Marche sans tendance detecte.\n"
        "Ne pas ouvrir de position.\n"
        "Attendre ADX > 20.\n"
        "================================"
    )

def format_recap(signaux):
    now = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    msg = (
        "================================\n"
        "  RECAP DU JOUR\n"
        "================================\n"
        "" + now + "\n\n"
    )
    if not signaux:
        msg += "Aucun signal envoye aujourd'hui.\n"
    else:
        for s in signaux:
            msg += s["ticker"] + " : " + s["direction"] + " " + s["force"] + " (" + str(s["confiance"]) + "%)\n"
    msg += "================================"
    return msg

def run():
    print("Bot V3 demarre")
    send_telegram(
        "================================\n"
        "  CRYPTO SIGNAL BOT V3\n"
        "================================\n"
        "Paires     : BTC / XRP / ETH\n"
        "Timeframes : 1H + 4H + 1D\n"
        "Indicateurs: RSI, MACD, EMA,\n"
        "  Bollinger, Stoch, ADX,\n"
        "  Divergences, Fibonacci,\n"
        "  Patterns de bougies\n"
        "Risque/t   : " + str(RISQUE_PCT) + "% du capital\n"
        "Levier     : x" + str(LEVIER) + "\n"
        "Pause WE   : OUI\n"
        "Filtre     : 7h - 23h (Paris)\n"
        "================================"
    )
    last_signals     = {"BTC": None, "XRP": None, "ETH": None}
    range_alerted    = {"BTC": False, "XRP": False, "ETH": False}
    weekend_notified = False
    signaux_du_jour  = []
    last_recap_day   = -1
    last_mouvement   = {"BTC": 0, "XRP": 0, "ETH": 0}
last_check_mvt   = 0


    while True:
        now = datetime.utcnow()

        if now.hour == 18 and now.day != last_recap_day:  # 18h UTC = 20h Paris
            send_telegram(format_recap(signaux_du_jour))
            signaux_du_jour = []
            last_recap_day  = now.day

        if PAUSE_WEEKEND and is_weekend():
            if not weekend_notified:
                send_telegram(
                    "================================\n"
                    "  BOT EN PAUSE - WEEKEND\n"
                    "================================\n"
                    "Reprise automatique lundi 7h.\n"
                    "================================"
                )
                weekend_notified = True
            time.sleep(3600)
            continue
        else:
            weekend_notified = False
        # Check mouvements brusques toutes les 5 minutes
        if time.time() - last_check_mvt >= 300:
            last_check_mvt = time.time()
            for ticker in COINS:
                mvt = check_mouvement_brusque(COINS[ticker], ticker)
                if mvt:
                    key = str(int(abs(mvt["var_1h"]))) + str(int(abs(mvt["var_4h"])))
                    if key != last_mouvement[ticker]:
                        send_telegram(format_mouvement(mvt))
                        last_mouvement[ticker] = key
                        time.sleep(2)

        if is_heure_creuse():
            print("[" + now.strftime("%H:%M") + " UTC] Heure creuse — pause")
            time.sleep(CHECK_INTERVAL_MINUTES * 60)
            continue

        print("[" + now.strftime("%H:%M") + " UTC] Analyse en cours...")

        for ticker in COINS:
            signal = analyze(ticker)
            if signal is None:
                print(ticker + ": erreur donnees")
                continue
            print(ticker + ": " + signal["direction"] + " " + signal["force"] + " conf=" + str(signal["confiance"]) + "% ADX=" + str(signal["adx"]))

            if signal["adx"] < 15 and not range_alerted[ticker]:
                send_telegram(format_range_alert(ticker, signal["adx"], signal["price"]))
                range_alerted[ticker] = True
                time.sleep(2)
                continue
            elif signal["adx"] >= 15:
                range_alerted[ticker] = False

            if signal["force"] in ("FORT", "TRES FORT") and signal["confiance"] >= 50:
                key = signal["direction"] + signal["force"] + str(int(signal["confiance"] / 10))
                if key != last_signals[ticker]:
                    send_telegram(format_signal(signal))
                    last_signals[ticker] = key
                    signaux_du_jour.append({
                        "ticker": ticker, "direction": signal["direction"],
                        "force": signal["force"], "confiance": signal["confiance"],
                    })
                    time.sleep(3)

        print("Prochain check dans " + str(CHECK_INTERVAL_MINUTES) + " min")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run()
