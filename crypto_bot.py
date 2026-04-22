import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"

PAUSE_WEEKEND = True
HEURE_DEBUT = 5
HEURE_FIN = 21

MOTS_POSITIFS = [
    "bullish", "surge", "rally", "adoption", "approved", "record",
    "high", "gain", "rise", "buy", "etf", "institutional", "breakout",
    "hausse", "positif", "achat", "sommet", "accumulation", "support",
    "moon", "pump", "green", "up", "growth", "partnership", "launch"
]

MOTS_NEGATIFS = [
    "bearish", "crash", "drop", "ban", "hack", "scam", "fear",
    "sell", "low", "loss", "regulation", "fine", "lawsuit", "fraud",
    "baisse", "negatif", "vente", "chute", "liquidation", "dump",
    "red", "down", "warning", "risk", "investigation", "collapse"
]


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
    return datetime.utcnow().weekday() >= 5


def is_heure_creuse():
    h = datetime.utcnow().hour
    return h < HEURE_DEBUT or h >= HEURE_FIN


def get_historique_btc():
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "7", "interval": "hourly"}
    try:
        time.sleep(5)
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "prices" not in data:
            return None, None
        prices = [p[1] for p in data["prices"]]
        volumes = [v[1] for v in data["total_volumes"]]
        return prices, volumes
    except Exception as e:
        print("Erreur CoinGecko: " + str(e))
        return None, None


def get_prix_actuel():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin",
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_7d_change": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()["bitcoin"]
        return {
            "prix": round(data["usd"], 2),
            "var_24h": round(data.get("usd_24h_change", 0), 2),
            "var_7d": round(data.get("usd_7d_change", 0), 2),
        }
    except:
        return None


def get_news_btc():
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": "free",
        "currencies": "BTC",
        "filter": "hot",
        "public": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        titres = []
        for item in data.get("results", [])[:12]:
            titre = item.get("title", "")
            if titre:
                titres.append(titre)
        return titres
    except:
        return []


def analyser_sentiment_news(news):
    if not news:
        return 0, "Neutre", []
    score = 0
    news_resume = []
    for titre in news[:8]:
        t = titre.lower()
        pts = 0
        for mot in MOTS_POSITIFS:
            if mot in t:
                pts += 1
        for mot in MOTS_NEGATIFS:
            if mot in t:
                pts -= 1
        score += pts
        news_resume.append(titre[:80])
    if score >= 4:
        sentiment = "Tres positif"
    elif score >= 2:
        sentiment = "Positif"
    elif score <= -4:
        sentiment = "Tres negatif"
    elif score <= -2:
        sentiment = "Negatif"
    else:
        sentiment = "Neutre"
    return score, sentiment, news_resume


