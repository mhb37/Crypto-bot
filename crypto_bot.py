import requests
import time
import os
from datetime import datetime

TELEGRAM_TOKEN = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

PAUSE_WEEKEND = True
HEURE_DEBUT = 5
HEURE_FIN = 21


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
        "include_market_cap": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()["bitcoin"]
        return {
            "prix": round(data["usd"], 2),
            "var_24h": round(data.get("usd_24h_change", 0), 2),
            "var_7d": round(data.get("usd_7d_change", 0), 2),
            "market_cap": round(data.get("usd_market_cap", 0) / 1e9, 1),
        }
    except:
        return None


def get_donnees_avancees():
    url = "https://api.coingecko.com/api/v3/coins/bitcoin"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "false",
    }
    try:
        time.sleep(3)
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        md = data.get("market_data", {})
        cd = data.get("community_data", {})
        return {
            "ath": round(md.get("ath", {}).get("usd", 0), 0),
            "ath_pct": round(md.get("ath_change_percentage", {}).get("usd", 0), 1),
            "sentiment_up": data.get("sentiment_votes_up_percentage", 0),
            "reddit_subscribers": cd.get("reddit_subscribers", 0),
        }
    except Exception as e:
        print("Erreur donnees avancees: " + str(e))
        return {}


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=3", timeout=10)
        data = r.json()
        results = data.get("data", [])
        if results:
            actuel = results[0]
            return {
                "valeur": actuel.get("value", "?"),
                "label": actuel.get("value_classification", "?"),
                "hier": results[1].get("value", "?") if len(results) > 1 else "?",
                "avant_hier": results[2].get("value", "?") if len(results) > 2 else "?",
            }
    except Exception as e:
        print("Erreur Fear and Greed: " + str(e))
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
        for item in data.get("results", [])[:15]:
            titre = item.get("title", "")
            if titre:
                titres.append(titre)
        return titres
    except:
        return []


def preparer_resume_prix(prices, volumes, actuel):
    if not prices or len(prices) < 24:
        return "Donnees indisponibles"

    prix_now = prices[-1]
    prix_1h = prices[-2] if len(prices) >= 2 else prix_now
    prix_4h = prices[-5] if len(prices) >= 5 else prix_now
    prix_6h = prices[-7] if len(prices) >= 7 else prix_now
    prix_12h = prices[-13] if len(prices) >= 13 else prix_now
    prix_24h = prices[-25] if len(prices) >= 25 else prices[0]
    prix_48h = prices[-49] if len(prices) >= 49 else prices[0]
    prix_7j = prices[0]

    def v(a, b):
        return round((a - b) / b * 100, 2)

    var_1h = v(prix_now, prix_1h)
    var_4h = v(prix_now, prix_4h)
    var_6h = v(prix_now, prix_6h)
    var_12h = v(prix_now, prix_12h)
    var_24h = v(prix_now, prix_24h)
    var_48h = v(prix_now, prix_48h)
    var_7j = v(prix_now, prix_7j)

    haut_24h = round(max(prices[-25:]), 0)
    bas_24h = round(min(prices[-25:]), 0)
    haut_7j = round(max(prices), 0)
    bas_7j = round(min(prices), 0)

    vol_recent = sum(volumes[-6:]) / 6 if len(volumes) >= 6 else 0
    vol_ancien = sum(volumes[-24:-6]) / 18 if len(volumes) >= 24 else vol_recent
    if vol_recent > vol_ancien * 1.15:
        tendance_vol = "en forte hausse"
    elif vol_recent > vol_ancien * 1.05:
        tendance_vol = "en legere hausse"
    elif vol_recent < vol_ancien * 0.85:
        tendance_vol = "en forte baisse"
    elif vol_recent < vol_ancien * 0.95:
        tendance_vol = "en legere baisse"
    else:
        tendance_vol = "stable"

    hausse_count = sum(1 for i in range(1, min(25, len(prices))) if prices[-i] > prices[-i-1])
    pct_hausse = round(hausse_count / 24 * 100, 0)

    support = round(min(prices[-48:] if len(prices) >= 48 else prices), 0)
    resistance = round(max(prices[-48:] if len(prices) >= 48 else prices), 0)

    def s(val):
        return "+" if val >= 0 else ""

    resume = (
        "Prix actuel : " + str(actuel["prix"]) + " USD\n"
        + "Market cap  : " + str(actuel["market_cap"]) + " Mrd USD\n"
        + "Variation 1H  : " + s(var_1h) + str(var_1h) + "%\n"
        + "Variation 4H  : " + s(var_4h) + str(var_4h) + "%\n"
        + "Variation 6H  : " + s(var_6h) + str(var_6h) + "%\n"
        + "Variation 12H : " + s(var_12h) + str(var_12h) + "%\n"
        + "Variation 24H : " + s(var_24h) + str(var_24h) + "%\n"
        + "Variation 48H : " + s(var_48h) + str(var_48h) + "%\n"
        + "Variation 7J  : " + s(var_7j) + str(var_7j) + "%\n"
        + "Plus haut 24H : " + str(haut_24h) + " USD\n"
        + "Plus bas 24H  : " + str(bas_24h) + " USD\n"
        + "Plus haut 7J  : " + str(haut_7j) + " USD\n"
        + "Plus bas 7J   : " + str(bas_7j) + " USD\n"
        + "Volume        : " + tendance_vol + "\n"
        + "Momentum 24H  : " + str(pct_hausse) + "% des heures en hausse\n"
        + "Support cle   : " + str(support) + " USD\n"
        + "Resistance cle: " + str(resistance) + " USD\n"
    )
    return resume


