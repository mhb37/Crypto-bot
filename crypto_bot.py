import requests
import time
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"
COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

CAPITAL_DEPART = 50.0
RISQUE_PAR_TRADE = 0.10
LEVIER = 5
PAUSE_WEEKEND = True
HEURE_DEBUT = 5
HEURE_FIN = 21
MAX_RETRY = 3
RETRY_DELAY = 20

MOTS_POSITIFS_REDDIT = [
    "bullish", "moon", "buy", "long", "pump", "green", "up", "rally",
    "support", "breakout", "accumulate", "hold", "hodl", "ath", "surge"
]

MOTS_NEGATIFS_REDDIT = [
    "bearish", "crash", "dump", "sell", "short", "red", "down", "bear",
    "fear", "panic", "drop", "fall", "resistance", "bubble", "scam"
]

MOTS_URGENTS = [
    "etf", "sec", "blackrock", "ban", "hack", "crash", "record",
    "bankruptcy", "arrest", "regulation", "emergency", "breaking",
    "federal reserve", "inflation", "halving", "liquidation", "whale", "scam"
]

capital = CAPITAL_DEPART
position = None
historique_trades = []
lecons_apprises = []


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
    return datetime.utcnow().hour < HEURE_DEBUT or datetime.utcnow().hour >= HEURE_FIN