def analyser_prix(prices, volumes):
    if not prices or len(prices) < 24:
        return {}
    prix_now = prices[-1]
    prix_1h = prices[-2] if len(prices) >= 2 else prix_now
    prix_4h = prices[-5] if len(prices) >= 5 else prix_now
    prix_6h = prices[-7] if len(prices) >= 7 else prix_now
    prix_24h = prices[-25] if len(prices) >= 25 else prices[0]
    prix_48h = prices[-49] if len(prices) >= 49 else prices[0]
    prix_7j = prices[0]
    var_1h = round((prix_now - prix_1h) / prix_1h * 100, 2)
    var_4h = round((prix_now - prix_4h) / prix_4h * 100, 2)
    var_6h = round((prix_now - prix_6h) / prix_6h * 100, 2)
    var_24h = round((prix_now - prix_24h) / prix_24h * 100, 2)
    var_48h = round((prix_now - prix_48h) / prix_48h * 100, 2)
    var_7j = round((prix_now - prix_7j) / prix_7j * 100, 2)
    haut_24h = round(max(prices[-25:]), 2)
    bas_24h = round(min(prices[-25:]), 2)
    haut_7j = round(max(prices), 2)
    bas_7j = round(min(prices), 2)
    vol_recent = sum(volumes[-6:]) / 6 if len(volumes) >= 6 else 0
    vol_ancien = sum(volumes[-24:-6]) / 18 if len(volumes) >= 24 else vol_recent
    if vol_recent > vol_ancien * 1.15:
        tendance_vol = "en hausse"
        vol_score = 1
    elif vol_recent < vol_ancien * 0.85:
        tendance_vol = "en baisse"
        vol_score = -1
    else:
        tendance_vol = "stable"
        vol_score = 0
    hausse_count = sum(1 for i in range(1, min(25, len(prices))) if prices[-i] > prices[-i-1])
    if hausse_count > 14:
        momentum = "fortement haussier"
    elif hausse_count > 11:
        momentum = "haussier"
    elif hausse_count < 8:
        momentum = "baissier"
    elif hausse_count < 11:
        momentum = "legerement baissier"
    else:
        momentum = "neutre"
    score_prix = 0
    if var_1h > 0: score_prix += 1
    if var_1h > 1: score_prix += 1
    if var_4h > 0: score_prix += 1
    if var_24h > 0: score_prix += 1
    if var_24h > 2: score_prix += 1
    if var_7j > 0: score_prix += 1
    if var_1h < 0: score_prix -= 1
    if var_1h < -1: score_prix -= 1
    if var_4h < 0: score_prix -= 1
    if var_24h < 0: score_prix -= 1
    if var_24h < -2: score_prix -= 1
    if var_7j < 0: score_prix -= 1
    score_prix += vol_score
    recent_prices = prices[-48:] if len(prices) >= 48 else prices
    support = round(min(recent_prices), 0)
    resistance = round(max(recent_prices), 0)
    pct_support = round((prix_now - support) / support * 100, 1)
    pct_resistance = round((resistance - prix_now) / prix_now * 100, 1)
    return {
        "prix_now": prix_now,
        "var_1h": var_1h,
        "var_4h": var_4h,
        "var_6h": var_6h,
        "var_24h": var_24h,
        "var_48h": var_48h,
        "var_7j": var_7j,
        "haut_24h": haut_24h,
        "bas_24h": bas_24h,
        "haut_7j": haut_7j,
        "bas_7j": bas_7j,
        "tendance_vol": tendance_vol,
        "momentum": momentum,
        "score_prix": score_prix,
        "support": support,
        "resistance": resistance,
        "pct_support": pct_support,
        "pct_resistance": pct_resistance,
    }


def generer_conseil(score_prix, score_news, analyse):
    score_total = score_prix * 0.6 + score_news * 0.4
    raisons_long = []
    raisons_short = []
    raisons_attendre = []
    if analyse.get("var_24h", 0) > 2:
        raisons_long.append("Hausse de " + str(analyse["var_24h"]) + "% sur 24h")
    elif analyse.get("var_24h", 0) < -2:
        raisons_short.append("Baisse de " + str(analyse["var_24h"]) + "% sur 24h")
    if analyse.get("var_7j", 0) > 3:
        raisons_long.append("Tendance haussiere sur 7 jours (" + str(analyse["var_7j"]) + "%)")
    elif analyse.get("var_7j", 0) < -3:
        raisons_short.append("Tendance baissiere sur 7 jours (" + str(analyse["var_7j"]) + "%)")
    if "haussier" in analyse.get("momentum", ""):
        raisons_long.append("Momentum " + analyse["momentum"])
    elif "baissier" in analyse.get("momentum", ""):
        raisons_short.append("Momentum " + analyse["momentum"])
    if analyse.get("tendance_vol") == "en hausse":
        if score_prix > 0:
            raisons_long.append("Volume en hausse confirme la tendance")
        else:
            raisons_short.append("Volume en hausse confirme la baisse")
    if analyse.get("pct_support", 100) < 2:
        raisons_long.append("Prix proche du support (" + str(int(analyse["support"])) + " USD)")
    if analyse.get("pct_resistance", 100) < 2:
        raisons_short.append("Prix proche resistance (" + str(int(analyse["resistance"])) + " USD)")
    if score_news >= 2:
        raisons_long.append("Sentiment des news positif")
    elif score_news <= -2:
        raisons_short.append("Sentiment des news negatif")
    else:
        raisons_attendre.append("Sentiment des news neutre")
    if abs(analyse.get("var_24h", 0)) < 0.5:
        raisons_attendre.append("Marche en consolidation")
    if score_total >= 2.5:
        conseil = "LONG"
        confiance = "Forte" if score_total >= 4 else "Moyenne"
        raisons = raisons_long[:3]
    elif score_total <= -2.5:
        conseil = "SHORT"
        confiance = "Forte" if score_total <= -4 else "Moyenne"
        raisons = raisons_short[:3]
    else:
        conseil = "ATTENDRE"
        confiance = "Faible"
        raisons = raisons_attendre[:2] if raisons_attendre else ["Signaux mixtes"]
    return conseil, confiance, raisons


def signe(v):
    return "+" if v >= 0 else ""