def analyser_avec_gemini(resume_prix, fear_greed, donnees_avancees, news, heure_paris):
    date_str = datetime.utcnow().strftime("%d/%m/%Y")

    if fear_greed:
        fg_texte = (
            "Indice Fear and Greed actuel : " + str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ")\n"
            + "Hier : " + str(fear_greed["hier"]) + "/100\n"
            + "Avant-hier : " + str(fear_greed["avant_hier"]) + "/100"
        )
    else:
        fg_texte = "Indice Fear and Greed : non disponible"

    if donnees_avancees:
        da_texte = (
            "ATH Bitcoin : " + str(int(donnees_avancees.get("ath", 0))) + " USD\n"
            + "Distance ATH : " + str(donnees_avancees.get("ath_pct", 0)) + "%\n"
            + "Sentiment communaute : " + str(donnees_avancees.get("sentiment_up", 0)) + "% haussier\n"
        )
    else:
        da_texte = ""

    if news:
        news_texte = ""
        for i, titre in enumerate(news[:10]):
            news_texte = news_texte + str(i+1) + ". " + titre + "\n"
    else:
        news_texte = "Aucune news disponible."

    prompt = (
        "Tu es un expert analyste Bitcoin tres reconnu. Nous sommes le "
        + date_str + " a " + heure_paris + " heure de Paris.\n\n"
        + "Voici toutes les donnees disponibles sur Bitcoin :\n\n"
        + "=== DONNEES DE PRIX ===\n"
        + resume_prix + "\n"
        + "=== SENTIMENT DU MARCHE ===\n"
        + fg_texte + "\n\n"
        + "=== DONNEES COMPLEMENTAIRES ===\n"
        + da_texte + "\n"
        + "=== NEWS CHAUDES DU MOMENT ===\n"
        + news_texte + "\n"
        + "En analysant TOUTES ces donnees, redige une analyse courte et directe en francais.\n"
        + "Reponds EXACTEMENT dans ce format :\n\n"
        + "CONSEIL : LONG ou SHORT ou ATTENDRE\n"
        + "CONFIANCE : Faible ou Moyenne ou Forte\n\n"
        + "CONTEXTE :\n"
        + "2 phrases maximum sur la situation actuelle de BTC\n\n"
        + "RAISONS :\n"
        + "- raison 1\n"
        + "- raison 2\n"
        + "- raison 3\n\n"
        + "RISQUES :\n"
        + "- risque principal\n\n"
        + "NIVEAUX CLES :\n"
        + "Support : prix USD\n"
        + "Resistance : prix USD\n"
        + "Objectif : prix USD\n"
    )

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 500,
        }
    }

    try:
        r = requests.post(url, json=body, timeout=30)
        data = r.json()
        candidates = data.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
        print("Erreur Gemini: " + str(data))
        return None
    except Exception as e:
        print("Erreur Gemini: " + str(e))
        return None


def format_message(analyse, actuel, fear_greed, heure_paris):
    s24 = "+" if actuel["var_24h"] >= 0 else ""
    s7 = "+" if actuel["var_7d"] >= 0 else ""
    fg_line = ""
    if fear_greed:
        fg_line = "Fear&Greed : " + str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ")\n"
    return (
        "================================\n"
        + "  ANALYSE BTC - " + heure_paris + " Paris\n"
        + "================================\n"
        + "Prix : " + str(actuel["prix"]) + " USD\n"
        + "24H  : " + s24 + str(actuel["var_24h"]) + "%\n"
        + "7J   : " + s7 + str(actuel["var_7d"]) + "%\n"
        + fg_line
        + "--------------------------------\n"
        + analyse
        + "\n--------------------------------\n"
        + "Pas un conseil financier\n"
        + "================================"
    )


def run():
    print("Bot BTC Predictif Gemini demarre")
    send_telegram(
        "================================\n"
        + "  BOT PREDICTIF BTC + IA\n"
        + "================================\n"
        + "IA      : Google Gemini gratuit\n"
        + "Sources : Prix, Volume, Fear&Greed\n"
        + "          News crypto, Sentiment\n"
        + "          Donnees marche avancees\n"
        + "Analyse : toutes les heures\n"
        + "Filtre  : 7h - 23h Paris\n"
        + "Pause WE: OUI\n"
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
            print("[" + now.strftime("%H:%M") + " UTC] Lancement analyse BTC...")

            prices, volumes = get_historique_btc()
            actuel = get_prix_actuel()

            if prices is None or actuel is None:
                print("Erreur donnees prix")
                time.sleep(300)
                continue

            resume_prix = preparer_resume_prix(prices, volumes, actuel)
            fear_greed = get_fear_greed()
            donnees_avancees = get_donnees_avancees()
            news = get_news_btc()

            print("Donnees collectees. Analyse Gemini en cours...")
            analyse = analyser_avec_gemini(resume_prix, fear_greed, donnees_avancees, news, heure_paris)

            if analyse is None:
                send_telegram(
                    "================================\n"
                    + "  ERREUR - " + heure_paris + " Paris\n"
                    + "================================\n"
                    + "Prix BTC : " + str(actuel["prix"]) + " USD\n"
                    + "Analyse IA indisponible.\n"
                    + "Reessai dans 1 heure.\n"
                    + "================================"
                )
            else:
                msg = format_message(analyse, actuel, fear_greed, heure_paris)
                send_telegram(msg)
                print("Analyse envoyee avec succes")

        time.sleep(600)


if __name__ == "__main__":
    run()
