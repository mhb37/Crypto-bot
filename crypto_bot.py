import requests
import time
from datetime import datetime

TELEGRAM_TOKEN = "TON_TOKEN"
TELEGRAM_CHAT_ID = "6866451502"
CHECK_INTERVAL_MINUTES = 30

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "XRP": "ripple",
    "ETH": "ethereum",
}

def get_prices(coin_id):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "2", "interval": "hourly"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return [p[1] for p in data["prices"]]
    except Exception as e:
        print(f"Erreur {coin_id}: {e}")
        return None

def calc_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    if al == 0:
        return 100
    return round(100 - 100 / (1 + ag / al), 2)

def send_telegram(message):
    url = f"https://api.telegram.org/bot{8642155934:AAEuhT2QFcoO3vA81fikn-Hn2-iIR4H4SU0}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Erreur Telegram: {e}")

def run():
    print("Bot demarre")
    send_telegram("Robot Crypto demarre ! BTC XRP ETH surveilles.")
    while True:
        print(f"[{datetime.now().strftime('%H:%M')}] Analyse...")
        for ticker, coin_id in COINGECKO_IDS.items():
            prices = get_prices(coin_id)
            if not prices:
                continue
            price = prices[-1]
            rsi = calc_rsi(prices)
            print(f"{ticker}: prix={price:.2f} RSI={rsi}")
            if rsi < 35:
                send_telegram(f"LONG {ticker}\nPrix: {price:.2f} USD\nRSI: {rsi} (survente)")
            elif rsi > 65:
                send_telegram(f"SHORT {ticker}\nPrix: {price:.2f} USD\nRSI: {rsi} (surachat)")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run()
