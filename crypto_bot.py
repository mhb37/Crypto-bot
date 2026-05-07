import requests
import time
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
PHANTOM_WALLET = "AVELFh7k13hounRzxbV1QczpaPAR4VtjEYw68LPBUrU5"

PAUSE_WEEKEND = True
HEURE_DEBUT = 5
HEURE_FIN = 21
SEUIL_MOUVEMENT = 3.0
MAX_RETRY = 3
RETRY_DELAY = 20

MOTS_URGENTS = [
    "etf", "sec", "blackrock", "fidelity", "ban", "banned", "hack", "hacked",
    "crash", "record", "all-time high", "ath", "bankruptcy", "bankrupt",
    "arrest", "seized", "regulation", "emergency", "breaking", "urgent",
    "federal reserve", "fed rate", "interest rate", "inflation", "halving",
    "liquidation", "whale", "manipulation", "exchange down", "scam", "fraud"
]

MOTS_POSITIFS_REDDIT = [
    "bullish", "moon", "buy", "long", "pump", "green", "up", "rally",
    "support", "breakout", "accumulate", "hold", "hodl", "ath", "surge"
]

MOTS_NEGATIFS_REDDIT = [
    "bearish", "crash", "dump", "sell", "short", "red", "down", "bear",
    "fear", "panic", "drop", "fall", "resistance", "bubble", "scam"
]

journal_trades = []
position_en_cours = None


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


def get_sol_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
            timeout=10
        )
        data = r.json()
        return data.get("solana", {}).get("usd", 0)
    except:
        return 0


def get_wallet_info():
    try:
        url = "https://api.mainnet-beta.solana.com"
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [PHANTOM_WALLET]
        }
        r = requests.post(url, json=body, timeout=10)
        data = r.json()
        lamports = data.get("result", {}).get("value", 0)
        sol = round(lamports / 1e9, 4)
        sol_price = get_sol_price()
        valeur_usd = round(sol * sol_price, 2)
        return {
            "sol": sol,
            "sol_price": round(sol_price, 2),
            "valeur_usd": valeur_usd,
        }
    except Exception as e:
        print("Erreur wallet: " + str(e))
        return None


def calculer_position(valeur_usd, score_risque):
    if score_risque <= 3:
        pct_capital = 5
        levier = 2
    elif score_risque <= 5:
        pct_capital = 10
        levier = 3
    elif score_risque <= 7:
        pct_capital = 15
        levier = 5
    else:
        pct_capital = 5
        levier = 2

    montant_usd = round(valeur_usd * pct_capital / 100, 2)
    position_totale = round(montant_usd * levier, 2)
    risque_max = round(montant_usd * 0.5, 2)

    return {
        "pct_capital": pct_capital,
        "montant_usd": montant_usd,
        "levier": levier,
        "position_totale": position_totale,
        "risque_max": risque_max,
    }


