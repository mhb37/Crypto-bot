import requests
import time
from datetime import datetime

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════
TELEGRAM_TOKEN   = "8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0"
TELEGRAM_CHAT_ID = "6866451502"

# Seuils assouplis
SEUIL_DETECTION    = 1.0   # % mouvement 1ere alerte (etait 2.0)
SEUIL_CONFIRMATION = 2.0   # % mouvement confirmation (etait 3.5)
SEUIL_EXTREME      = 4.0   # % mouvement extreme (etait 6.0)

CHECK_SEC      = 180       # Check toutes les 3 min (etait 5 min)
PAUSE_WEEKEND  = True
HEURE_DEBUT    = 5         # 5h UTC = 7h Paris
HEURE_FIN      = 21        # 21h UTC = 23h Paris
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
    return datetime.utcnow().weekday() >= 5

def is_heure_creuse():
    h = datetime.utcnow().hour
    return h < HEURE_DEBUT or h >= HEURE_FIN

def get_prix_historique(coin_id, days=2):
    url = "https://api.coingecko.com/api/v3/coins/" + coin_id + "/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": "hourly"}
    try:
        time.sleep(10)
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "prices" not in data:
            return None
        return [p[1] for p in data["prices"]]
    except Exception as e:
        print("Erreur " + coin_id + ": " + str(e))
        return None

def get_prix_actuel(coin_id):
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data[coin_id]["usd"], round(data[coin_id].get("usd_24h_change", 0), 2)
    except:
        return None, None

def analyser_mouvement(ticker, coin_id):
    prices = get_prix_historique(coin_id, days=2)
    if not prices or len(prices) < 6:
        return None

    prix_actuel = prices[-1]
    prix_1h     = prices[-2]  if len(prices) >= 2 else prix_actuel
    prix_2h     = prices[-3]  if len(prices) >= 3 else prix_actuel
    prix_4h     = prices[-5]  if len(prices) >= 5 else prix_actuel
    prix_6h     = prices[-7]  if len(prices) >= 7 else prix_actuel
    prix_24h    = prices[-25] if len(prices) >= 25 else prices[0]

    var_1h  = round((prix_actuel - prix_1h)  / prix_1h  * 100, 2)
    var_2h  = round((prix_actuel - prix_2h)  / prix_2h  * 100, 2)
    var_4h  = round((prix_actuel - prix_4h)  / prix_4h  * 100, 2)
    var_6h  = round((prix_actuel - prix_6h)  / prix_6h  * 100, 2)
    var_24h = round((prix_actuel - prix_24h) / prix_24h * 100, 2)

    direction = "HAUSSE" if var_1h >= 0 else "BAISSE"

    # Coherence direction sur plusieurs periodes
    coherence = 0
    if var_1h > 0 and var_2h > 0: coherence += 1
    if var_2h > 0 and var_4h > 0: coherence += 1
    if var_4h > 0 and var_6h > 0: coherence += 1
    if var_1h < 0 and var_2h < 0: coherence += 1
    if var_2h < 0 and var_4h < 0: coherence += 1
    if var_4h < 0 and var_6h < 0: coherence += 1

    acceleration = abs(var_1h) > abs(var_2h) * 0.8

    return {
        "ticker":       ticker,
        "prix":         prix_actuel,
        "var_1h":       var_1h,
        "var_2h":       var_2h,
        "var_4h":       var_4h,
        "var_6h":       var_6h,
        "var_24h":      var_24h,
        "direction":    direction,
        "coherence":    coherence,
        "acceleration": acceleration,
    }

def niveau_signal(m):
    force_1h = abs(m["var_1h"])
    force_4h = abs(m["var_4h"])

    if force_1h >= SEUIL_EXTREME or force_4h >= SEUIL_EXTREME:
        return "EXTREME"
    elif force_1h >= SEUIL_CONFIRMATION and m["coherence"] >= 1:
        return "CONFIRMATION"
    elif force_1h >= SEUIL_DETECTION:
        return "DETECTION"
    return "AUCUN"

def signe(v):
    return "+" if v >= 0 else ""

def fleche(direction):
    return "HAUSSE" if direction == "HAUSSE" else "BAISSE"