def get_prix_actuel():
    for tentative in range(MAX_RETRY):
        try:
            time.sleep(10)
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "bitcoin",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            btc = data.get("bitcoin", {})
            if "usd" in btc:
                return {
                    "prix": round(btc["usd"], 2),
                    "var_24h": round(btc.get("usd_24h_change", 0), 2),
                    "high_24h": 0,
                    "low_24h": 0,
                    "volume": 0,
                }
        except Exception as e:
            print("Erreur prix tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(60)
    return None



def get_historique_btc():
    for tentative in range(MAX_RETRY):
        try:
            time.sleep(8)
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
            print("Erreur historique tentative " + str(tentative + 1) + ": " + str(e))
            time.sleep(RETRY_DELAY)
    return None, None


def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=3", timeout=10)
        data = r.json()
        results = data.get("data", [])
        if results:
            return {
                "valeur": results[0].get("value", "?"),
                "label": results[0].get("value_classification", "?"),
                "hier": results[1].get("value", "?") if len(results) > 1 else "?",
            }
    except Exception as e:
        print("Erreur Fear and Greed: " + str(e))
    return None


def get_news_btc():
    titres = []
    try:
        time.sleep(3)
        r = requests.get("https://api.coingecko.com/api/v3/news", timeout=10)
        data = r.json()
        for item in data.get("data", [])[:8]:
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
    return titres[:15]


def get_reddit_sentiment():
    try:
        headers = {"User-Agent": "Mozilla/5.0 CryptoBotAnalysis/1.0"}
        r = requests.get(
            "https://www.reddit.com/r/Bitcoin/hot.json?limit=25",
            headers=headers,
            timeout=15
        )
        if r.status_code != 200:
            return "Neutre"
        data = r.json()
        posts = data.get("data", {}).get("children", [])
        score_pos = 0
        score_neg = 0
        for post in posts:
            titre = post.get("data", {}).get("title", "").lower()
            for mot in MOTS_POSITIFS_REDDIT:
                if mot in titre:
                    score_pos += 1
            for mot in MOTS_NEGATIFS_REDDIT:
                if mot in titre:
                    score_neg += 1
        score_net = score_pos - score_neg
        if score_net >= 3:
            return "Tres haussier"
        elif score_net >= 1:
            return "Haussier"
        elif score_net <= -3:
            return "Tres baissier"
        elif score_net <= -1:
            return "Baissier"
        return "Neutre"
    except Exception as e:
        print("Erreur Reddit: " + str(e))
        return "Neutre"



def preparer_resume_prix(prices, volumes, actuel):
    if not prices or len(prices) < 24:
        return "Donnees indisponibles"
    prix_now = prices[-1]
    prix_1h = prices[-2] if len(prices) >= 2 else prix_now
    prix_4h = prices[-5] if len(prices) >= 5 else prix_now
    prix_24h = prices[-25] if len(prices) >= 25 else prices[0]
    prix_7j = prices[0]

    def v(a, b):
        return round((a - b) / b * 100, 2)

    var_1h = v(prix_now, prix_1h)
    var_4h = v(prix_now, prix_4h)
    var_24h = v(prix_now, prix_24h)
    var_7j = v(prix_now, prix_7j)
    support = round(min(prices[-48:] if len(prices) >= 48 else prices), 0)
    resistance = round(max(prices[-48:] if len(prices) >= 48 else prices), 0)
    vol_recent = sum(volumes[-6:]) / 6 if len(volumes) >= 6 else 0
    vol_ancien = sum(volumes[-24:-6]) / 18 if len(volumes) >= 24 else vol_recent
    tendance_vol = "hausse" if vol_recent > vol_ancien * 1.1 else "baisse" if vol_recent < vol_ancien * 0.9 else "stable"

    def s(val):
        return "+" if val >= 0 else ""

    return (
        "Prix : " + str(actuel["prix"]) + " USD\n"
        "Variation 1H  : " + s(var_1h) + str(var_1h) + "%\n"
        "Variation 4H  : " + s(var_4h) + str(var_4h) + "%\n"
        "Variation 24H : " + s(var_24h) + str(var_24h) + "%\n"
        "Variation 7J  : " + s(var_7j) + str(var_7j) + "%\n"
        "Support    : " + str(support) + " USD\n"
        "Resistance : " + str(resistance) + " USD\n"
        "Volume : " + tendance_vol + "\n"
    )


def ouvrir_position(direction, prix, tp1, tp2, sl, raison):
    global position, capital
    montant = round(capital * RISQUE_PAR_TRADE, 2)
    position_totale = round(montant * LEVIER, 2)
    position = {
        "direction": direction,
        "prix_entree": prix,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "montant": montant,
        "position_totale": position_totale,
        "tp1_atteint": False,
        "heure": datetime.utcnow().strftime("%d/%m %H:%M UTC"),
        "raison": raison,
    }
    send_telegram(
        "🤖 TRADE OUVERT (SIMULATION)\n"
        "\n"
        "📍 Direction : " + direction + "\n"
        "💰 Prix entree : " + str(prix) + " USD\n"
        "🎯 TP1 : " + str(tp1) + " USD\n"
        "🎯 TP2 : " + str(tp2) + " USD\n"
        "🛑 SL  : " + str(sl) + " USD\n"
        "\n"
        "💵 Capital risque : " + str(montant) + " USD\n"
        "📊 Position totale : " + str(position_totale) + " USD (x" + str(LEVIER) + ")\n"
        "💼 Capital total : " + str(round(capital, 2)) + " USD\n"
        "\n"
        "📝 " + raison[:200] + "\n"
        "\n"
        "⚠️ SIMULATION - Pas de vrai argent"
    )


def fermer_position(prix_sortie, raison_fermeture):
    global position, capital, historique_trades, lecons_apprises
    if not position:
        return
    direction = position["direction"]
    prix_entree = position["prix_entree"]
    montant = position["montant"]
    if direction == "LONG":
        pct = round((prix_sortie - prix_entree) / prix_entree * 100, 2)
    else:
        pct = round((prix_entree - prix_sortie) / prix_entree * 100, 2)
    gain_brut = round(montant * LEVIER * pct / 100, 2)
    capital = round(capital + gain_brut, 2)
    resultat = "GAGNANT" if gain_brut >= 0 else "PERDANT"
    trade = {
        "direction": direction,
        "prix_entree": prix_entree,
        "prix_sortie": prix_sortie,
        "pct": pct,
        "gain_usd": gain_brut,
        "resultat": resultat,
        "raison_sortie": raison_fermeture,
        "heure_sortie": datetime.utcnow().strftime("%d/%m %H:%M UTC"),
    }
    historique_trades.append(trade)
    if resultat == "PERDANT":
        lecon = "Trade " + direction + " perdant " + str(pct) + "%. Entree " + str(prix_entree) + " sortie " + str(prix_sortie) + ". " + raison_fermeture
        lecons_apprises.append(lecon)
        if len(lecons_apprises) > 10:
            lecons_apprises.pop(0)
    emoji = "✅" if resultat == "GAGNANT" else "❌"
    s = "+" if gain_brut >= 0 else ""
    send_telegram(
        emoji + " TRADE FERME (SIMULATION)\n"
        "\n"
        "📍 Direction : " + direction + "\n"
        "💰 Entree : " + str(prix_entree) + " USD\n"
        "💰 Sortie : " + str(prix_sortie) + " USD\n"
        "📊 Performance : " + s + str(pct) + "%\n"
        "💵 Gain/Perte : " + s + str(gain_brut) + " USD\n"
        "\n"
        "💼 Capital actuel : " + str(capital) + " USD\n"
        "📈 vs Depart : " + ("+" if capital >= CAPITAL_DEPART else "") + str(round(capital - CAPITAL_DEPART, 2)) + " USD\n"
        "\n"
        "⚠️ SIMULATION - Pas de vrai argent"
    )
    position = None


def verifier_tp_sl(prix_actuel):
    global position
    if not position:
        return
    direction = position["direction"]
    tp1 = position["tp1"]
    tp2 = position["tp2"]
    sl = position["sl"]
    prix_entree = position["prix_entree"]
    if direction == "LONG":
        if tp2 > 0 and prix_actuel >= tp2:
            fermer_position(prix_actuel, "TP2 atteint")
        elif tp1 > 0 and prix_actuel >= tp1 and not position.get("tp1_atteint"):
            position["tp1_atteint"] = True
            pct = round((prix_actuel - prix_entree) / prix_entree * 100, 2)
            gain = round(position["montant"] * LEVIER * pct / 100, 2)
            send_telegram(
                "🎯 TP1 ATTEINT (SIMULATION)\n"
                "LONG en cours\n"
                "Entree : " + str(prix_entree) + " USD\n"
                "Actuel : " + str(prix_actuel) + " USD\n"
                "Profit : +" + str(pct) + "% (+" + str(gain) + " USD)\n"
                "TP2 vise : " + str(tp2) + " USD\n"
                "⚠️ SIMULATION"
            )
        elif sl > 0 and prix_actuel <= sl:
            fermer_position(prix_actuel, "Stop Loss declenche")
    elif direction == "SHORT":
        if tp2 > 0 and prix_actuel <= tp2:
            fermer_position(prix_actuel, "TP2 atteint")
        elif tp1 > 0 and prix_actuel <= tp1 and not position.get("tp1_atteint"):
            position["tp1_atteint"] = True
            pct = round((prix_entree - prix_actuel) / prix_entree * 100, 2)
            gain = round(position["montant"] * LEVIER * pct / 100, 2)
            send_telegram(
                "🎯 TP1 ATTEINT (SIMULATION)\n"
                "SHORT en cours\n"
                "Entree : " + str(prix_entree) + " USD\n"
                "Actuel : " + str(prix_actuel) + " USD\n"
                "Profit : +" + str(pct) + "% (+" + str(gain) + " USD)\n"
                "TP2 vise : " + str(tp2) + " USD\n"
                "⚠️ SIMULATION"
            )
        elif sl > 0 and prix_actuel >= sl:
            fermer_position(prix_actuel, "Stop Loss declenche")


def construire_prompt_decision(resume_prix, fear_greed, news, reddit_sentiment):
    date_str = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    fg_txt = "non disponible"
    if fear_greed:
        fg_txt = str(fear_greed["valeur"]) + "/100 (" + fear_greed["label"] + ") | Hier : " + str(fear_greed["hier"])
    nw_txt = ""
    for i, titre in enumerate(news[:10]):
        nw_txt = nw_txt + str(i+1) + ". " + titre + "\n"
    pos_txt = "Aucune position ouverte."
    if position:
        pos_txt = (
            "POSITION OUVERTE : " + position["direction"] + "\n"
            "Entree : " + str(position["prix_entree"]) + " USD\n"
            "TP1=" + str(position["tp1"]) + " TP2=" + str(position["tp2"]) + " SL=" + str(position["sl"]) + "\n"
            "NE PAS ouvrir de nouvelle position !"
        )
    lecons_txt = "Aucune lecon pour l instant."
    if lecons_apprises:
        lecons_txt = ""
        for l in lecons_apprises[-5:]:
            lecons_txt = lecons_txt + "- " + l + "\n"
    historique_txt = "Aucun trade."
    if historique_trades:
        total = len(historique_trades)
        gagnants = len([t for t in historique_trades if t["resultat"] == "GAGNANT"])
        pct_moyen = round(sum(t["pct"] for t in historique_trades) / total, 2)
        historique_txt = (
            str(total) + " trades | Taux reussite : " + str(round(gagnants / total * 100, 0)) + "% | Perf moyenne : " + str(pct_moyen) + "%"
        )
    return (
        "Tu es un bot de trading Bitcoin autonome. Reponds UNIQUEMENT en francais.\n"
        "Tu geres un portefeuille simule de " + str(round(capital, 2)) + " USD (depart : " + str(CAPITAL_DEPART) + " USD).\n"
        "Levier : x" + str(LEVIER) + " | Risque par trade : " + str(int(RISQUE_PAR_TRADE * 100)) + "% du capital.\n\n"
        "Date : " + date_str + " UTC\n\n"
        "=== POSITION EN COURS ===\n" + pos_txt + "\n\n"
        "=== HISTORIQUE ===\n" + historique_txt + "\n\n"
        "=== LECONS APPRISES ===\n" + lecons_txt + "\n\n"
        "=== PRIX BTC ===\n" + resume_prix + "\n"
        "=== FEAR AND GREED ===\n" + fg_txt + "\n\n"
        "=== SENTIMENT REDDIT ===\n" + reddit_sentiment + "\n\n"
        "=== ACTUALITES ===\n" + nw_txt + "\n"
        "Prends une decision IMMEDIATE. Reponds UNIQUEMENT avec ce JSON :\n\n"
        "{\n"
        "  \"decision\": \"LONG\" ou \"SHORT\" ou \"ATTENDRE\" ou \"FERMER\",\n"
        "  \"conviction\": 1 a 10,\n"
        "  \"tp1\": prix USD ou 0,\n"
        "  \"tp2\": prix USD ou 0,\n"
        "  \"sl\": prix USD ou 0,\n"
        "  \"raison\": \"explication courte en francais\"\n"
        "}\n\n"
        "Reponds UNIQUEMENT avec le JSON rien d autre."
    )


def appeler_ia_decision(prompt):
    headers = {
        "Authorization": "Bearer " + COHERE_API_KEY,
        "Content-Type": "application/json",
    }
    body = {
        "model": "command-a-03-2025",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("Cohere decision tentative " + str(tentative + 1))
            r = requests.post("https://api.cohere.com/v2/chat", headers=headers, json=body, timeout=30)
            data = r.json()
            content = data.get("message", {}).get("content", [])
            if content and len(content) > 0:
                text = content[0].get("text", "").strip()
                if text and len(text) > 5:
                    return text
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur Cohere: " + str(e))
            time.sleep(RETRY_DELAY)
    headers2 = {
        "Authorization": "Bearer " + OPENROUTER_API_KEY,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://crypto-bot.app",
        "X-Title": "CryptoBotBTC",
    }
    body2 = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    for tentative in range(MAX_RETRY):
        try:
            print("OpenRouter decision tentative " + str(tentative + 1))
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers2, json=body2, timeout=30)
            data = r.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content and len(content) > 5:
                    return content.strip()
            time.sleep(RETRY_DELAY)
        except Exception as e:
            print("Erreur OpenRouter: " + str(e))
            time.sleep(RETRY_DELAY)
    return None


def parser_decision(texte):
    try:
        debut = texte.find("{")
        fin = texte.rfind("}") + 1
        if debut >= 0 and fin > debut:
            return json.loads(texte[debut:fin])
    except Exception as e:
        print("Erreur parsing JSON: " + str(e))
        print("Texte recu: " + texte[:200])
    return None


def prendre_decision():
    actuel = get_prix_actuel()
    if not actuel:
        print("Prix indisponible")
        return
    verifier_tp_sl(actuel["prix"])
    prices, volumes = get_historique_btc()
    if not prices:
        print("Historique indisponible")
        return
    resume_prix = preparer_resume_prix(prices, volumes, actuel)
    fear_greed = get_fear_greed()
    news = get_news_btc()
    reddit = get_reddit_sentiment()
    prompt = construire_prompt_decision(resume_prix, fear_greed, news, reddit)
    texte_ia = appeler_ia_decision(prompt)
    if not texte_ia:
        print("IA indisponible")
        return
    decision = parser_decision(texte_ia)
    if not decision:
        print("JSON invalide")
        return
    action = decision.get("decision", "ATTENDRE")
    conviction = decision.get("conviction", 0)
    tp1 = decision.get("tp1", 0)
    tp2 = decision.get("tp2", 0)
    sl = decision.get("sl", 0)
    raison = decision.get("raison", "")
    print("Decision : " + action + " conviction=" + str(conviction))
    if action == "FERMER" and position:
        fermer_position(actuel["prix"], "Fermeture IA : " + raison)
    elif action in ("LONG", "SHORT") and not position:
        if conviction >= 6 and sl > 0:
            ouvrir_position(action, actuel["prix"], tp1, tp2, sl, raison)
        else:
            print("Conviction trop faible ou SL manquant")
    elif action == "ATTENDRE":
        print("ATTENDRE : " + raison)
    elif action in ("LONG", "SHORT") and position:
        print("Position deja ouverte - impossible d ouvrir")


def envoyer_rapport():
    now = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
    perf_totale = round(capital - CAPITAL_DEPART, 2)
    perf_pct = round((capital - CAPITAL_DEPART) / CAPITAL_DEPART * 100, 2)
    msg = (
        "📊 RAPPORT PAPER TRADING\n"
        "─────────────────────────\n"
        "" + now + " UTC\n"
        "\n"
        "💼 Capital depart  : " + str(CAPITAL_DEPART) + " USD\n"
        "💰 Capital actuel  : " + str(round(capital, 2)) + " USD\n"
        "📈 Performance     : " + ("+" if perf_totale >= 0 else "") + str(perf_totale) + " USD (" + ("+" if perf_pct >= 0 else "") + str(perf_pct) + "%)\n"
        "\n"
    )
    if position:
        actuel = get_prix_actuel()
        if actuel:
            if position["direction"] == "LONG":
                pct_actuel = round((actuel["prix"] - position["prix_entree"]) / position["prix_entree"] * 100, 2)
            else:
                pct_actuel = round((position["prix_entree"] - actuel["prix"]) / position["prix_entree"] * 100, 2)
            gain_actuel = round(position["montant"] * LEVIER * pct_actuel / 100, 2)
            msg = msg + (
                "📍 POSITION EN COURS\n"
                "Direction : " + position["direction"] + "\n"
                "Entree    : " + str(position["prix_entree"]) + " USD\n"
                "Actuel    : " + str(actuel["prix"]) + " USD\n"
                "P&L       : " + ("+" if pct_actuel >= 0 else "") + str(pct_actuel) + "% (" + ("+" if gain_actuel >= 0 else "") + str(gain_actuel) + " USD)\n"
                "TP1=" + str(position["tp1"]) + " TP2=" + str(position["tp2"]) + " SL=" + str(position["sl"]) + "\n\n"
            )
    if historique_trades:
        total = len(historique_trades)
        gagnants = [t for t in historique_trades if t["resultat"] == "GAGNANT"]
        perdants = [t for t in historique_trades if t["resultat"] == "PERDANT"]
        pct_moyen = round(sum(t["pct"] for t in historique_trades) / total, 2)
        taux = round(len(gagnants) / total * 100, 0)
        msg = msg + (
            "📋 HISTORIQUE (" + str(total) + " trades)\n"
            "✅ Gagnants : " + str(len(gagnants)) + " | ❌ Perdants : " + str(len(perdants)) + "\n"
            "🎯 Taux reussite : " + str(taux) + "%\n"
            "📊 Perf moyenne  : " + ("+" if pct_moyen >= 0 else "") + str(pct_moyen) + "%\n\n"
            "Derniers trades :\n"
        )
        for t in historique_trades[-5:]:
            emoji = "✅" if t["resultat"] == "GAGNANT" else "❌"
            s = "+" if t["pct"] >= 0 else ""
            msg = msg + emoji + " " + t["direction"] + " " + s + str(t["pct"]) + "% (" + t["heure_sortie"] + ")\n"
    else:
        msg = msg + "Aucun trade ferme pour l instant.\n"
    if lecons_apprises:
        msg = msg + "\n🧠 Lecons apprises :\n"
        for l in lecons_apprises[-3:]:
            msg = msg + "- " + l[:100] + "\n"
    msg = msg + "\n─────────────────────────\n"
    msg = msg + "⚠️ SIMULATION - Pas de vrai argent"
    send_telegram(msg)


def run():
    print("Bot Paper Trading BTC demarre")
    send_telegram(
        "🤖 BOT PAPER TRADING BTC\n"
        "\n"
        "Mode SIMULATION - 1 semaine de test\n"
        "\n"
        "💼 Capital simule : " + str(CAPITAL_DEPART) + " USD\n"
        "📊 Levier : x" + str(LEVIER) + "\n"
        "🎯 Risque/trade : " + str(int(RISQUE_PAR_TRADE * 100)) + "% du capital\n"
        "\n"
        "🔄 Decision IA : toutes les 30 min\n"
        "⚡ Check TP/SL : toutes les 5 min\n"
        "📊 Rapport : toutes les 6h\n"
        "⏸️ Pause weekend : OUI\n"
        "\n"
        "⚠️ SIMULATION - Pas de vrai argent\n"
        "Demarrage dans 1 minute..."
    )
    weekend_notified = False
    dernier_check_prix = 0
    derniere_decision = 0
    dernier_rapport = 0
    time.sleep(60)
    while True:
        now = datetime.utcnow()
        if PAUSE_WEEKEND and is_weekend():
            if not weekend_notified:
                send_telegram("⏸️ PAUSE WEEKEND\nReprise lundi 7h Paris.")
                envoyer_rapport()
                weekend_notified = True
            time.sleep(3600)
            continue
        else:
            weekend_notified = False
        if is_heure_creuse():
            print("[" + now.strftime("%H:%M") + " UTC] Heure creuse")
            time.sleep(600)
            continue
        if time.time() - dernier_check_prix >= 300:
            dernier_check_prix = time.time()
            actuel = get_prix_actuel()
            if actuel and position:
                verifier_tp_sl(actuel["prix"])
        if time.time() - derniere_decision >= 1800:
            derniere_decision = time.time()
            print("[" + now.strftime("%H:%M") + " UTC] Prise de decision IA...")
            prendre_decision()
        if time.time() - dernier_rapport >= 21600:
            dernier_rapport = time.time()
            print("[" + now.strftime("%H:%M") + " UTC] Envoi rapport...")
            envoyer_rapport()
        time.sleep(60)


if __name__ == "__main__":
    run()
