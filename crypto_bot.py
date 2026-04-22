import requests
import time
from datetime import datetime

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════
TELEGRAM_TOKEN    = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID  = "6866451502"
ANTHROPIC_API_KEY = "METS_TA_CLE_ANTHROPIC_ICI"  # voir instructions bas

PAUSE_WEEKEND = True
HEURE_DEBUT   = 5    # 5h UTC = 7h Paris
HEURE_FIN     = 21   # 21h UTC = 23h Paris
# ═══════════════════════════════════════════

# ───────────────────────────────────────────
#  TELEGRAM
# ───────────────────────────────────────────
def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print("Telegram: " + str(r.status_code))
        return r.status_code == 200
    except Exception as e:
        print("Erreur Telegram: " + str(e))
        return False

# ───────────────────────────────────────────
#  FILTRES
# ───────────────────────────────────────────
def is_weekend():
    return datetime.utcnow().weekday() >= 5

def is_heure_creuse():
    h = datetime.utcnow().hour
    return h < HEURE_DEBUT or h >= HEURE_FIN

# ───────────────────────────────────────────
#  DONNEES PRIX BTC
# ───────────────────────────────────────────
def get_historique_btc():
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "7", "interval": "hourly"}
    try:
        time.sleep(5)
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "prices" not in data:
            return None
        prices  = [p[1] for p in data["prices"]]
        volumes = [v[1] for v in data["total_volumes"]]
        return prices, volumes
    except Exception as e:
        print("Erreur CoinGecko: " + str(e))
        return None

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
            "prix":      round(data["usd"], 2),
            "var_24h":   round(data.get("usd_24h_change", 0), 2),
            "var_7d":    round(data.get("usd_7d_change", 0), 2),
            "market_cap": data.get("usd_market_cap", 0),
        }
    except:
        return None

def preparer_resume_prix(prices, volumes, actuel):
    if not prices or len(prices) < 24:
        return "Donnees prix indisponibles."

    prix_now  = prices[-1]
    prix_1h   = prices[-2]
    prix_6h   = prices[-7]  if len(prices) >= 7  else prices[0]
    prix_24h  = prices[-25] if len(prices) >= 25 else prices[0]
    prix_7j   = prices[0]

    var_1h  = round((prix_now - prix_1h)  / prix_1h  * 100, 2)
    var_6h  = round((prix_now - prix_6h)  / prix_6h  * 100, 2)
    var_24h = round((prix_now - prix_24h) / prix_24h * 100, 2)
    var_7j  = round((prix_now - prix_7j)  / prix_7j  * 100, 2)

    # Plus haut et plus bas 24h
    haut_24h = round(max(prices[-25:]), 2)
    bas_24h  = round(min(prices[-25:]), 2)
    haut_7j  = round(max(prices), 2)
    bas_7j   = round(min(prices), 2)

    # Volume moyen
    vol_recent = sum(volumes[-6:]) / 6 if len(volumes) >= 6 else 0
    vol_ancien = sum(volumes[-24:-6]) / 18 if len(volumes) >= 24 else vol_recent
    tendance_vol = "en hausse" if vol_recent > vol_ancien * 1.1 else "en baisse" if vol_recent < vol_ancien * 0.9 else "stable"

    # Momentum
    hausse_count = sum(1 for i in range(1, min(25, len(prices))) if prices[-i] > prices[-i-1])
    momentum = "haussier" if hausse_count > 12 else "baissier" if hausse_count < 8 else "neutre"

    resume = (
        "PRIX ACTUEL : " + str(actuel["prix"]) + " USD\n"
        "Variation 1H  : " + ("+" if var_1h >= 0 else "") + str(var_1h) + "%\n"
        "Variation 6H  : " + ("+" if var_6h >= 0 else "") + str(var_6h) + "%\n"
        "Variation 24H : " + ("+" if var_24h >= 0 else "") + str(var_24h) + "%\n"
        "Variation 7J  : " + ("+" if var_7j >= 0 else "") + str(var_7j) + "%\n"
        "Plus haut 24H : " + str(haut_24h) + " USD\n"
        "Plus bas 24H  : " + str(bas_24h)  + " USD\n"
        "Plus haut 7J  : " + str(haut_7j) + " USD\n"
        "Plus bas 7J   : " + str(bas_7j)  + " USD\n"
        "Volume        : " + tendance_vol + "\n"
        "Momentum 24H  : " + momentum + "\n"
    )
    return resume