def format_detection(m):
    now = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    return (
        "================================\n"
        "  DETECTION - " + m["ticker"] + "/USDT\n"
        "================================\n"
        "" + now + "\n"
        "Prix : " + str(round(m["prix"], 4)) + " USD\n"
        "\n"
        "Mouvement : " + fleche(m["direction"]) + "\n"
        "1H  : " + signe(m["var_1h"])  + str(m["var_1h"])  + "%\n"
        "4H  : " + signe(m["var_4h"])  + str(m["var_4h"])  + "%\n"
        "24H : " + signe(m["var_24h"]) + str(m["var_24h"]) + "%\n"
        "\n"
        "Mouvement detecte.\n"
        "Surveiller pour confirmation.\n"
        "Ne pas entrer encore.\n"
        "================================"
    )

def format_confirmation(m):
    now      = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    position = "LONG" if m["direction"] == "HAUSSE" else "SHORT"
    accel    = "OUI" if m["acceleration"] else "NON"
    return (
        "================================\n"
        "  SIGNAL CONFIRME - " + position + "\n"
        "================================\n"
        "" + m["ticker"] + "/USDT   " + now + "\n"
        "Prix entree : " + str(round(m["prix"], 4)) + " USD\n"
        "\n"
        "Direction    : " + fleche(m["direction"]) + "\n"
        "Coherence    : " + str(m["coherence"]) + "/3\n"
        "Acceleration : " + accel + "\n"
        "\n"
        "1H  : " + signe(m["var_1h"])  + str(m["var_1h"])  + "%\n"
        "2H  : " + signe(m["var_2h"])  + str(m["var_2h"])  + "%\n"
        "4H  : " + signe(m["var_4h"])  + str(m["var_4h"])  + "%\n"
        "6H  : " + signe(m["var_6h"])  + str(m["var_6h"])  + "%\n"
        "24H : " + signe(m["var_24h"]) + str(m["var_24h"]) + "%\n"
        "\n"
        "================================\n"
        " RENTRER EN POSITION " + position + "\n"
        " Maintenir jusqu'a inversion\n"
        "================================\n"
        "Pas un conseil financier\n"
        "================================"
    )

def format_extreme(m):
    now      = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    position = "LONG" if m["direction"] == "HAUSSE" else "SHORT"
    return (
        "================================\n"
        "  MOUVEMENT EXTREME !\n"
        "================================\n"
        "" + m["ticker"] + "/USDT   " + now + "\n"
        "Prix : " + str(round(m["prix"], 4)) + " USD\n"
        "\n"
        "1H  : " + signe(m["var_1h"])  + str(m["var_1h"])  + "%\n"
        "4H  : " + signe(m["var_4h"])  + str(m["var_4h"])  + "%\n"
        "24H : " + signe(m["var_24h"]) + str(m["var_24h"]) + "%\n"
        "\n"
        "VERIFIER LES NEWS !\n"
        "Evenement majeur possible.\n"
        "Si confirmation : " + position + "\n"
        "Prudence sur le levier.\n"
        "================================\n"
        "Pas un conseil financier\n"
        "================================"
    )