def verifier_tp_sl(prix_actuel):
    global position_en_cours, journal_trades
    if not position_en_cours:
        return None

    direction = position_en_cours.get("direction", "")
    tp1 = position_en_cours.get("tp1", 0)
    tp2 = position_en_cours.get("tp2", 0)
    sl = position_en_cours.get("sl", 0)
    prix_entree = position_en_cours.get("prix_entree", 0)
    heure_entree = position_en_cours.get("heure", "")
    montant = position_en_cours.get("montant_usd", 0)
    levier = position_en_cours.get("levier", 1)

    message = None
    resultat = None
    pct = 0

    if direction == "LONG":
        if tp2 > 0 and prix_actuel >= tp2:
            pct = round((prix_actuel - prix_entree) / prix_entree * 100, 2)
            gain_usd = round(montant * levier * pct / 100, 2)
            resultat = "GAGNANT"
            message = (
                "🎯 TP2 ATTEINT - LONG GAGNE\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Sortie    : " + str(prix_actuel) + " USD\n"
                "📈 Gain      : +" + str(pct) + "%\n"
                "💵 Gain USD  : +" + str(gain_usd) + " USD\n"
                "⏰ Ouvert a  : " + heure_entree + "\n"
                "\n"
                "Fermer la position maintenant !"
            )
        elif tp1 > 0 and prix_actuel >= tp1 and not position_en_cours.get("tp1_atteint"):
            pct = round((prix_actuel - prix_entree) / prix_entree * 100, 2)
            gain_usd = round(montant * levier * pct / 100, 2)
            position_en_cours["tp1_atteint"] = True
            message = (
                "🎯 TP1 ATTEINT - LONG EN PROFIT\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Actuel    : " + str(prix_actuel) + " USD\n"
                "📈 Profit    : +" + str(pct) + "%\n"
                "💵 Profit USD: +" + str(gain_usd) + " USD\n"
                "\n"
                "Securiser une partie.\n"
                "TP2 vise : " + str(tp2) + " USD"
            )
        elif sl > 0 and prix_actuel <= sl:
            pct = round((prix_actuel - prix_entree) / prix_entree * 100, 2)
            perte_usd = round(montant * levier * abs(pct) / 100, 2)
            resultat = "PERDANT"
            message = (
                "🛑 STOP LOSS DECLENCHE\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Actuel    : " + str(prix_actuel) + " USD\n"
                "📉 Perte     : " + str(pct) + "%\n"
                "💵 Perte USD : -" + str(perte_usd) + " USD\n"
                "⏰ Ouvert a  : " + heure_entree + "\n"
                "\n"
                "Fermer la position maintenant !"
            )

    elif direction == "SHORT":
        if tp2 > 0 and prix_actuel <= tp2:
            pct = round((prix_entree - prix_actuel) / prix_entree * 100, 2)
            gain_usd = round(montant * levier * pct / 100, 2)
            resultat = "GAGNANT"
            message = (
                "🎯 TP2 ATTEINT - SHORT GAGNE\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Sortie    : " + str(prix_actuel) + " USD\n"
                "📈 Gain      : +" + str(pct) + "%\n"
                "💵 Gain USD  : +" + str(gain_usd) + " USD\n"
                "⏰ Ouvert a  : " + heure_entree + "\n"
                "\n"
                "Fermer la position maintenant !"
            )
        elif tp1 > 0 and prix_actuel <= tp1 and not position_en_cours.get("tp1_atteint"):
            pct = round((prix_entree - prix_actuel) / prix_entree * 100, 2)
            gain_usd = round(montant * levier * pct / 100, 2)
            position_en_cours["tp1_atteint"] = True
            message = (
                "🎯 TP1 ATTEINT - SHORT EN PROFIT\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Actuel    : " + str(prix_actuel) + " USD\n"
                "📈 Profit    : +" + str(pct) + "%\n"
                "💵 Profit USD: +" + str(gain_usd) + " USD\n"
                "\n"
                "Securiser une partie.\n"
                "TP2 vise : " + str(tp2) + " USD"
            )
        elif sl > 0 and prix_actuel >= sl:
            pct = round((prix_entree - prix_actuel) / prix_entree * 100, 2)
            perte_usd = round(montant * levier * abs(pct) / 100, 2)
            resultat = "PERDANT"
            message = (
                "🛑 STOP LOSS DECLENCHE\n"
                "\n"
                "💰 Entree    : " + str(prix_entree) + " USD\n"
                "💰 Actuel    : " + str(prix_actuel) + " USD\n"
                "📉 Perte     : " + str(pct) + "%\n"
                "💵 Perte USD : -" + str(perte_usd) + " USD\n"
                "⏰ Ouvert a  : " + heure_entree + "\n"
                "\n"
                "Fermer la position maintenant !"
            )

    if resultat:
        journal_trades.append({
            "direction": direction,
            "prix_entree": prix_entree,
            "prix_sortie": prix_actuel,
            "pct": pct,
            "resultat": resultat,
            "heure": datetime.utcnow().strftime("%d/%m %H:%M"),
        })
        position_en_cours = None

    return message


def enregistrer_position(direction, prix_entree, tp1, tp2, sl, montant_usd, levier):
    global position_en_cours
    if direction in ("LONG", "SHORT"):
        position_en_cours = {
            "direction": direction,
            "prix_entree": prix_entree,
            "tp1": tp1,
            "tp2": tp2,
            "sl": sl,
            "montant_usd": montant_usd,
            "levier": levier,
            "tp1_atteint": False,
            "heure": datetime.utcnow().strftime("%d/%m %H:%M UTC"),
        }
        print("Position enregistree: " + direction + " a " + str(prix_entree))


def reporting_soir():
    global journal_trades
    now = datetime.utcnow().strftime("%d/%m/%Y")
    msg = "📊 REPORTING DU SOIR - " + now + "\n"
    msg = msg + "─────────────────────────\n"

    if not journal_trades:
        msg = msg + "Aucun trade ferme aujourd hui.\n"
    else:
        total = len(journal_trades)
        gagnants = [t for t in journal_trades if t["resultat"] == "GAGNANT"]
        perdants = [t for t in journal_trades if t["resultat"] == "PERDANT"]
        pct_moyen = round(sum(t["pct"] for t in journal_trades) / total, 2)
        taux = round(len(gagnants) / total * 100, 0)
        msg = msg + "Trades fermes   : " + str(total) + "\n"
        msg = msg + "Gagnants        : " + str(len(gagnants)) + " ✅\n"
        msg = msg + "Perdants        : " + str(len(perdants)) + " ❌\n"
        msg = msg + "Taux de reussite: " + str(taux) + "%\n"
        s = "+" if pct_moyen >= 0 else ""
        msg = msg + "Perf moyenne    : " + s + str(pct_moyen) + "%\n"
        msg = msg + "\nDetail :\n"
        for t in journal_trades:
            emoji = "✅" if t["resultat"] == "GAGNANT" else "❌"
            s = "+" if t["pct"] >= 0 else ""
            msg = msg + emoji + " " + t["direction"] + " " + s + str(t["pct"]) + "% (" + t["heure"] + ")\n"

    if position_en_cours:
        msg = msg + (
            "\nPosition ouverte :\n"
            "📍 " + position_en_cours["direction"] + " @ " + str(position_en_cours["prix_entree"]) + " USD\n"
            "Depuis : " + position_en_cours["heure"] + "\n"
            "Montant : " + str(position_en_cours["montant_usd"]) + " USD x" + str(position_en_cours["levier"]) + "\n"
        )

    msg = msg + "─────────────────────────\n"
    msg = msg + "⚠️ Pas un conseil financier"
    return msg


