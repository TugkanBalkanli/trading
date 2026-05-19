import os
import time
import requests
from datetime import datetime

# --- AYARLAR ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

SCAN_INTERVAL = 900  # 15 dakika

# --- TELEGRAM ---
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram hatası: {e}")

# --- BİNANCE KLINE ---
def get_klines(symbol, interval="15m", limit=100):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        closes = [float(c[4]) for c in data]
        volumes = [float(c[5]) for c in data]
        return closes, volumes
    except:
        return None, None

# --- EMA ---
def calc_ema(values, period):
    k = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = v * k + ema * (1 - k)
    return ema

# --- RSI ---
def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# --- RSI SERİSİ ---
def calc_rsi_series(closes, period=14):
    rsi_vals = []
    for i in range(period, len(closes)):
        rsi_vals.append(calc_rsi(closes[:i+1], period))
    return rsi_vals

# --- FUTURES SEMBOLLER ---
def get_futures_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return [s["symbol"] for s in data["symbols"]
                if s["status"] == "TRADING" and s["symbol"].endswith("USDT")]
    except:
        return []

# --- OI ORANI ---
def get_oi_ratio(symbol):
    try:
        oi_r = requests.get("https://fapi.binance.com/fapi/v1/openInterest",
                            params={"symbol": symbol}, timeout=10)
        oi = float(oi_r.json().get("openInterest", 0))

        vol_r = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr",
                             params={"symbol": symbol}, timeout=10)
        vol = float(vol_r.json().get("quoteVolume", 1))

        price_r = requests.get("https://fapi.binance.com/fapi/v1/ticker/price",
                               params={"symbol": symbol}, timeout=10)
        price = float(price_r.json().get("price", 1))

        oi_usd = oi * price
        ratio = (oi_usd / vol) * 100
        return round(ratio, 1)
    except:
        return 0

# --- 24S DEĞİŞİM ---
def get_24h_change(symbol):
    try:
        r = requests.get("https://fapi.binance.com/fapi/v1/ticker/24hr",
                         params={"symbol": symbol}, timeout=10)
        return float(r.json().get("priceChangePercent", 0))
    except:
        return 0

# --- SETUP KONTROL ---
def check_setup(symbol):
    closes, volumes = get_klines(symbol, interval="15m", limit=100)
    if not closes or len(closes) < 50:
        return False, {}

    ema21 = calc_ema(closes, 21)
    rsi = calc_rsi(closes)

    rsi_series = calc_rsi_series(closes)
    if len(rsi_series) < 14:
        return False, {}
    rsi_sma = sum(rsi_series[-14:]) / 14

    # Son 3 mumda hacim artıyor mu
    vol_increasing = volumes[-1] > volumes[-2] > volumes[-3]

    above_ema21 = closes[-1] > ema21
    rsi_ok = 45 <= rsi <= 65
    rsi_above_sma = rsi > rsi_sma

    # Zaten çok fırlamış mı kontrolü (son 3 mumda %5+ hareket varsa geç)
    recent_move = abs(closes[-1] - closes[-4]) / closes[-4] * 100
    not_overextended = recent_move < 5

    if above_ema21 and rsi_ok and rsi_above_sma and vol_increasing and not_overextended:
        return True, {
            "close": closes[-1],
            "ema21": round(ema21, 6),
            "rsi": round(rsi, 1),
            "rsi_sma": round(rsi_sma, 1),
            "recent_move": round(recent_move, 1)
        }
    return False, {}

# --- ANA TARAMA ---
def scan():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Kısa vadeli tarama başladı...")

    symbols = get_futures_symbols()
    print(f"{len(symbols)} coin taranıyor...")

    alerts = []
    for symbol in symbols:
        try:
            setup_ok, data = check_setup(symbol)
            if not setup_ok:
                time.sleep(0.15)
                continue

            oi_ratio = get_oi_ratio(symbol)
            if oi_ratio < 10:
                time.sleep(0.15)
                continue

            change_24h = get_24h_change(symbol)
            alerts.append({
                "symbol": symbol,
                "data": data,
                "oi_ratio": oi_ratio,
                "change_24h": change_24h
            })
            time.sleep(0.15)
        except Exception as e:
            print(f"{symbol} hata: {e}")
            continue

    if alerts:
        # 24s değişime göre sırala, en yükseleni üste
        alerts.sort(key=lambda x: x["change_24h"], reverse=True)
        for alert in alerts[:10]:  # En fazla 10 alert gönder
            s = alert["symbol"]
            d = alert["data"]
            change = alert["change_24h"]
            emoji = "🟢" if change > 0 else "🔴"
            msg = (
                f"⚡ <b>SCALP SETUP: {s}</b>\n\n"
                f"💰 Fiyat: {d['close']}\n"
                f"📊 EMA21: {d['ema21']}\n"
                f"📈 RSI: {d['rsi']} (SMA: {d['rsi_sma']})\n"
                f"📦 OI/Hacim: %{alert['oi_ratio']}\n"
                f"{emoji} 24s Değişim: %{change}\n"
                f"📉 Son hareket: %{d['recent_move']}\n\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}\n"
                f"🕯 M15 grafiği kontrol et!"
            )
            send_telegram(msg)
            print(f"Alert: {s} (%{change})")
    else:
        print("Setup bulunamadı.")

# --- BAŞLAT ---
if __name__ == "__main__":
    send_telegram("⚡ Scalp Bot başlatıldı! BTC filtresi yok, tüm coinler taranıyor.")
    while True:
        scan()
        print(f"Sonraki tarama {SCAN_INTERVAL // 60} dakika sonra...")
        time.sleep(SCAN_INTERVAL)