def format_inversion(ticker, prix, ancienne_dir, nouvelle_dir):
    now      = datetime.utcnow().strftime("%d/%m %H:%M") + " UTC"
    position = "LONG" if nouvelle_dir == "HAUSSE" else "SHORT"
    return (
        "================================\n"
        "  INVERSION DETECTEE\n"
        "================================\n"
        "" + ticker + "/USDT   " + now + "\n"
        "Prix : " + str(round(prix, 4)) + " USD\n"
        "\n"
        "Tendance " + fleche(ancienne_dir) + " terminee.\n"
        "Nouveau mouvement : " + fleche(nouvelle_dir) + "\n"
        "\n"
        "FERMER LA POSITION EN COURS.\n"
        "Surveiller pour nouveau " + position + ".\n"
        "================================\n"
        "Pas un conseil financier\n"
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
            msg += "- " + s + "\n"
    msg += "================================"
    return msg

def run():
    print("Bot V5 demarre")
    send_telegram(
        "================================\n"
        "  CRYPTO SIGNAL BOT V5\n"
        "================================\n"
        "Paires      : BTC / XRP / ETH\n"
        "Mode        : Mouvements prix\n"
        "Check       : toutes les 3 min\n"
        "Detection   : " + str(SEUIL_DETECTION) + "%\n"
        "Confirmation: " + str(SEUIL_CONFIRMATION) + "%\n"
        "Extreme     : " + str(SEUIL_EXTREME) + "%\n"
        "Filtre      : 7h - 23h Paris\n"
        "Pause WE    : OUI\n"
        "================================"
    )

    etat = {
        "BTC": {"direction": None, "alerte_envoyee": "AUCUN"},
        "XRP": {"direction": None, "alerte_envoyee": "AUCUN"},
        "ETH": {"direction": None, "alerte_envoyee": "AUCUN"},
    }

    weekend_notified = False
    signaux_du_jour  = []
    last_recap_day   = -1

    while True:
        now = datetime.utcnow()

        # Recap 18h UTC = 20h Paris
        if now.hour == 18 and now.day != last_recap_day:
            send_telegram(format_recap(signaux_du_jour))
            signaux_du_jour = []
            last_recap_day  = now.day

        # Pause weekend
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
                for t in etat:
                    etat[t] = {"direction": None, "alerte_envoyee": "AUCUN"}
            time.sleep(3600)
            continue
        else:
            weekend_notified = False

        # Heure creuse
        if is_heure_creuse():
            print("[" + now.strftime("%H:%M") + " UTC] Heure creuse")
            time.sleep(CHECK_SEC)
            continue

        print("[" + now.strftime("%H:%M") + " UTC] Analyse...")

        for ticker, coin_id in COINS.items():
            m = analyser_mouvement(ticker, coin_id)
            if m is None:
                print(ticker + ": erreur donnees")
                continue

            niveau = niveau_signal(m)
            e      = etat[ticker]

            print(
                ticker +
                " 1H=" + str(m["var_1h"]) + "%" +
                " 4H=" + str(m["var_4h"]) + "%" +
                " coh=" + str(m["coherence"]) +
                " -> " + niveau
            )

            # Inversion de tendance
            if (e["direction"] is not None and
                e["alerte_envoyee"] == "CONFIRMATION" and
                m["direction"] != e["direction"] and
                abs(m["var_1h"]) >= SEUIL_DETECTION):
                send_telegram(format_inversion(ticker, m["prix"], e["direction"], m["direction"]))
                signaux_du_jour.append(ticker + " : INVERSION vers " + m["direction"])
                etat[ticker] = {"direction": m["direction"], "alerte_envoyee": "DETECTION"}
                time.sleep(2)
                continue

            # EXTREME
            if niveau == "EXTREME" and e["alerte_envoyee"] != "EXTREME":
                send_telegram(format_extreme(m))
                signaux_du_jour.append(ticker + " : EXTREME " + m["direction"])
                etat[ticker]["alerte_envoyee"] = "EXTREME"
                etat[ticker]["direction"]       = m["direction"]
                time.sleep(2)

            # CONFIRMATION
            elif niveau == "CONFIRMATION" and e["alerte_envoyee"] not in ("CONFIRMATION", "EXTREME"):
                send_telegram(format_confirmation(m))
                signaux_du_jour.append(ticker + " : SIGNAL " + ("LONG" if m["direction"] == "HAUSSE" else "SHORT"))
                etat[ticker]["alerte_envoyee"] = "CONFIRMATION"
                etat[ticker]["direction"]       = m["direction"]
                time.sleep(2)

            # DETECTION
            elif niveau == "DETECTION" and e["alerte_envoyee"] == "AUCUN":
                send_telegram(format_detection(m))
                signaux_du_jour.append(ticker + " : DETECTION " + m["direction"])
                etat[ticker]["alerte_envoyee"] = "DETECTION"
                etat[ticker]["direction"]       = m["direction"]
                time.sleep(2)

            # Reset si calme
            elif niveau == "AUCUN" and abs(m["var_1h"]) < 0.5 and abs(m["var_4h"]) < 1.5:
                etat[ticker] = {"direction": None, "alerte_envoyee": "AUCUN"}

        time.sleep(CHECK_SEC)

if __name__ == "__main__":
    run()