def get_historique_btc():
    for tentative in range(MAX_RETRY):
        try:
            time.sleep(5)
            url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
            params = {"vs_currency": "usd", "days": "7", "interval": "hourly"}
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            if "prices" not in data:
                print("CoinGecko rate limit tentative " + str(tentative + 1))
                time.sleep(60)
                continue
            prices = [p[1] for p in data["prices"]]
            volumes = [v[1] for v in data["total_volumes"]]
            return prices, volumes
        except Exception as e:
            print("Erreur CoinGecko tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None, None


def get_prix_actuel():
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=10)
        data = r.json()
        return {
            "prix": round(float(data["lastPrice"]), 2),
            "var_24h": round(float(data["priceChangePercent"]), 2),
            "var_7d": 0,
        }
    except Exception as e:
        print("Erreur Binance: " + str(e))
    for tentative in range(MAX_RETRY):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "bitcoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_7d_change": "true",
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()["bitcoin"]
            return {
                "prix": round(data["usd"], 2),
                "var_24h": round(data.get("usd_24h_change", 0), 2),
                "var_7d": round(data.get("usd_7d_change", 0), 2),
            }
        except Exception as e:
            print("Erreur CoinGecko prix tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def get_donnees_avancees():
    for tentative in range(MAX_RETRY):
        try:
            time.sleep(3)
            url = "https://api.coingecko.com/api/v3/coins/bitcoin"
            params = {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "true",
                "developer_data": "false",
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            md = data.get("market_data", {})
            return {
                "ath": round(md.get("ath", {}).get("usd", 0), 0),
                "ath_pct": round(md.get("ath_change_percentage", {}).get("usd", 0), 1),
                "sentiment_up": data.get("sentiment_votes_up_percentage", 0),
            }
        except Exception as e:
            print("Erreur donnees avancees tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return {}


def get_fear_greed():
    for tentative in range(MAX_RETRY):
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
            print("Erreur Fear and Greed tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def get_news_btc():
    titres = []
    try:
        time.sleep(3)
        r = requests.get("https://api.coingecko.com/api/v3/news", timeout=10)
        data = r.json()
        for item in data.get("data", [])[:10]:
            titre = item.get("title", "")
            if titre:
                t = titre.lower()
                if "bitcoin" in t or "btc" in t or "crypto" in t:
                    titres.append(titre)
    except Exception as e:
        print("Erreur CoinGecko news: " + str(e))
    try:
        url = "https://api.rss2json.com/v1/api.json"
        params = {"rss_url": "https://cointelegraph.com/rss/tag/bitcoin", "count": "15"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for item in data.get("items", [])[:15]:
            titre = item.get("title", "")
            if titre and titre not in titres:
                titres.append(titre)
    except Exception as e:
        print("Erreur Cointelegraph: " + str(e))
    try:
        url = "https://api.rss2json.com/v1/api.json"
        params = {"rss_url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "count": "15"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for item in data.get("items", [])[:15]:
            titre = item.get("title", "")
            if titre and titre not in titres:
                t = titre.lower()
                if "bitcoin" in t or "btc" in t or "crypto" in t:
                    titres.append(titre)
    except Exception as e:
        print("Erreur CoinDesk: " + str(e))
    print("News recuperees: " + str(len(titres)))
    return titres[:20]


def get_reddit_sentiment():
    for tentative in range(MAX_RETRY):
        try:
            headers = {"User-Agent": "CryptoBotAnalysis/1.0"}
            url = "https://www.reddit.com/r/Bitcoin/hot.json?limit=25"
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json()
            posts = data.get("data", {}).get("children", [])
            score_pos = 0
            score_neg = 0
            titres_reddit = []
            for post in posts:
                pd = post.get("data", {})
                titre = pd.get("title", "").lower()
                upvotes = pd.get("ups", 0)
                for mot in MOTS_POSITIFS_REDDIT:
                    if mot in titre:
                        score_pos += 1
                for mot in MOTS_NEGATIFS_REDDIT:
                    if mot in titre:
                        score_neg += 1
                if upvotes > 500:
                    titres_reddit.append(pd.get("title", "")[:100])
            score_net = score_pos - score_neg
            if score_net >= 4:
                sentiment = "Tres haussier"
            elif score_net >= 2:
                sentiment = "Haussier"
            elif score_net <= -4:
                sentiment = "Tres baissier"
            elif score_net <= -2:
                sentiment = "Baissier"
            else:
                sentiment = "Neutre"
            return {
                "sentiment": sentiment,
                "top_posts": titres_reddit[:3],
            }
        except Exception as e:
            print("Erreur Reddit tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def get_google_trends():
    for tentative in range(MAX_RETRY):
        try:
            url = "https://trends.google.com/trends/api/dailytrends"
            params = {"hl": "fr", "tz": "-60", "geo": "FR", "ns": "15"}
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, params=params, headers=headers, timeout=10)
            text = r.text
            if ")]}'" in text:
                text = text[text.index(")]}'")+4:]
            data = json.loads(text)
            trending = data.get("default", {}).get("trendingSearchesDays", [])
            btc_trending = False
            for day in trending:
                for search in day.get("trendingSearches", []):
                    titre = search.get("title", {}).get("query", "").lower()
                    for kw in ["bitcoin", "btc", "crypto", "cryptocurrency"]:
                        if kw in titre:
                            btc_trending = True
            return {
                "btc_trending": btc_trending,
                "statut": "Bitcoin en tendance Google" if btc_trending else "Bitcoin non trending",
            }
        except Exception as e:
            print("Erreur Google Trends tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def detecter_news_urgente(news):
    for titre in news:
        t = titre.lower()
        for mot in MOTS_URGENTS:
            if mot in t:
                return True, titre
    return False, None


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

    return (
        "Prix actuel : " + str(actuel["prix"]) + " USD\n"
        "Variation 1H  : " + s(var_1h) + str(var_1h) + "%\n"
        "Variation 4H  : " + s(var_4h) + str(var_4h) + "%\n"
        "Variation 6H  : " + s(var_6h) + str(var_6h) + "%\n"
        "Variation 12H : " + s(var_12h) + str(var_12h) + "%\n"
        "Variation 24H : " + s(var_24h) + str(var_24h) + "%\n"
        "Variation 48H : " + s(var_48h) + str(var_48h) + "%\n"
        "Variation 7J  : " + s(var_7j) + str(var_7j) + "%\n"
        "Plus haut 24H : " + str(haut_24h) + " USD\n"
        "Plus bas 24H  : " + str(bas_24h) + " USD\n"
        "Plus haut 7J  : " + str(haut_7j) + " USD\n"
        "Plus bas 7J   : " + str(bas_7j) + " USD\n"
        "Volume        : " + tendance_vol + "\n"
        "Momentum 24H  : " + str(pct_hausse) + "% des heures en hausse\n"
        "Support cle   : " + str(support) + " USD\n"
        "Resistance cle: " + str(resistance) + " USD\n"
    )


def construire_prompt(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte, wallet_info, calc_pos):
    date_str = datetime.utcnow().strftime("%d/%m/%Y")

    if fear_greed:
        fg = (
            "Fear and Greed actuel : " + str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ")\n"
            "Hier : " + str(fear_greed["hier"]) + "/100\n"
            "Avant-hier : " + str(fear_greed["avant_hier"]) + "/100"
        )
    else:
        fg = "Fear and Greed : non disponible"

    if donnees_avancees:
        da = (
            "ATH Bitcoin : " + str(int(donnees_avancees.get("ath", 0))) + " USD\n"
            "Distance ATH : " + str(donnees_avancees.get("ath_pct", 0)) + "%\n"
            "Sentiment : " + str(donnees_avancees.get("sentiment_up", 0)) + "% haussier\n"
        )
    else:
        da = ""

    if reddit:
        rd = "Sentiment Reddit r/Bitcoin : " + reddit["sentiment"] + "\n"
        if reddit["top_posts"]:
            rd = rd + "Posts populaires :\n"
            for p in reddit["top_posts"]:
                rd = rd + "- " + p + "\n"
    else:
        rd = "Sentiment Reddit : non disponible"

    tr = "Google Trends : non disponible"
    if trends:
        tr = "Google Trends : " + trends["statut"]

    if news:
        nw = ""
        for i, titre in enumerate(news[:15]):
            nw = nw + str(i + 1) + ". " + titre + "\n"
    else:
        nw = "Aucune news disponible."

    pos_info = "Aucune position ouverte actuellement."
    if position_en_cours:
        pos_info = (
            "POSITION EN COURS : " + position_en_cours["direction"] + "\n"
            "Prix d entree : " + str(position_en_cours["prix_entree"]) + " USD\n"
            "Montant investi : " + str(position_en_cours["montant_usd"]) + " USD\n"
            "Levier : x" + str(position_en_cours["levier"]) + "\n"
            "TP1 : " + str(position_en_cours["tp1"]) + " USD\n"
            "TP2 : " + str(position_en_cours["tp2"]) + " USD\n"
            "SL  : " + str(position_en_cours["sl"]) + " USD\n"
            "Ouverte a : " + position_en_cours["heure"] + "\n"
            "IMPORTANT : Ne pas ouvrir une nouvelle position !"
        )

    wallet_txt = "Portefeuille non disponible"
    if wallet_info:
        wallet_txt = (
            "Solde total : " + str(wallet_info["valeur_usd"]) + " USD\n"
            "Composition : " + str(wallet_info["sol"]) + " SOL @ " + str(wallet_info["sol_price"]) + " USD\n"
        )

    calc_txt = ""
    if calc_pos:
        calc_txt = (
            "Capital recommande a deployer : " + str(calc_pos["pct_capital"]) + "% = " + str(calc_pos["montant_usd"]) + " USD\n"
            "Levier recommande : x" + str(calc_pos["levier"]) + "\n"
            "Taille totale de position : " + str(calc_pos["position_totale"]) + " USD\n"
            "Risque maximum acceptable : " + str(calc_pos["risque_max"]) + " USD\n"
        )

    if contexte == "matin":
        instruction = (
            "Analyse du MATIN tres detaillee. Sois PROACTIF.\n"
            "Analyse les news du jour ET d hier avant de decider.\n"
            "1. Donne la METEO DU MARCHE\n"
            "2. Donne un SCORE DE RISQUE de 1 a 10\n"
            "3. Utilise le budget du portefeuille pour calculer la position exacte en USD\n"
            "4. Si position en cours, faut-il la garder ou la fermer ?\n"
            "5. Si pas de position, y a-t-il une opportunite claire ?\n"
            "6. Donne un plan d action PRECIS avec montants en USD"
        )
    elif contexte == "midi":
        instruction = (
            "POINT DU MIDI. Sois COHERENT avec la position en cours.\n"
            "1. La tendance du matin se confirme-t-elle ?\n"
            "2. La position en cours est-elle toujours valide ?\n"
            "3. Faut-il ajuster le SL pour securiser les profits ?\n"
            "4. NE PAS proposer une nouvelle entree si position deja ouverte"
        )
    elif contexte == "soir":
        instruction = (
            "BILAN DU SOIR. Sois COHERENT.\n"
            "1. Bilan complet de la journee\n"
            "2. La position en cours : garder pour la nuit ou fermer ?\n"
            "3. Que surveiller cette nuit ?\n"
            "4. Preparation pour demain avec budget disponible"
        )
    elif contexte == "alerte_mouvement":
        instruction = (
            "ALERTE MOUVEMENT. Sois IMMEDIAT.\n"
            "1. Ce mouvement impacte-t-il la position en cours ?\n"
            "2. Faut-il fermer, ajuster le SL ou laisser courir ?\n"
            "3. NE PAS ouvrir une nouvelle position si une est deja ouverte\n"
            "4. Si pas de position, est-ce le bon moment ? Quel montant en USD ?"
        )
    elif contexte == "alerte_news":
        instruction = (
            "ALERTE NEWS. Sois IMMEDIAT et COHERENT.\n"
            "1. Cette news change-t-elle la these de la position en cours ?\n"
            "2. Faut-il agir sur la position existante ?\n"
            "3. NE PAS proposer de nouvelle entree si position ouverte\n"
            "4. Impact direct sur le prix dans les prochaines heures ?"
        )
    else:
        instruction = "Analyse complete et proactive de BTC."

    return (
        "Tu es un trader Bitcoin expert et PROACTIF. Tu reponds UNIQUEMENT en francais.\n"
        "Tu parles TOUJOURS en USD, jamais en SOL.\n"
        "Tu es COHERENT : jamais de nouvelle position si une est deja ouverte.\n"
        "Tu analyses les news du jour ET de la veille avant de decider.\n"
        "Nous sommes le " + date_str + " a " + heure_paris + " heure de Paris.\n\n"
        + instruction + "\n\n"
        "=== POSITION EN COURS ===\n" + pos_info + "\n\n"
        "=== PORTEFEUILLE (en USD) ===\n" + wallet_txt + "\n"
        + calc_txt + "\n"
        "=== PRIX BTC ===\n" + resume_prix + "\n"
        "=== FEAR AND GREED ===\n" + fg + "\n\n"
        "=== DONNEES MARCHE ===\n" + da + "\n"
        "=== SENTIMENT REDDIT ===\n" + rd + "\n\n"
        "=== GOOGLE TRENDS ===\n" + tr + "\n\n"
        "=== ACTUALITES DU JOUR ET VEILLE ===\n" + nw + "\n"
        "Reponds UNIQUEMENT en francais dans ce format EXACT :\n\n"
        "METEO : [emoji] [Favorable / Mitige / Dangereux]\n"
        "SCORE DE RISQUE : [1-10]/10\n\n"
        "POSITION EN COURS : [Garder / Fermer / Ajuster SL] ou [Aucune]\n\n"
        "CONSEIL : [LONG / SHORT / ATTENDRE / MAINTENIR]\n"
        "CONVICTION : [1-10]/10\n\n"
        "GESTION DU CAPITAL (en USD) :\n"
        "Budget total    : X USD\n"
        "Montant a risquer : X USD ([X]% du capital)\n"
        "Levier recommande : xX\n"
        "Taille de position: X USD\n\n"
        "PLAN D ACTION :\n"
        "- Action 1\n"
        "- Action 2\n"
        "- Action 3\n\n"
        "SI NOUVELLE ENTREE SEULEMENT :\n"
        "Entre a   : X USD\n"
        "TP1       : X USD\n"
        "TP2       : X USD\n"
        "Stop Loss : X USD\n\n"
        "SITUATION ACTUELLE :\n"
        "3 phrases sur ce qui se passe\n\n"
        "ACTUALITES IMPORTANTES :\n"
        "- actu 1 en francais\n"
        "- actu 2 en francais\n"
        "- actu 3 en francais\n\n"
        "RISQUES :\n"
        "- risque 1\n"
        "- risque 2\n\n"
        "SENTIMENT GLOBAL : [Haussier / Baissier / Neutre]\n"
    )


def extraire_position(analyse, prix_actuel):
    lines = analyse.lower().split("\n")
    direction = None
    tp1 = tp2 = sl = 0
    for line in lines:
        if "conseil :" in line:
            if "long" in line:
                direction = "LONG"
            elif "short" in line:
                direction = "SHORT"
        for key in ["tp1", "tp 1"]:
            if key in line:
                parts = line.replace(",", ".").split()
                for p in parts:
                    try:
                        val = float(p.replace("$", "").replace("usd", "").strip())
                        if val > 1000:
                            tp1 = val
                            break
                    except:
                        pass
        for key in ["tp2", "tp 2"]:
            if key in line:
                parts = line.replace(",", ".").split()
                for p in parts:
                    try:
                        val = float(p.replace("$", "").replace("usd", "").strip())
                        if val > 1000:
                            tp2 = val
                            break
                    except:
                        pass
        if "stop loss" in line or "stop-loss" in line:
            parts = line.replace(",", ".").split()
            for p in parts:
                try:
                    val = float(p.replace("$", "").replace("usd", "").strip())
                    if val > 1000:
                        sl = val
                        break
                except:
                    pass
    return direction, tp1, tp2, sl


def analyser_avec_cohere(prompt):
    headers = {
        "Authorization": "Bearer " + COHERE_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "model": "command-a-03-2025",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 900,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("Cohere tentative " + str(tentative + 1))
            r = requests.post("https://api.cohere.com/v2/chat", headers=headers, json=body, timeout=30)
            data = r.json()
            message = data.get("message", {})
            content = message.get("content", [])
            if content and len(content) > 0:
                text = content[0].get("text", "").strip()
                if text and len(text) > 10:
                    return text
            print("Cohere invalide: " + str(data)[:100])
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur Cohere tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def analyser_avec_openrouter(prompt):
    headers = {
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://crypto-bot.app",
        "X-Title": "CryptoBotBTC",
    }
    body = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 900,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("OpenRouter tentative " + str(tentative + 1))
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body, timeout=30)
            data = r.json()
            choices = data.get("choices", [])
            if choices and len(choices) > 0:
                content = choices[0].get("message", {}).get("content", "")
                if content and len(content) > 10:
                    return content.strip()
            print("OpenRouter invalide: " + str(data)[:150])
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur OpenRouter tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def analyser_ia(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte, wallet_info, calc_pos):
    prompt = construire_prompt(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte, wallet_info, calc_pos)
    print("Essai Cohere...")
    analyse = analyser_avec_cohere(prompt)
    if analyse:
        print("Cohere OK")
        return analyse, "Cohere"
    print("Cohere echoue, essai OpenRouter...")
    analyse = analyser_avec_openrouter(prompt)
    if analyse:
        print("OpenRouter OK")
        return analyse, "OpenRouter"
    return None, None


def label_analyse(contexte, heure_paris):
    labels = {
        "matin": "ANALYSE DU MATIN - " + heure_paris,
        "midi": "POINT DU MIDI - " + heure_paris,
        "soir": "BILAN DU SOIR - " + heure_paris,
        "alerte_mouvement": "ALERTE MOUVEMENT - " + heure_paris,
        "alerte_news": "ALERTE NEWS - " + heure_paris,
    }
    return labels.get(contexte, "ANALYSE BTC - " + heure_paris)


def format_message(actuel, fear_greed, reddit, trends, heure_paris, contexte, analyse, ia_utilisee, wallet_info):
    s24 = "+" if actuel["var_24h"] >= 0 else ""
    fg_line = ""
    if fear_greed:
        val = int(str(fear_greed["valeur"]))
        if val <= 25:
            fg_emoji = "😱"
        elif val <= 45:
            fg_emoji = "😰"
        elif val <= 55:
            fg_emoji = "😐"
        elif val <= 75:
            fg_emoji = "😊"
        else:
            fg_emoji = "🤑"
        fg_line = fg_emoji + " Fear&Greed : " + str(fear_greed["valeur"]) + "/100\n"
    reddit_line = ""
    if reddit:
        if "haussier" in reddit["sentiment"].lower():
            rd_emoji = "📈"
        elif "baissier" in reddit["sentiment"].lower():
            rd_emoji = "📉"
        else:
            rd_emoji = "➡️"
        reddit_line = rd_emoji + " Reddit : " + reddit["sentiment"] + "\n"
    trends_line = ""
    if trends and trends.get("btc_trending"):
        trends_line = "🔥 Google : Bitcoin en tendance\n"
    wallet_line = ""
    if wallet_info:
        wallet_line = "👛 Wallet : " + str(wallet_info["valeur_usd"]) + " USD\n"
    pos_line = ""
    if position_en_cours:
        pos_line = "📍 Position : " + position_en_cours["direction"] + " @ " + str(position_en_cours["prix_entree"]) + " USD\n"
    prix_emoji = "📈" if actuel["var_24h"] >= 0 else "📉"
    return (
        "╔══════════════════════════╗\n"
        "  " + label_analyse(contexte, heure_paris) + "\n"
        "╚══════════════════════════╝\n"
        "\n"
        "💰 BTC : " + str(actuel["prix"]) + " USD\n"
        "" + prix_emoji + " 24H : " + s24 + str(actuel["var_24h"]) + "%\n"
        + fg_line + reddit_line + trends_line + wallet_line + pos_line
        + "🤖 IA : " + ia_utilisee + "\n"
        "\n"
        "─────────────────────────\n"
        + analyse
        + "\n─────────────────────────\n"
        "⚠️ Pas un conseil financier\n"
    )


def collecter_donnees():
    prices, volumes = get_historique_btc()
    actuel = get_prix_actuel()
    if prices is None or actuel is None:
        return None
    return {
        "actuel": actuel,
        "resume_prix": preparer_resume_prix(prices, volumes, actuel),
        "fear_greed": get_fear_greed(),
        "donnees_avancees": get_donnees_avancees(),
        "news": get_news_btc(),
        "reddit": get_reddit_sentiment(),
        "trends": get_google_trends(),
        "wallet_info": get_wallet_info(),
    }


def lancer_analyse(contexte, heure_paris):
    global position_en_cours
    print("[" + datetime.utcnow().strftime("%H:%M") + " UTC] Analyse " + contexte + "...")
    d = collecter_donnees()
    if d is None:
        send_telegram(
            "⚠️ ERREUR DONNEES - " + heure_paris + "\n"
            "Impossible de recuperer les donnees.\n"
            "Nouvelle tentative dans 30 min."
        )
        return False

    calc_pos = None
    if d["wallet_info"] and not position_en_cours:
        score_risque = 5
        calc_pos = calculer_position(d["wallet_info"]["valeur_usd"], score_risque)

    analyse, ia = analyser_ia(
        d["resume_prix"], d["fear_greed"], d["donnees_avancees"],
        d["news"], d["reddit"], d["trends"], heure_paris, contexte,
        d["wallet_info"], calc_pos
    )
    if analyse is None:
        send_telegram(
            "⚠️ ERREUR IA - " + heure_paris + "\n"
            "Prix BTC : " + str(d["actuel"]["prix"]) + " USD\n"
            "Les IA sont indisponibles.\n"
            "Prochaine analyse prevue."
        )
        return False

    if not position_en_cours:
        direction, tp1, tp2, sl = extraire_position(analyse, d["actuel"]["prix"])
        if direction and sl > 0 and calc_pos:
            enregistrer_position(
                direction,
                d["actuel"]["prix"],
                tp1, tp2, sl,
                calc_pos["montant_usd"],
                calc_pos["levier"]
            )

    msg = format_message(
        d["actuel"], d["fear_greed"], d["reddit"], d["trends"],
        heure_paris, contexte, analyse, ia, d["wallet_info"]
    )
    send_telegram(msg)
    print("Analyse " + contexte + " envoyee via " + ia)
    return True


def run():
    global journal_trades
    print("Bot BTC V7 demarre")
    send_telegram(
        "🚀 BOT BTC INTELLIGENT V7\n"
        "\n"
        "🤖 IA 1 : Cohere command-a\n"
        "🤖 IA 2 : OpenRouter Mistral\n"
        "💰 Prix : Binance + CoinGecko\n"
        "👛 Wallet Phantom surveille\n"
        "\n"
        "✅ Fonctions :\n"
        "- Budget en USD automatique\n"
        "- Montant et levier calcules\n"
        "- 1 position a la fois\n"
        "- Suivi TP et SL automatique\n"
        "- Reporting performances 20h\n"
        "- 20 news J et J-1 analysees\n"
        "\n"
        "⏰ Analyses : 8h / 13h / 20h\n"
        "📊 Reporting : 20h chaque soir\n"
        "🔔 Alertes mouvements > " + str(SEUIL_MOUVEMENT) + "%\n"
        "⏸️ Pause weekend : OUI\n"
        "\n"
        "Demarrage dans 1 minute..."
    )
    weekend_notified = False
    analyses_faites = set()
    dernier_prix = None
    dernier_check = 0
    news_vues = set()
    last_reporting_day = -1
    time.sleep(60)

    while True:
        now = datetime.utcnow()
        heure_paris_int = now.hour + 2
        heure_paris = str(heure_paris_int) + "h" + now.strftime("%M")
        cle_jour = str(now.date())

        if PAUSE_WEEKEND and is_weekend():
            if not weekend_notified:
                send_telegram(
                    "⏸️ BOT EN PAUSE - WEEKEND\n"
                    "Reprise automatique lundi 7h. 🌙"
                )
                weekend_notified = True
                analyses_faites = set()
                journal_trades = []
            time.sleep(3600)
            continue
        else:
            weekend_notified = False

        if is_heure_creuse():
            print("[" + now.strftime("%H:%M") + " UTC] Heure creuse")
            time.sleep(600)
            continue

        if heure_paris_int == 8 and cle_jour + "_matin" not in analyses_faites:
            ok = lancer_analyse("matin", heure_paris)
            if ok:
                analyses_faites.add(cle_jour + "_matin")
            else:
                time.sleep(1800)
            time.sleep(30)

        elif heure_paris_int == 13 and cle_jour + "_midi" not in analyses_faites:
            ok = lancer_analyse("midi", heure_paris)
            if ok:
                analyses_faites.add(cle_jour + "_midi")
            else:
                time.sleep(1800)
            time.sleep(30)

        elif heure_paris_int == 20 and cle_jour + "_soir" not in analyses_faites:
            ok = lancer_analyse("soir", heure_paris)
            if ok:
                analyses_faites.add(cle_jour + "_soir")
            else:
                time.sleep(1800)
            time.sleep(30)

        if heure_paris_int == 20 and now.day != last_reporting_day:
            time.sleep(90)
            send_telegram(reporting_soir())
            last_reporting_day = now.day
            journal_trades = []

        if time.time() - dernier_check >= 600:
            dernier_check = time.time()
            print("[" + now.strftime("%H:%M") + " UTC] Check alertes...")
            actuel = get_prix_actuel()
            if actuel:
                alerte_tp_sl = verifier_tp_sl(actuel["prix"])
                if alerte_tp_sl:
                    send_telegram(alerte_tp_sl)
                if dernier_prix is not None:
                    var = round((actuel["prix"] - dernier_prix) / dernier_prix * 100, 2)
                    if abs(var) >= SEUIL_MOUVEMENT:
                        sv = "+" if var >= 0 else ""
                        direction = "HAUSSE 📈" if var > 0 else "BAISSE 📉"
                        send_telegram(
                            "🚨 ALERTE MOUVEMENT BTC\n"
                            "\n"
                            "💰 Prix : " + str(actuel["prix"]) + " USD\n"
                            "📊 Variation : " + sv + str(var) + "%\n"
                            "📍 Direction : " + direction + "\n"
                            "\n"
                            "🤖 Analyse en cours..."
                        )
                        time.sleep(5)
                        lancer_analyse("alerte_mouvement", heure_paris)
                dernier_prix = actuel["prix"]

            news = get_news_btc()
            urgente, titre_urgent = detecter_news_urgente(news)
            if urgente and titre_urgent and titre_urgent not in news_vues:
                news_vues.add(titre_urgent)
                if len(news_vues) > 50:
                    news_vues.clear()
                send_telegram(
                    "📰 ALERTE NEWS IMPORTANTE\n"
                    "\n"
                    "🔔 " + titre_urgent[:200] + "\n"
                    "\n"
                    "🤖 Analyse en cours..."
                )
                time.sleep(5)
                lancer_analyse("alerte_news", heure_paris)

        time.sleep(60)


if __name__ == "__main__":
    run()