def format_analyse(actuel, analyse, conseil, confiance, raisons, sentiment, news_resume, heure_paris):
    msg = (
        "================================\n"
        + "  ANALYSE BTC - " + heure_paris + " Paris\n"
        + "================================\n"
        + "Prix    : " + str(actuel["prix"]) + " USD\n"
        + "24H     : " + signe(actuel["var_24h"]) + str(actuel["var_24h"]) + "%\n"
        + "7J      : " + signe(actuel["var_7d"]) + str(actuel["var_7d"]) + "%\n"
        + "--------------------------------\n"
        + "  CONSEIL : " + conseil + "\n"
        + "  Confiance : " + confiance + "\n"
        + "--------------------------------\n"
        + "VARIATIONS :\n"
        + "1H  : " + signe(analyse["var_1h"]) + str(analyse["var_1h"]) + "%\n"
        + "4H  : " + signe(analyse["var_4h"]) + str(analyse["var_4h"]) + "%\n"
        + "24H : " + signe(analyse["var_24h"]) + str(analyse["var_24h"]) + "%\n"
        + "48H : " + signe(analyse["var_48h"]) + str(analyse["var_48h"]) + "%\n"
        + "7J  : " + signe(analyse["var_7j"]) + str(analyse["var_7j"]) + "%\n"
        + "\n"
        + "Momentum : " + analyse["momentum"] + "\n"
        + "Volume   : " + analyse["tendance_vol"] + "\n"
        + "--------------------------------\n"
        + "NIVEAUX CLES :\n"
        + "Support    : " + str(int(analyse["support"])) + " USD\n"
        + "Resistance : " + str(int(analyse["resistance"])) + " USD\n"
        + "Haut 24H   : " + str(analyse["haut_24h"]) + " USD\n"
        + "Bas 24H    : " + str(analyse["bas_24h"]) + " USD\n"
        + "--------------------------------\n"
        + "RAISONS :\n"
    )
    for r in raisons:
        msg = msg + "- " + r + "\n"
    msg = msg + (
        "--------------------------------\n"
        + "NEWS (sentiment : " + sentiment + ") :\n"
    )
    for titre in news_resume[:3]:
        msg = msg + "- " + titre + "\n"
    msg = msg + (
        "================================\n"
        + "Pas un conseil financier\n"
        + "================================"
    )
    return msg


def run():
    print("Bot Predictif BTC demarre")
    send_telegram(
        "================================\n"
        + "  BOT PREDICTIF BTC\n"
        + "================================\n"
        + "Mode     : Analyse prix + news\n"
        + "Frequence: toutes les heures\n"
        + "Filtre   : 7h - 23h Paris\n"
        + "Pause WE : OUI\n"
        + "100% gratuit\n"
        + "================================\n"
        + "Premiere analyse dans 1 minute..."
    )
    weekend_notified = False
    derniere_analyse_h = -1
    time.sleep(60)
    while True:
        now = datetime.utcnow()
        heure_paris = str(now.hour + 2) + "h" + now.strftime("%M")
        if PAUSE_WEEKEND and is_weekend():
            if not weekend_notified:
                send_telegram(
                    "================================\n"
                    + "  BOT EN PAUSE - WEEKEND\n"
                    + "================================\n"
                    + "Reprise automatique lundi 7h.\n"
                    + "================================"
                )
                weekend_notified = True
                derniere_analyse_h = -1
            time.sleep(3600)
            continue
        else:
            weekend_notified = False
        if is_heure_creuse():
            print("[" + now.strftime("%H:%M") + " UTC] Heure creuse")
            time.sleep(1800)
            continue
        if now.hour != derniere_analyse_h:
            derniere_analyse_h = now.hour
            print("[" + now.strftime("%H:%M") + " UTC] Analyse BTC...")
            prices, volumes = get_historique_btc()
            actuel = get_prix_actuel()
            if prices is None or actuel is None:
                print("Erreur donnees")
                time.sleep(300)
                continue
            analyse = analyser_prix(prices, volumes)
            news = get_news_btc()
            score_news, sentiment, news_resume = analyser_sentiment_news(news)
            conseil, confiance, raisons = generer_conseil(
                analyse.get("score_prix", 0),
                score_news,
                analyse
            )
            msg = format_analyse(
                actuel, analyse, conseil, confiance,
                raisons, sentiment, news_resume, heure_paris
            )
            send_telegram(msg)
            print("Analyse envoyee : " + conseil + " (" + confiance + ")")
        time.sleep(600)


if __name__ == "__main__":
    run()
