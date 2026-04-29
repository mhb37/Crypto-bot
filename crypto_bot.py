import requests
import time
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

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
            "market_cap": 0,
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
                "include_market_cap": "true",
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()["bitcoin"]
            return {
                "prix": round(data["usd"], 2),
                "var_24h": round(data.get("usd_24h_change", 0), 2),
                "var_7d": round(data.get("usd_7d_change", 0), 2),
                "market_cap": round(data.get("usd_market_cap", 0) / 1e9, 1),
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
            cd = data.get("community_data", {})
            return {
                "ath": round(md.get("ath", {}).get("usd", 0), 0),
                "ath_pct": round(md.get("ath_change_percentage", {}).get("usd", 0), 1),
                "sentiment_up": data.get("sentiment_votes_up_percentage", 0),
                "reddit_subscribers": cd.get("reddit_subscribers", 0),
                "reddit_active": cd.get("reddit_active_accounts_48h", 0),
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
        params = {"rss_url": "https://cointelegraph.com/rss/tag/bitcoin", "count": "10"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for item in data.get("items", [])[:10]:
            titre = item.get("title", "")
            if titre and titre not in titres:
                titres.append(titre)
    except Exception as e:
        print("Erreur Cointelegraph: " + str(e))
    try:
        url = "https://api.rss2json.com/v1/api.json"
        params = {"rss_url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "count": "10"}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        for item in data.get("items", [])[:10]:
            titre = item.get("title", "")
            if titre and titre not in titres:
                t = titre.lower()
                if "bitcoin" in t or "btc" in t or "crypto" in t:
                    titres.append(titre)
    except Exception as e:
        print("Erreur CoinDesk: " + str(e))
    print("News recuperees: " + str(len(titres)))
    return titres[:15]


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
                "score_pos": score_pos,
                "score_neg": score_neg,
                "score_net": score_net,
                "top_posts": titres_reddit[:3],
                "total_posts": len(posts),
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


def construire_prompt(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte):
    date_str = datetime.utcnow().strftime("%d/%m/%Y")
    if fear_greed:
        fg = (
            "Indice Fear and Greed actuel : " + str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ")\n"
            "Hier : " + str(fear_greed["hier"]) + "/100\n"
            "Avant-hier : " + str(fear_greed["avant_hier"]) + "/100"
        )
    else:
        fg = "Fear and Greed : non disponible"
    if donnees_avancees:
        da = (
            "ATH Bitcoin : " + str(int(donnees_avancees.get("ath", 0))) + " USD\n"
            "Distance de l ATH : " + str(donnees_avancees.get("ath_pct", 0)) + "%\n"
            "Sentiment communaute : " + str(donnees_avancees.get("sentiment_up", 0)) + "% haussier\n"
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
        for i, titre in enumerate(news[:10]):
            nw = nw + str(i + 1) + ". " + titre + "\n"
    else:
        nw = "Aucune news disponible."
    if contexte == "matin":
        instruction = (
            "C est l analyse du MATIN. Tu dois :\n"
            "1. Resumer ce qui s est passe la nuit sur BTC\n"
            "2. Donner une vision claire de la journee a venir\n"
            "3. Identifier les opportunites et les risques\n"
            "4. Conseiller sur la direction a prendre aujourd hui"
        )
    elif contexte == "midi":
        instruction = (
            "C est le POINT DU MIDI. Tu dois :\n"
            "1. Faire le bilan de la matinee\n"
            "2. Analyser si la tendance du matin se confirme\n"
            "3. Donner une direction pour l apres-midi\n"
            "4. Identifier les niveaux cles a surveiller"
        )
    elif contexte == "soir":
        instruction = (
            "C est le BILAN DU SOIR. Tu dois :\n"
            "1. Resumer la journee complete sur BTC\n"
            "2. Analyser les evenements marquants du jour\n"
            "3. Donner une vision pour demain\n"
            "4. Conseiller sur les positions a maintenir ou fermer"
        )
    elif contexte == "alerte_mouvement":
        instruction = (
            "ALERTE URGENTE : un mouvement important vient d etre detecte sur BTC.\n"
            "Tu dois analyser immediatement :\n"
            "1. La nature et la force de ce mouvement\n"
            "2. Si c est une opportunite d entrer ou de sortir\n"
            "3. Les niveaux cles a surveiller maintenant\n"
            "4. Le risque associe a ce mouvement"
        )
    elif contexte == "alerte_news":
        instruction = (
            "ALERTE URGENTE : une news importante vient d etre detectee.\n"
            "Tu dois analyser immediatement :\n"
            "1. L impact potentiel de cette news sur BTC\n"
            "2. Si c est positif ou negatif pour le prix\n"
            "3. La reaction probable du marche\n"
            "4. Ce qu il faut faire maintenant"
        )
    else:
        instruction = "Analyse la situation actuelle de BTC de facon complete."

    return (
        "Tu es un expert analyste Bitcoin reconnu, tu reponds UNIQUEMENT en francais.\n"
        "Nous sommes le " + date_str + " a " + heure_paris + " heure de Paris.\n\n"
        + instruction + "\n\n"
        "=== DONNEES DE PRIX BTC ===\n" + resume_prix + "\n"
        "=== INDICE FEAR AND GREED ===\n" + fg + "\n\n"
        "=== DONNEES MARCHE ===\n" + da + "\n"
        "=== SENTIMENT REDDIT r/Bitcoin ===\n" + rd + "\n\n"
        "=== GOOGLE TRENDS ===\n" + tr + "\n\n"
        "=== ACTUALITES CHAUDES (traduis-les en francais) ===\n" + nw + "\n"
        "Reponds UNIQUEMENT en francais et EXACTEMENT dans ce format :\n\n"
        "CONSEIL : LONG ou SHORT ou ATTENDRE\n"
        "CONFIANCE : Faible ou Moyenne ou Forte\n\n"
        "RESUME DE LA SITUATION :\n"
        "3 phrases maximum en francais sur la situation actuelle de BTC\n\n"
        "ACTUALITES DU MOMENT :\n"
        "- actualite 1 traduite en francais et resumee\n"
        "- actualite 2 traduite en francais et resumee\n"
        "- actualite 3 traduite en francais et resumee\n\n"
        "RAISONS DU CONSEIL :\n"
        "- raison 1\n"
        "- raison 2\n"
        "- raison 3\n\n"
        "RISQUES A SURVEILLER :\n"
        "- risque principal\n"
        "- risque secondaire\n\n"
        "NIVEAUX CLES :\n"
        "Support    : prix en USD\n"
        "Resistance : prix en USD\n"
        "Objectif   : prix en USD si LONG ou SHORT\n\n"
        "SENTIMENT GLOBAL : Haussier ou Baissier ou Neutre\n"
    )


def analyser_avec_gemini(prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
    }
    for tentative in range(MAX_RETRY):
        try:
            print("Gemini tentative " + str(tentative + 1))
            r = requests.post(url, json=body, timeout=30)
            data = r.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur Gemini tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def analyser_avec_cohere(prompt):
    headers = {
        "Authorization": "Bearer " + COHERE_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "model": "command-r-plus",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 700,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("Cohere tentative " + str(tentative + 1))
            r = requests.post(
                "https://api.cohere.com/v2/chat",
                headers=headers,
                json=body,
                timeout=30
            )
            data = r.json()
            print("Cohere reponse: " + str(data)[:200])
            message = data.get("message", {})
            content = message.get("content", [])
            if content and len(content) > 0:
                return content[0].get("text", "").strip()
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
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 700,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("OpenRouter tentative " + str(tentative + 1))
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body, timeout=30)
            data = r.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content.strip()
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur OpenRouter tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def analyser_ia(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte):
    prompt = construire_prompt(resume_prix, fear_greed, donnees_avancees, news, reddit, trends, heure_paris, contexte)
    print("Essai Gemini...")
    analyse = analyser_avec_gemini(prompt)
    if analyse:
        print("Gemini OK")
        return analyse, "Gemini"
    print("Gemini echoue, essai Cohere...")
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


def format_message(actuel, fear_greed, reddit, trends, heure_paris, contexte, analyse, ia_utilisee):
    s24 = "+" if actuel["var_24h"] >= 0 else ""
    s7 = "+" if actuel["var_7d"] >= 0 else ""
    fg_line = ""
    if fear_greed:
        fg_line = "Fear&Greed : " + str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ")\n"
    reddit_line = ""
    if reddit:
        reddit_line = "Reddit     : " + reddit["sentiment"] + "\n"
    trends_line = ""
    if trends and trends.get("btc_trending"):
        trends_line = "Google     : Bitcoin en tendance\n"
    return (
        "================================\n"
        "  " + label_analyse(contexte, heure_paris) + "\n"
        "================================\n"
        "Prix : " + str(actuel["prix"]) + " USD\n"
        "24H  : " + s24 + str(actuel["var_24h"]) + "%\n"
        "7J   : " + s7 + str(actuel["var_7d"]) + "%\n"
        + fg_line + reddit_line + trends_line
        + "IA   : " + ia_utilisee + "\n"
        "--------------------------------\n"
        + analyse
        + "\n--------------------------------\n"
        "Pas un conseil financier\n"
        "================================"
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
    }


def lancer_analyse(contexte, heure_paris):
    print("[" + datetime.utcnow().strftime("%H:%M") + " UTC] Analyse " + contexte + "...")
    d = collecter_donnees()
    if d is None:
        send_telegram(
            "================================\n"
            "  ERREUR DONNEES - " + heure_paris + "\n"
            "================================\n"
            "Impossible de recuperer les donnees.\n"
            "Nouvelle tentative dans 30 min.\n"
            "================================"
        )
        return False
    analyse, ia = analyser_ia(
        d["resume_prix"], d["fear_greed"], d["donnees_avancees"],
        d["news"], d["reddit"], d["trends"], heure_paris, contexte
    )
    if analyse is None:
        send_telegram(
            "================================\n"
            "  ERREUR IA - " + heure_paris + "\n"
            "================================\n"
            "Prix BTC : " + str(d["actuel"]["prix"]) + " USD\n"
            "Les 3 IA sont indisponibles.\n"
            "Prochaine analyse prevue.\n"
            "================================"
        )
        return False
    msg = format_message(
        d["actuel"], d["fear_greed"], d["reddit"], d["trends"],
        heure_paris, contexte, analyse, ia
    )
    send_telegram(msg)
    print("Analyse " + contexte + " envoyee via " + ia)
    return True


def run():
    print("Bot BTC V5 demarre")
    send_telegram(
        "================================\n"
        "  BOT BTC INTELLIGENT V5\n"
        "================================\n"
        "IA 1    : Google Gemini\n"
        "IA 2    : Cohere (secours)\n"
        "IA 3    : OpenRouter Llama (secours)\n"
        "Prix    : Binance + CoinGecko\n"
        "Sources : Fear&Greed, News x3\n"
        "          Reddit, Google Trends\n"
        "Langue  : Francais complet\n"
        "Analyses: 8h / 13h / 20h Paris\n"
        "Alertes : Mouvements > " + str(SEUIL_MOUVEMENT) + "%\n"
        "          News importantes\n"
        "Pause WE: OUI\n"
        "================================\n"
        "Demarrage dans 1 minute..."
    )
    weekend_notified = False
    analyses_faites = set()
    dernier_prix = None
    dernier_check = 0
    news_vues = set()
    time.sleep(60)
    while True:
        now = datetime.utcnow()
        heure_paris_int = now.hour + 2
        heure_paris = str(heure_paris_int) + "h" + now.strftime("%M")
        cle_jour = str(now.date())
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
                analyses_faites = set()
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
        if time.time() - dernier_check >= 600:
            dernier_check = time.time()
            print("[" + now.strftime("%H:%M") + " UTC] Check alertes...")
            actuel = get_prix_actuel()
            if actuel:
                if dernier_prix is not None:
                    var = round((actuel["prix"] - dernier_prix) / dernier_prix * 100, 2)
                    if abs(var) >= SEUIL_MOUVEMENT:
                        sv = "+" if var >= 0 else ""
                        direction = "HAUSSE" if var > 0 else "BAISSE"
                        send_telegram(
                            "================================\n"
                            "  ALERTE MOUVEMENT BTC\n"
                            "================================\n"
                            "Prix : " + str(actuel["prix"]) + " USD\n"
                            "Variation : " + sv + str(var) + "%\n"
                            "Direction : " + direction + "\n"
                            "================================\n"
                            "Analyse en cours...\n"
                            "================================"
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
                    "================================\n"
                    "  ALERTE NEWS IMPORTANTE\n"
                    "================================\n"
                    "NEWS : " + titre_urgent[:200] + "\n"
                    "================================\n"
                    "Analyse en cours...\n"
                    "================================"
                )
                time.sleep(5)
                lancer_analyse("alerte_news", heure_paris)
        time.sleep(60)


if __name__ == "__main__":
    run()