# ───────────────────────────────────────────
#  NEWS BTC (CryptoPanic API gratuite)
# ───────────────────────────────────────────
def get_news_btc():
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        "auth_token": "free",
        "currencies": "BTC",
        "filter":     "hot",
        "public":     "true",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        titres = []
        for item in data.get("results", [])[:10]:
            titre = item.get("title", "")
            if titre:
                titres.append(titre)
        return titres
    except Exception as e:
        print("Erreur news: " + str(e))
        return []

def get_news_backup():
    """Source de secours si CryptoPanic indisponible."""
    url = "https://api.coingecko.com/api/v3/news"
    try:
        time.sleep(3)
        r = requests.get(url, timeout=10)
        data = r.json()
        titres = []
        for item in data.get("data", [])[:8]:
            titre = item.get("title", "")
            if titre and "bitcoin" in titre.lower() or "btc" in titre.lower() or "crypto" in titre.lower():
                titres.append(titre)
        return titres[:8]
    except:
        return []

# ───────────────────────────────────────────
#  ANALYSE IA VIA ANTHROPIC
# ───────────────────────────────────────────
def analyser_avec_ia(resume_prix, news, heure_paris):
    news_texte = ""
    if news:
        for i, titre in enumerate(news[:8]):
            news_texte += str(i+1) + ". " + titre + "\n"
    else:
        news_texte = "Aucune news disponible pour le moment."

    prompt = (
        "Tu es un analyste crypto expert specialise sur Bitcoin (BTC).\n"
        "Nous sommes le " + datetime.utcnow().strftime("%d/%m/%Y") + " a " + heure_paris + " (heure Paris).\n\n"
        "DONNEES DE PRIX BTC :\n"
        "" + resume_prix + "\n"
        "NEWS BTC DU MOMENT :\n"
        "" + news_texte + "\n\n"
        "En te basant sur ces donnees, redige une analyse TRES COURTE et DIRECTE en francais.\n"
        "Format OBLIGATOIRE (respecte exactement ce format) :\n\n"
        "CONSEIL : [LONG / SHORT / ATTENDRE]\n"
        "CONFIANCE : [Faible / Moyenne / Forte]\n\n"
        "CONTEXTE (2 phrases max) :\n"
        "[Resume ce qui se passe sur BTC en ce moment]\n\n"
        "RAISONS (3 points max) :\n"
        "- [raison 1]\n"
        "- [raison 2]\n"
        "- [raison 3]\n\n"
        "RISQUES (1-2 points) :\n"
        "- [risque principal]\n\n"
        "NIVEAUX CLES :\n"
        "Support : [prix]\n"
        "Resistance : [prix]\n\n"
        "Sois direct, concis, et base toi uniquement sur les donnees fournies."
    )

    headers = {
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 600,
        "messages":   [{"role": "user", "content": prompt}],
    }

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
            timeout=30,
        )
        data = r.json()
        if "content" in data and len(data["content"]) > 0:
            return data["content"][0]["text"]
        else:
            print("Erreur API Anthropic: " + str(data))
            return None
    except Exception as e:
        print("Erreur Anthropic: " + str(e))
        return None

# ───────────────────────────────────────────
#  FORMATAGE MESSAGE FINAL
# ───────────────────────────────────────────
def format_message_final(analyse, prix, heure_paris):
    now = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    return (
        "================================\n"
        "  ANALYSE BTC - " + heure_paris + " Paris\n"
        "================================\n"
        "Prix : " + str(prix) + " USD\n"
        "--------------------------------\n"
        "" + analyse + "\n"
        "--------------------------------\n"
        "Pas un conseil financier\n"
        "================================"
    )

# ───────────────────────────────────────────
#  BOUCLE PRINCIPALE
# ───────────────────────────────────────────
def run():
    print("Bot Predictif BTC demarre")
    send_telegram(
        "================================\n"
        "  BOT PREDICTIF BTC V1\n"
        "================================\n"
        "Mode     : Analyse IA + News\n"
        "Frequence: toutes les heures\n"
        "Filtre   : 7h - 23h Paris\n"
        "Pause WE : OUI\n"
        "================================\n"
        "Premiere analyse dans 1 minute..."
    )

    weekend_notified   = False
    dern​​​​​​​​​​​​​​​​
